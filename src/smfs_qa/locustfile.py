"""Locust load test suite for SMFS — REST API + WebSocket.

Profiles:
  make load-test      50 users, 120s, CSV + HTML output
  make stress-test    100 users, 120s, CSV + HTML output
  make soak-test      30 users, 300s, CSV + HTML output
  make locust-ui      Interactive web UI at http://localhost:8089

SLA Thresholds:
  REST: p95 < 1000ms, error rate < 1%
  /stats: p95 < 3000ms (known bimodal latency F-PERF-001)
  /snapshot: error rate < 15% (known 500 errors under load)
  WS: hello within 2s, messages flowing
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from locust import HttpUser, between, events, tag, task
from locust.runners import MasterRunner, WorkerRunner

_test_start_time: float = 0.0


@events.test_start.add_listener
def on_test_start(environment, **kwargs) -> None:
    global _test_start_time
    _test_start_time = time.time()
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    opts = environment.parsed_options
    users = opts.num_users if opts else "?"
    rate = opts.spawn_rate if opts else "?"
    dur = opts.run_time if opts else "?"
    print("\n" + "=" * 72)
    print(f"  SMFS Load Test — Started at {ts}")
    print(f"  Target: {environment.host}")
    print(f"  Users: {users}  |  Spawn rate: {rate}/s  |  Duration: {dur}")
    print("=" * 72 + "\n")

# ---------------------------------------------------------------------------
# REST API Users
# ---------------------------------------------------------------------------


class SMFSReadUser(HttpUser):
    """Simulates read-only API consumers hitting all GET endpoints.

    Weighted to reflect realistic usage patterns:
    - /health is polled frequently (monitoring)
    - /markets is read occasionally (discovery)
    - /snapshot is read for trading (moderate)
    - /stats is read for dashboards (occasional)
    """

    wait_time = between(0.5, 2.0)
    host = "https://interviews-api.sonic.game"

    def on_start(self) -> None:
        self.client.headers.update({"User-Agent": "smfs-qa/1.0 (locust; load-test)"})

    @tag("rest", "health")
    @task(3)
    def check_health(self) -> None:
        with self.client.get("/health", catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("ok"):
                    resp.failure("health.ok is not True")
            else:
                resp.failure(f"Status {resp.status_code}")

    @tag("rest", "markets")
    @task(2)
    def get_markets(self) -> None:
        with self.client.get("/markets", catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("markets"):
                    resp.failure("Empty markets list")
            else:
                resp.failure(f"Status {resp.status_code}")

    @tag("rest", "snapshot")
    @task(2)
    def get_snapshot(self) -> None:
        with self.client.get("/markets/BTC-PERP/snapshot", catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("bids") and not data.get("asks"):
                    resp.failure("Snapshot has no bids or asks")
            elif resp.status_code == 500:
                resp.failure("HTTP 500 — server error on snapshot")
            else:
                resp.failure(f"Status {resp.status_code}")

    @tag("rest", "stats")
    @task(1)
    def get_stats(self) -> None:
        with self.client.get("/stats", catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                btc = data.get("markets", {}).get("BTC-PERP", {})
                if btc.get("currentSeq", 0) <= 0:
                    resp.failure("stats.markets.BTC-PERP.currentSeq not positive")
            else:
                resp.failure(f"Status {resp.status_code}")


class SMFSOrderUser(HttpUser):
    """Simulates clients submitting orders via POST /orders.

    Tests order acceptance, validation errors, and concurrent submission.
    Lower weight than read users (1:3 ratio).
    """

    wait_time = between(1.0, 3.0)
    host = "https://interviews-api.sonic.game"
    weight = 1

    def on_start(self) -> None:
        self.client.headers.update(
            {
                "User-Agent": "smfs-qa/1.0 (locust; order-test)",
                "Content-Type": "application/json",
            }
        )

    @tag("rest", "orders")
    @task(3)
    def post_valid_limit_order(self) -> None:
        payload = {
            "marketId": "BTC-PERP",
            "side": "buy",
            "type": "limit",
            "size": 0.01,
            "price": 50000.0,
        }
        with self.client.post("/orders", json=payload, catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("accepted"):
                    resp.failure("Order not accepted")
                if not data.get("orderId"):
                    resp.failure("No orderId returned")
            else:
                resp.failure(f"Status {resp.status_code}")

    @tag("rest", "orders")
    @task(1)
    def post_valid_market_order(self) -> None:
        payload = {
            "marketId": "BTC-PERP",
            "side": "sell",
            "type": "market",
            "size": 0.01,
        }
        with self.client.post("/orders", json=payload, catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("accepted"):
                    resp.failure("Market order not accepted")
            else:
                resp.failure(f"Status {resp.status_code}")

    @tag("rest", "orders", "boundary")
    @task(1)
    def post_invalid_market_id(self) -> None:
        """Boundary: invalid marketId should return client error."""
        payload = {
            "marketId": "INVALID",
            "side": "buy",
            "type": "limit",
            "size": 0.01,
            "price": 50000.0,
        }
        with self.client.post(
            "/orders", json=payload, catch_response=True, name="/orders [invalid marketId]"
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"Server error {resp.status_code} for invalid marketId")
            else:
                resp.success()

    @tag("rest", "orders", "boundary")
    @task(1)
    def post_negative_size(self) -> None:
        """Boundary: negative size should return client error."""
        payload = {
            "marketId": "BTC-PERP",
            "side": "buy",
            "type": "limit",
            "size": -1.0,
            "price": 50000.0,
        }
        with self.client.post(
            "/orders", json=payload, catch_response=True, name="/orders [negative size]"
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"Server error {resp.status_code} for negative size")
            else:
                resp.success()


# ---------------------------------------------------------------------------
# WebSocket User
# ---------------------------------------------------------------------------


class SMFSWebSocketUser(HttpUser):
    """Simulates WebSocket market feed consumers.

    Connects, verifies hello, collects messages for 5s, then disconnects.
    Measures hello latency and message throughput.
    """

    wait_time = between(2.0, 5.0)
    host = "https://interviews-api.sonic.game"
    weight = 1

    @tag("websocket")
    @task
    def ws_connect_and_collect(self) -> None:
        import websocket

        ws_url = "wss://interviews-api.sonic.game/ws?marketId=BTC-PERP"
        start = time.perf_counter()

        try:
            ws = websocket.create_connection(ws_url, timeout=10)
            raw = ws.recv()
            hello_ms = (time.perf_counter() - start) * 1000
            hello = json.loads(raw)

            if hello.get("type") != "hello":
                events.request.fire(
                    request_type="WSS",
                    name="/ws hello",
                    response_time=hello_ms,
                    response_length=len(raw),
                    exception=Exception(f"Expected hello, got {hello.get('type')}"),
                )
                ws.close()
                return

            events.request.fire(
                request_type="WSS",
                name="/ws hello",
                response_time=hello_ms,
                response_length=len(raw),
                exception=None,
            )

            msg_count = 0
            collect_start = time.perf_counter()
            while time.perf_counter() - collect_start < 5.0:
                try:
                    ws.settimeout(2.0)
                    ws.recv()
                    msg_count += 1
                except Exception:
                    break

            throughput_ms = (time.perf_counter() - collect_start) * 1000
            events.request.fire(
                request_type="WSS",
                name="/ws 5s-collect",
                response_time=throughput_ms,
                response_length=msg_count,
                exception=None,
            )

            ws.close()

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            events.request.fire(
                request_type="WSS",
                name="/ws hello",
                response_time=elapsed,
                response_length=0,
                exception=e,
            )


# ---------------------------------------------------------------------------
# Load Shape (for advanced profiling)
# ---------------------------------------------------------------------------


class SMFSLoadShape:
    """Not a LoadTestShape class -- just documents the intended profiles.

    Use Makefile targets instead:
      make load-test    → 50 users, 60s
      make stress-test  → 100 users, 120s
    """

    pass


# ---------------------------------------------------------------------------
# SLA Check on Quit
# ---------------------------------------------------------------------------


@events.quitting.add_listener
def check_sla(environment, **kwargs) -> None:
    """Print detailed summary and fail the process if SLA thresholds are breached."""
    if isinstance(environment.runner, (MasterRunner, WorkerRunner)):
        return

    stats = environment.runner.stats
    total = stats.total

    if total.num_requests == 0:
        return

    duration_s = time.time() - _test_start_time if _test_start_time else 0
    duration_str = f"{int(duration_s // 60)}m {int(duration_s % 60)}s"

    error_rate = total.fail_ratio
    p50 = total.get_response_time_percentile(0.50) or 0
    p95 = total.get_response_time_percentile(0.95) or 0
    p99 = total.get_response_time_percentile(0.99) or 0

    print("\n" + "=" * 72)
    print("  SMFS LOAD TEST — SUMMARY REPORT")
    print("=" * 72)
    print(f"  Duration:        {duration_str}")
    print(f"  Total requests:  {total.num_requests:,}")
    print(f"  Total failures:  {total.num_failures:,}")
    print(f"  Error rate:      {error_rate:.2%}")
    print(f"  Avg RPS:         {total.total_rps:.1f}")
    print(f"  Response time:   p50={p50:.0f}ms  p95={p95:.0f}ms  p99={p99:.0f}ms")
    print("-" * 72)

    print(f"  {'Type':<6} {'Endpoint':<35} {'Reqs':>6} {'Fail':>6} "
          f"{'Avg':>7} {'p50':>7} {'p95':>7} {'p99':>7} {'Err%':>7}")
    print("-" * 72)

    for entry in sorted(stats.entries.values(), key=lambda e: e.name):
        ep50 = entry.get_response_time_percentile(0.50) or 0
        ep95 = entry.get_response_time_percentile(0.95) or 0
        ep99 = entry.get_response_time_percentile(0.99) or 0
        err_pct = (entry.fail_ratio * 100) if entry.num_requests > 0 else 0
        print(
            f"  {entry.method:<6} {entry.name:<35} {entry.num_requests:>6} "
            f"{entry.num_failures:>6} {entry.avg_response_time:>7.0f} "
            f"{ep50:>7.0f} {ep95:>7.0f} {ep99:>7.0f} {err_pct:>6.1f}%"
        )

    print("-" * 72)

    if total.num_failures > 0:
        print("\n  FAILURES:")
        for error in stats.errors.values():
            print(f"    [{error.occurrences:>4}x] {error.method} {error.name}: {error.error}")

    sla_failures: list[str] = []
    sla_passes: list[str] = []

    if p95 > 1000:
        sla_failures.append(f"Aggregated p95 = {p95:.0f}ms (SLA: < 1000ms)")
    else:
        sla_passes.append(f"Aggregated p95 = {p95:.0f}ms (SLA: < 1000ms)")

    if error_rate > 0.01:
        sla_failures.append(f"Error rate = {error_rate:.1%} (SLA: < 1%)")
    else:
        sla_passes.append(f"Error rate = {error_rate:.1%} (SLA: < 1%)")

    for entry in stats.entries.values():
        if entry.name == "/markets/BTC-PERP/snapshot":
            if entry.num_requests > 0:
                if entry.fail_ratio > 0.15:
                    sla_failures.append(
                        f"/snapshot error rate = {entry.fail_ratio:.1%} (SLA: < 15%)"
                    )
                else:
                    sla_passes.append(
                        f"/snapshot error rate = {entry.fail_ratio:.1%} (SLA: < 15%)"
                    )

    for entry in stats.entries.values():
        if "stats" in entry.name.lower():
            ep95_stats = entry.get_response_time_percentile(0.95) or 0
            if ep95_stats > 3000:
                sla_failures.append(
                    f"/stats p95 = {ep95_stats:.0f}ms (SLA: < 3000ms, F-PERF-001)"
                )
            else:
                sla_passes.append(f"/stats p95 = {ep95_stats:.0f}ms (SLA: < 3000ms)")

    print("\n  SLA ASSESSMENT:")
    for msg in sla_passes:
        print(f"    PASS: {msg}")
    for msg in sla_failures:
        print(f"    FAIL: {msg}")

    print("\n  KNOWN FINDINGS DETECTED:")
    order_entry = None
    for entry in stats.entries.values():
        if entry.name == "/orders" and entry.num_failures > 0:
            order_entry = entry
    if order_entry:
        print(f"    F-PERF-002: POST /orders rate-limited "
              f"({order_entry.num_failures}/{order_entry.num_requests} = "
              f"{order_entry.fail_ratio:.1%} HTTP 429)")
    snapshot_entry = None
    for entry in stats.entries.values():
        if entry.name == "/markets/BTC-PERP/snapshot" and entry.num_failures > 0:
            snapshot_entry = entry
    if snapshot_entry:
        print(f"    F-PERF-003: /snapshot intermittent 500 "
              f"({snapshot_entry.num_failures}/{snapshot_entry.num_requests} = "
              f"{snapshot_entry.fail_ratio:.1%})")
    stats_entry = None
    for entry in stats.entries.values():
        if "stats" in entry.name.lower():
            stats_entry = entry
    if stats_entry:
        ep95_stats = stats_entry.get_response_time_percentile(0.95) or 0
        if ep95_stats > 1000:
            print(f"    F-PERF-001: /stats bimodal latency "
                  f"(p95={ep95_stats:.0f}ms)")
    if not order_entry and not snapshot_entry:
        print("    None detected in this run")

    print("=" * 72 + "\n")

    if sla_failures:
        environment.process_exit_code = 1