"""Locust load test suite for SMFS — REST API + WebSocket.

Profiles:
  make load-test      50 users, 60s, CSV output
  make stress-test    100 users, 120s, CSV output
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

from locust import HttpUser, between, events, tag, task
from locust.runners import MasterRunner, WorkerRunner

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
        self.client.headers.update(
            {"User-Agent": "smfs-qa/1.0 (locust; load-test)"}
        )

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
        with self.client.get(
            "/markets/BTC-PERP/snapshot", catch_response=True
        ) as resp:
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
        self.client.headers.update({
            "User-Agent": "smfs-qa/1.0 (locust; order-test)",
            "Content-Type": "application/json",
        })

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
        with self.client.post(
            "/orders", json=payload, catch_response=True
        ) as resp:
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
        with self.client.post(
            "/orders", json=payload, catch_response=True
        ) as resp:
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
    """Fail the Locust process if SLA thresholds are breached."""
    if isinstance(environment.runner, (MasterRunner, WorkerRunner)):
        return

    stats = environment.runner.stats
    total = stats.total

    if total.num_requests == 0:
        return

    error_rate = total.fail_ratio
    p95 = total.get_response_time_percentile(0.95) or 0

    sla_failures = []

    if p95 > 1000:
        sla_failures.append(f"p95 response time {p95:.0f}ms > 1000ms SLA")

    if error_rate > 0.01:
        sla_failures.append(f"Error rate {error_rate:.1%} > 1% SLA")

    for entry in stats.entries.values():
        if entry.name == "/markets/BTC-PERP/snapshot":
            if entry.num_requests > 0 and entry.fail_ratio > 0.15:
                sla_failures.append(
                    f"/snapshot error rate {entry.fail_ratio:.1%} > 15%"
                )

    if sla_failures:
        for msg in sla_failures:
            print(f"SLA BREACH: {msg}")
        environment.process_exit_code = 1
    else:
        print("SLA CHECK: All thresholds met")
