# TEST_PLAN.md -- Sonic Market Feed Service Quality Audit

**Version:** 1.1
**Author:** Samuel Cheng
**Date:** 2026-03-20
**System Under Test:** Sonic Market Feed Service (SMFS)
**Approach:** Black-box quality audit against a live production service

---

## Table of Contents

1. [Scope](#1-scope)
2. [Risk Analysis](#2-risk-analysis)
3. [Test Categories](#3-test-categories)
4. [Priority Matrix](#4-priority-matrix)
5. [Non-Determinism Strategy](#5-non-determinism-strategy)
6. [xfail Strategy with Finding IDs](#6-xfail-strategy-with-finding-ids)
7. [Entry and Exit Criteria](#7-entry-and-exit-criteria)
8. [Test Environment](#8-test-environment)
9. [Test Architecture](#9-test-architecture)
10. [Test Coverage Matrix](#10-test-coverage-matrix)
11. [Performance Testing Strategy](#11-performance-testing-strategy)
12. [Reporting](#12-reporting)
13. [Schedule and Dependencies](#13-schedule-and-dependencies)

---

## 1. Scope

### 1.1 In-Scope

| Component | Surface Area | Protocols |
|-----------|-------------|-----------|
| **REST API** | 5 endpoints: `GET /health`, `GET /markets`, `GET /markets/{marketId}/snapshot`, `POST /orders`, `GET /stats` | HTTPS, JSON |
| **WebSocket Market Feed** | Real-time order book deltas and trades for BTC-PERP | WSS, JSON messages |
| **Solana Transaction Stream** | Real-time Solana transaction streaming with subscribe/filter | WSS, JSON messages |
| **Cross-Component** | REST-to-WebSocket data consistency, error format consistency | Mixed |
| **Performance** | Latency benchmarks, throughput measurement, concurrent connection scaling | All |

**Testing types included:**
- Functional testing (positive and negative paths)
- Schema validation (Pydantic v2 strict mode against OpenAPI 3.1 spec)
- Integration testing (cross-component data consistency)
- Performance testing (latency percentiles, throughput, concurrent connections)
- Edge case testing (boundary values, malformed input, injection attempts)
- Resilience testing (reconnection, burst traffic, graceful degradation)

### 1.2 Out-of-Scope

| Item | Reason |
|------|--------|
| Source code review | Black-box engagement -- no source code access |
| Deployment/infrastructure testing | No access to deployment pipeline or infrastructure |
| Authentication/authorization | The SMFS API has no authentication mechanism |
| Database testing | No direct database access |
| UI/frontend testing | No frontend component in scope |
| Load testing beyond 100 concurrent users | Production service -- avoid causing disruption |
| Penetration testing | Out of scope for quality audit; only basic injection safety checks |

---

## 2. Risk Analysis

### 2.1 Risk Matrix

| ID | Risk Area | Component | Likelihood | Impact | Severity | Mitigation |
|----|-----------|-----------|------------|--------|----------|------------|
| R-01 | Cloudflare bot protection | REST | Confirmed | Critical | **Critical** | User-Agent header in SMFSClient (F-INFRA-001, mitigated) |
| R-02 | Floating-point price artifacts | REST + WS | Confirmed | Medium | **Medium** | xfail F-REST-001/F-WS-002/F-WS-003; statistical sampling across 3 snapshots |
| R-03 | Crossed order book | REST | Medium | High | **High** | xfail F-REST-002; statistical detection over multiple snapshots |
| R-04 | Error format inconsistency | REST | Confirmed | Medium | **Medium** | xfail F-REST-004; error responses use text/plain not application/json |
| R-05 | Invalid marketId silently accepted | WebSocket | Confirmed | High | **High** | xfail F-WS-001; test with invalid/missing marketId |
| R-06 | Subscribe data intermittent | Solana | Confirmed | High | **High** | Deep investigation via F-SOL-001/F-SOL-002; 5 subscribe variants, 30-60s waits |
| R-07 | Sequence ordering violations | WebSocket | Low | High | **High** | Collect 50+ messages; assert strict monotonic increment |
| R-08 | Reconnection data loss | WebSocket | Medium | Medium | **Medium** | Verify fresh hello after reconnect |
| R-09 | Transient network failures | All | High | Low | **Medium** | pytest-rerunfailures with 3 retries, 2s delay |
| R-10 | GET /orders returns 404 | REST | Expected | None | **None** | Only POST /orders is documented; 404 is correct behavior |
| R-11 | Production service instability | All | Medium | High | **High** | Explicit timeouts, statistical assertions |

### 2.2 Component Risk Ranking

| Rank | Component | Risk Level | Rationale |
|------|-----------|------------|-----------|
| 1 | **Solana Transaction Stream** | High | Subscribe data delivery is intermittent (~60% success) with no acknowledgment; reliability is insufficient for production use (F-SOL-001, F-SOL-002) |
| 2 | **WebSocket Market Feed** | High | Invalid marketId silently accepted (F-WS-001); floating-point artifacts in prices (F-WS-002, F-WS-003) |
| 3 | **REST API** | Medium | All 5 endpoints operational; known issues are float artifacts in snapshot (F-REST-001), crossed book (F-REST-002), error format (F-REST-004) |
| 4 | **Cross-Component Integration** | Medium | REST-to-WS consistency testable; Stats seq correlates with WS seq |
| 5 | **Infrastructure** | Low | Cloudflare bot protection requires User-Agent header (F-INFRA-001, mitigated in client.py) |

---

## 3. Test Categories

### 3.1 Functional Tests

**Positive path:** Verify each endpoint/message type returns the documented schema and status code when given valid input.

**Negative path:** Verify the service handles invalid input gracefully -- returns appropriate error codes, does not crash, does not expose internal details.

| Sub-category | Description | Example |
|--------------|-------------|---------|
| Happy path | Valid request, valid response | `GET /health` returns 200 with `{ok, serverTime, markets, wsUrl}` |
| Error handling | Invalid input produces correct error | `POST /orders` accepts most payloads and returns 200; server-side validation is lenient |
| Method rejection | Wrong HTTP method returns 405 | `POST /health` should return 405 (finding: returns 404) |
| Schema validation | Response body matches OpenAPI spec | All required fields present with correct types |

### 3.2 Integration Tests (Cross-Component)

| Test | Components | Validation |
|------|-----------|------------|
| Health wsUrl connects | REST + WS | WebSocket URL from `/health` response successfully connects |
| Markets match WS | REST + WS | `marketId` in `/markets` response matches WebSocket `hello.marketId` |
| Stats seq correlates with WS seq | REST + WS | `currentSeq` from `/stats` is within reasonable range of observed WS `seq` |
| Stats rate correlates with WS rate | REST + WS | Observed message rate is at least 50% of declared `bookUpdatesPerSecond` |
| Book delta timestamps monotonic | WS | `ts` values are non-decreasing across consecutive messages |
| Sequence contiguity end-to-end | WS | No gaps in sequence numbers over 50+ messages |

### 3.3 Performance Tests

| Metric | Target | Method |
|--------|--------|--------|
| REST p50 latency | < 500ms | 100 sequential requests, compute percentiles |
| REST p95 latency | < 2000ms | Same sample, 95th percentile |
| REST p99 latency | < 3000ms | Same sample, 99th percentile |
| WS message throughput | >= 1 msg/s | Measure over 30s window |
| Concurrent WS connections | 5 simultaneous | All receive hello + data |
| Burst tolerance | 20 requests in <1s | 100% success rate |
| Locust SLA compliance | p95 < 1000ms, error rate < 1% | 50-user headless run, 120s duration |

### 3.4 Edge Case Tests

| Category | Examples |
|----------|----------|
| Boundary values | Empty string marketId, 1000-character marketId, zero-size order, negative price |
| Injection safety | SQL injection (`' OR 1=1 --`), path traversal (`../../etc/passwd`), XSS (`<script>alert(1)</script>`) |
| Protocol edge cases | Trailing slashes (`/health/`), extra query params (`?foo=bar`), HEAD requests, OPTIONS preflight |
| Encoding | Unicode marketId, emoji in path, URL-encoded special characters |
| WebSocket edge cases | Sending binary frames, invalid JSON, extremely large messages |

---

## 4. Priority Matrix

### 4.1 P0 -- Must Test (Blocking for audit completion)

These tests validate core functionality. If any P0 test fails unexpectedly (not covered by a known finding), the audit cannot proceed to completion.

| Test ID | Component | Test Description | Finding |
|---------|-----------|-----------------|---------|
| TC-REST-001 | REST | `GET /health` returns 200 | -- |
| TC-REST-002 | REST | Health response matches schema `{ok, serverTime, markets, wsUrl}` | -- |
| TC-REST-003 | REST | `health.ok` is `true` | -- |
| TC-REST-004 | REST | `health.serverTime` is within 30s of current time | -- |
| TC-REST-005 | REST | `health.markets` contains `"BTC-PERP"` | -- |
| TC-REST-006 | REST | `health.wsUrl` starts with `wss://` | -- |
| TC-REST-007 | REST | Health response `Content-Type` is `application/json` | -- |
| TC-REST-016 | REST | `GET /markets` returns 200 | -- |
| TC-REST-017 | REST | Markets response matches schema `{markets: [{marketId, base, quote}]}` | -- |
| TC-REST-018 | REST | Markets list is non-empty | -- |
| TC-REST-019 | REST | BTC-PERP has `base=BTC`, `quote=USDT` | -- |
| TC-REST-025 | REST | `GET /stats` returns 200 | -- |
| TC-REST-034 | REST | `GET /markets/BTC-PERP/snapshot` returns 200 — xfail on float artifacts | F-REST-001 |
| TC-REST-037 | REST | `POST /orders` valid limit order accepted | -- |
| TC-WS-001 | WebSocket | First message after connect is `type: "hello"` | -- |
| TC-WS-002 | WebSocket | Hello message validates against `WsHelloMessage` schema | -- |
| TC-WS-003 | WebSocket | `hello.marketId` matches query parameter `BTC-PERP` | -- |
| TC-WS-007 | WebSocket | Ping/pong: send `{"type":"ping"}`, receive `{"type":"pong"}` | -- |
| TC-WS-012 | WebSocket | `book_delta` messages received after hello | -- |
| TC-WS-013 | WebSocket | `book_delta` validates against `WsBookDeltaMessage` schema | -- |
| TC-WS-019 | WebSocket | Sequence numbers are strictly monotonic (seq[i] > seq[i-1]) over 50+ messages | -- |
| TC-WS-022 | WebSocket | Trade messages validate against `WsTradeMessage` schema | -- |
| TC-WS-028 | WebSocket | Graceful close: `ws.close()` without error | -- |
| TC-WS-030 | WebSocket | Reconnection: new connection receives new hello | -- |
| TC-SOL-001 | Solana | Stream connection receives `type: "stream_hello"` | -- |
| TC-SOL-002 | Solana | Stream hello validates against schema | -- |
| TC-SOL-007 | Solana | Stream ping/pong works | -- |
| TC-SOL-012 | Solana | Subscribe produces transaction data | F-SOL-001 (xfail) |
| TC-SOL-023 | Solana | `SolanaTransaction` Pydantic model accepts valid data | -- |
| TC-SOL-027 | Solana | Negative fee rejected by schema validation | -- |
| TC-SOL-033 | Solana | 87-character Base58 signature validates as valid | -- |
| TC-SOL-034 | Solana | 88-character Base58 signature validates as valid | -- |
| TC-E2E-001 | Integration | Health `wsUrl` can be used to establish WebSocket connection | -- |
| TC-E2E-002 | Integration | `marketId` in `/markets` response appears in WebSocket `hello` | -- |

### 4.2 P1 -- Should Test (Important for audit quality)

| Test ID | Component | Test Description |
|---------|-----------|-----------------|
| TC-REST-008 | REST | `POST /health` returns 4xx (not 5xx) |
| TC-REST-009 | REST | `PUT /health` returns 4xx |
| TC-REST-010 | REST | `DELETE /health` returns 4xx |
| TC-REST-026 | REST | Stats schema validation `{markets: {BTC-PERP: {bookUpdatesPerSecond, tradesPerSecond, currentSeq}}, connectedClients}` |
| TC-REST-031 | REST | Stats `currentSeq` increases between two calls |
| TC-REST-036 | REST | Boundary marketId values (empty, 1000-char, injection) do not cause 5xx |
| TC-REST-040 | REST | Error responses have `Content-Type: application/json` |
| TC-REST-044 | REST | SQL injection in marketId does not cause 5xx |
| TC-WS-020 | WebSocket | Sequence numbers are contiguous (gap = 1) |
| TC-WS-034 | WebSocket | Reconnection produces fresh hello on each connection |
| TC-SOL-043 | Solana | Slot ordering is monotonic (unit test) |
| TC-E2E-004 | Integration | Book delta `ts` values are non-decreasing |
| TC-E2E-007 | Integration | No sequence gaps in end-to-end collection |
| TC-E2E-008 | Integration | Stats `currentSeq` within 1000 of observed WS seq |
| TC-E2E-009 | Integration | Observed WS rate >= 50% of declared rate in stats |
| TC-PERF-001 | Performance | Health endpoint p50 latency < 500ms |
| TC-PERF-002 | Performance | Health endpoint p95 latency < 2000ms |
| TC-PERF-003 | Performance | Health endpoint p99 latency < 3000ms |
| TC-PERF-007 | Performance | WebSocket throughput >= 1 msg/s |
| TC-PERF-009 | Performance | 5 concurrent WebSocket connections all succeed |
| TC-PERF-011 | Performance | 20 burst requests at 100% success rate |

### 4.3 P2 -- Nice to Test (Time permitting)

| Test ID | Component | Test Description |
|---------|-----------|-----------------|
| TC-REST-012 | REST | `HEAD /health` returns 200 with empty body |
| TC-REST-013 | REST | Extra query params are ignored |
| TC-REST-014 | REST | Trailing slash does not cause 5xx |
| TC-REST-015 | REST | `OPTIONS /health` returns CORS headers |
| TC-REST-049 | REST | CORS `Access-Control-Allow-Origin: *` header present |
| TC-REST-052 | REST | `GET /ws` returns 400 (WebSocket upgrade required) |
| Advanced WS | WebSocket | 10+ concurrent connections, message loss detection under burst |
| Advanced Solana | Solana | Reorg detection, duplicate transaction detection, program ID validation |
| Advanced Perf | Performance | Locust stress test at 100 users, idle disconnect timing |

---

## 5. Non-Determinism Strategy

The SMFS is a live production service with inherent non-determinism. This section documents how each source of non-determinism is handled.

### 5.1 Transient Network Failures

**Problem:** Network timeouts, connection resets, and intermittent 5xx errors can cause false test failures.

**Solution:** Automatic retry with `pytest-rerunfailures`.

```python
# Global: configured in pyproject.toml addopts
# Per-test override for known-flaky tests:
@pytest.mark.flaky(reruns=3, reruns_delay=2)
async def test_ws_reconnection():
    ...
```

**Configuration:**
- Default retries: 3 (via `--reruns 3` in CI)
- Retry delay: 2 seconds (via `--reruns-delay 2`)
- Tests can opt out with `@pytest.mark.no_rerun` for deterministic validations

### 5.2 Known Broken Endpoints (xfail)

**Problem:** Some endpoints exhibit data quality issues (float artifacts, crossed books) or missing functionality (GET /orders).

**Solution:** `@pytest.mark.xfail` with `strict=True` and finding ID references.

```python
@pytest.mark.xfail(
    reason="F-REST-001: Floating-point price artifacts in snapshot prices",
    strict=True,
)
@pytest.mark.finding
async def test_snapshot_prices_clean_decimals(snapshot_route):
    """Snapshot prices should be clean decimals without IEEE 754 artifacts."""
    from smfs_qa.validators import has_float_artifact
    data = await snapshot_route.get_snapshot_parsed()
    artifacts = [l.price for l in data.bids + data.asks if has_float_artifact(l.price)]
    assert len(artifacts) == 0, f"Found {len(artifacts)} float artifacts"
```

**Key rules:**
- Tests MUST assert the **correct expected behavior** (never assert the broken behavior as "correct")
- `strict=True` ensures that if the endpoint is fixed, the test will XPASS and force us to update the test
- Every xfail maps to a finding ID (e.g., `F-REST-001`)

### 5.3 Statistical Assertions for Non-Deterministic Data

**Problem:** WebSocket message rates, latencies, and Solana slot ordering are inherently variable.

**Solution:** Collect N samples and assert on statistical properties.

```python
async def test_ws_message_rate_within_tolerance(market_feed_route):
    """Collect messages for 30s, verify rate is at least 1 msg/s."""
    messages = await market_feed_route.collect_messages(duration=30.0)
    rate = len(messages) / 30.0
    assert rate >= 1.0, f"Message rate {rate:.2f}/s below 1.0/s threshold"
```

**Thresholds:**
- WebSocket message rate: >= 1 msg/s (conservative lower bound)
- Sequence gap rate: 0% (gaps indicate a bug, not non-determinism)
- Slot rollback rate: < 5% (reorgs are valid but rare on Solana)
- Latency assertions: Use percentiles (p50, p95, p99) not individual samples

### 5.4 Timing-Dependent Tests

**Problem:** Tests that wait for messages or connections can hang indefinitely without explicit timeouts.

**Solution:** Always use `asyncio.wait_for()` with explicit timeout values.

```python
async def test_receives_book_delta(market_feed_route):
    async with market_feed_route.connect() as ws:
        # Wait for hello
        hello = await asyncio.wait_for(ws.recv(), timeout=5.0)
        # Wait for first data message
        data = await asyncio.wait_for(ws.recv(), timeout=10.0)
        parsed = json.loads(data)
        assert parsed["type"] in ("book_delta", "trade")
```

**Timeout guidelines:**

| Operation | Timeout | Rationale |
|-----------|---------|-----------|
| HTTP request | 10s | REST endpoints should respond within seconds |
| WebSocket connect | 5s | TLS handshake + upgrade |
| WebSocket hello message | 5s | First message after connect |
| WebSocket data message | 10s | Depends on simulator update rate |
| Stream data collection | 30-60s | Meaningful statistical sample |
| Performance test run | 120s | Extended collection for percentiles |

---

## 6. xfail Strategy with Finding IDs

Each known finding has a unique ID following the pattern `F-{COMPONENT}-{NNN}`. Tests referencing findings use `@pytest.mark.xfail(reason="...", strict=True)` and are additionally tagged with `@pytest.mark.finding`.

### 6.1 REST API Findings

| Finding ID | Severity | Endpoint | Description | Affected Tests |
|-----------|----------|----------|-------------|----------------|
| **F-INFRA-001** | Medium | All REST | Cloudflare error 1010 — requests without `User-Agent` header return 403. Mitigated by adding `User-Agent: smfs-qa/1.0` to SMFSClient. | All REST tests |
| **F-REST-001** | Medium | `GET /markets/{marketId}/snapshot` | Floating-point price artifacts — prices like `66079.90000000001` instead of clean decimals. IEEE 754 representation issue. | test_snapshot_prices_clean_decimals |
| **F-REST-002** | Medium | `GET /markets/{marketId}/snapshot` | Crossed order book — best bid sometimes >= best ask, indicating data integrity issue in order book aggregation. | test_snapshot_book_not_crossed |
| **F-REST-004** | Low | All error responses | Error responses use `text/plain` Content-Type instead of `application/json`. Affects non-existent paths and some valid-path error cases. | test_error_content_type_is_json |

### 6.2 WebSocket Findings

| Finding ID | Severity | Endpoint | Description | Affected Tests |
|-----------|----------|----------|-------------|----------------|
| **F-WS-001** | Medium | `WS /ws?marketId={invalid}` | Invalid marketId silently accepted — connection succeeds, hello sent, but behavior is undefined. No error message returned for invalid markets. | test_invalid_market_id_rejected, test_missing_market_id_rejected |
| **F-WS-002** | Medium | `WS /ws` book_delta | IEEE 754 floating-point artifacts in order book delta prices. Same root cause as F-REST-001. | test_book_delta_prices_clean_decimals |
| **F-WS-003** | Medium | `WS /ws` trade | IEEE 754 floating-point artifacts in trade prices. Same root cause as F-REST-001 and F-WS-002. | test_trade_prices_clean_decimals |

### 6.3 Solana Stream Findings

| Finding ID | Severity | Endpoint | Description | Affected Tests |
|-----------|----------|----------|-------------|----------------|
| **F-SOL-001** | Medium | `WS /ws/stream` | Subscribe data delivery is intermittent (~60% success) with no acknowledgment from the server. Tested with 5 subscribe variants with 30-60s wait windows. | TC-SOL-012 |
| **F-SOL-002** | Medium | `WS /ws/stream` | Subscribe filter variants (multiple programs, empty array) have similarly intermittent delivery (~67% success). The stream connects and responds to pings, but subscribe data delivery is unreliable. | -- |

### 6.4 xfail Usage Pattern

```python
import pytest

@pytest.mark.finding
@pytest.mark.xfail(
    reason="F-REST-001: Floating-point price artifacts in snapshot prices",
    strict=True,
)
async def test_snapshot_prices_clean_decimals(snapshot_route):
    """Snapshot prices should be clean decimals without IEEE 754 artifacts."""
    from smfs_qa.validators import has_float_artifact
    data = await snapshot_route.get_snapshot_parsed()
    artifacts = [l.price for l in data.bids + data.asks if has_float_artifact(l.price)]
    assert len(artifacts) == 0
```

**Why `strict=True` matters:** If the API is fixed and the endpoint starts returning 200, the test will XPASS (unexpectedly pass), which `strict=True` treats as a failure. This forces the team to remove the xfail marker and update FINDINGS.md, ensuring the audit stays accurate.

---

## 7. Entry and Exit Criteria

### 7.1 Entry Criteria

All entry criteria must be satisfied before test execution begins.

| # | Criterion | Verification Method |
|---|-----------|-------------------|
| E1 | SMFS API is accessible at `https://interviews-api.sonic.game` | `GET /health` returns 200 |
| E2 | WebSocket endpoint is connectable | `wss://interviews-api.sonic.game/ws?marketId=BTC-PERP` accepts connection |
| E3 | Solana stream endpoint is connectable | `wss://interviews-api.sonic.game/ws/stream` accepts connection |
| E4 | Test framework is installed | `pytest --version` succeeds |
| E5 | All dependencies are installed | `pip install -e ".[test]"` succeeds |
| E6 | OpenAPI spec is cached | `docs/openapi.json` exists and is valid JSON |
| E7 | Test case blueprints are available | `docs/testcases/smfs-testcases-detail.md` exists |

### 7.2 Exit Criteria

The audit is complete when all exit criteria are met.

| # | Criterion | Evidence |
|---|-----------|----------|
| X1 | All P0 tests pass or are xfail'd with documented findings | `pytest` output shows 0 unexpected failures for P0 tests |
| X2 | All P1 tests are implemented and executed | Test count matches priority matrix |
| X3 | `FINDINGS.md` is produced with all required fields per finding | Document review |
| X4 | `PERFORMANCE.md` is produced with latency tables and throughput data | Document review |
| X5 | CI pipeline runs without crashes | GitHub Actions workflow completes |
| X6 | JUnit XML and Allure report artifacts are generated | Artifact upload in CI |
| X7 | All xfail tests have a corresponding finding ID in `FINDINGS.md` | Cross-reference check |
| X8 | No P0 test is left in a permanently broken state without documentation | Review of test results |

---

## 8. Test Environment

### 8.1 Target Service

| Property | Value |
|----------|-------|
| Base URL | `https://interviews-api.sonic.game` |
| WebSocket Market Feed URL | `wss://interviews-api.sonic.game/ws?marketId=BTC-PERP` |
| Solana Transaction Stream URL | `wss://interviews-api.sonic.game/ws/stream` |
| API Explorer | `https://interviews-api.sonic.game/docs` |
| Available Markets | `BTC-PERP` |
| Authentication | None (public API) |
| Protocol | HTTPS / WSS (TLS required) |

### 8.2 Test Infrastructure

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.11+ |
| Test runner | pytest | 8.x |
| Async support | pytest-asyncio | 0.23+ (auto mode) |
| Retry handling | pytest-rerunfailures | 14+ |
| Parallel execution | pytest-xdist | 3.x |
| HTTP client | httpx | 0.27+ (async, HTTP/2) |
| Retry logic | tenacity | 8.x (exponential backoff) |
| WebSocket client | websockets | 12+ (async) |
| Schema validation | pydantic | 2.x (strict mode) |
| Solana primitives | solders | 0.21+ (Base58, signatures) |
| Load testing | locust | 2.x |
| Reporting | allure-pytest | 2.x + JUnit XML |
| Statistics | numpy | 1.26+ (percentile calculations) |

### 8.3 Test Execution Modes

| Mode | Command | Description |
|------|---------|-------------|
| All tests | `make test` | Run full suite against live service |
| REST only | `pytest tests/rest/ -v` | REST API tests only |
| WebSocket only | `pytest tests/websocket/ -v` | WebSocket tests only |
| Solana only | `pytest tests/solana/ -v` | Solana stream tests only |
| Performance only | `pytest tests/performance/ -v` | Performance benchmarks only |
| With retries | `pytest --reruns 3 --reruns-delay 2` | CI-grade with retry tolerance |
| Load test | `make load-test` | Locust headless, 50 users, 120s |
| Stress test | `make stress-test` | Locust headless, 100 users, 120s |
| Locust UI | `make locust-ui` | Locust web UI on http://localhost:8089 |

### 8.4 Reports

| Report | Format | Location |
|--------|--------|----------|
| Console output | Text | stdout |
| JUnit XML | XML | `results/live.xml` |
| Allure results | JSON | `allure-results/` |
| Allure HTML report | HTML | `allure-report/` (generated from results) |

---

## 9. Test Architecture

### 9.1 Monorepo Package Structure

```
SonicSVM/
├── pyproject.toml                      # Root workspace config
├── conftest.py                         # Root fixtures: base_url, ws_base_url, route models
├── Makefile                            # Build and test automation
├── docs/
│   ├── openapi.json                    # Cached OpenAPI 3.1 spec (source of truth)
│   ├── assignment-spec.md              # Original assignment
│   └── testcases/
│       ├── smfs-testcases-detail.md    # Detailed test case blueprints
│       └── smfs-testcases-xmind.md     # XMind format test map
├── src/smfs_qa/                       # Shared test framework (pip-installable)
│   ├── client.py                      # SMFSClient (httpx + tenacity)
│   ├── ws_client.py                   # WSTestClient (websockets)
│   ├── schemas.py                     # Pydantic v2 strict response models
│   ├── solana.py                      # Base58, signature validation (solders)
│   ├── perf.py                        # LatencyTracker, Timer utilities
│   ├── logger.py                      # QALogger with Allure integration
│   ├── locustfile.py                  # Locust load test users
│   ├── routes/                        # POM Route Model (REST)
│   │   ├── health.py, markets.py, snapshot.py
│   │   ├── orders.py, stats.py
│   └── ws_routes/                     # POM Route Model (WebSocket)
│       ├── market_feed.py
│       └── solana_stream.py
├── tests/
│   ├── rest/                          # REST API tests (72 tests, 9 files)
│   │   ├── test_health.py
│   │   ├── test_markets.py
│   │   ├── test_snapshot.py           # xfail: F-REST-001, F-REST-002
│   │   ├── test_orders.py            # POST /orders validation + boundary tests
│   │   ├── test_stats.py
│   │   ├── test_error_format.py       # xfail: F-REST-004
│   │   ├── test_error_cases.py        # Boundary and injection tests
│   │   ├── test_docs_endpoints.py     # Documentation endpoint availability
│   │   └── test_method_not_allowed.py
│   ├── websocket/                     # WebSocket market feed tests (44 tests, 7 files)
│   │   ├── test_connection.py         # xfail: F-WS-001
│   │   ├── test_ping_pong.py
│   │   ├── test_book_delta.py         # xfail: F-WS-002
│   │   ├── test_trades.py             # xfail: F-WS-003
│   │   ├── test_sequence.py
│   │   ├── test_disconnect.py
│   │   └── test_reconnection.py
│   ├── solana/                        # Solana transaction stream tests (54 tests, 8 files)
│   │   ├── test_stream_connect.py
│   │   ├── test_stream_ping.py
│   │   ├── test_subscribe.py          # F-SOL-001 (partially resolved)
│   │   ├── test_subscribe_filters.py  # F-SOL-002 (partially resolved)
│   │   ├── test_stream_schema.py
│   │   ├── test_signature_validation.py
│   │   ├── test_reorg.py               # Reorg detection, rollback rate
│   │   └── test_slot_ordering.py       # Monotonic ordering, gap distribution
│   └── performance/                   # Performance tests (38 tests, 7 files)
│       ├── test_rest_latency.py       # xfail: F-PERF-001
│       ├── test_ws_throughput.py
│       ├── test_concurrent_ws.py
│       ├── test_burst.py
│       ├── test_latency_under_load.py # F-PERF-003 (tolerance test)
│       ├── test_orders_perf.py        # F-PERF-002 (tolerance test)
│       └── test_ws_advanced.py
├── locustfile.py                      # Locust load test definitions (symlink)
├── allure/
│   └── categories.json                # Allure failure categorization
└── .github/workflows/
    ├── smoke.yml                      # Fast CI gate for PRs/pushes
    ├── regression.yml                 # Full regression suite
    ├── performance.yml                # Performance benchmarks and load tests
    └── qa-analyze.yml                 # Automated failure analysis
```

### 9.2 POM Route Model Pattern

All endpoint interactions are encapsulated in Route Model classes, following the Page Object Model (POM) pattern adapted for APIs.

```
Test File                Route Model                   API
---------                -----------                   ---
test_health.py  ──>  HealthRoute.get()        ──>  GET /health
test_markets.py ──>  MarketsRoute.get()       ──>  GET /markets
test_sequence.py ──> MarketFeedRoute.connect() ──> WS /ws?marketId=...
```

**Benefits:**
- Endpoint paths are defined once in route models, not scattered across tests
- Request/response parsing logic is centralized and reusable
- If an endpoint path changes, only the route model needs updating
- Tests read as domain-level assertions, not HTTP mechanics

### 9.3 Shared Fixtures (Root conftest.py)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `base_url` | session | `https://interviews-api.sonic.game` |
| `ws_base_url` | session | `wss://interviews-api.sonic.game` |
| `api_client` | function | `SMFSClient` instance (httpx async, auto-closed) |
| `health_route` | function | `HealthRoute` bound to `api_client` |
| `markets_route` | function | `MarketsRoute` bound to `api_client` |
| `snapshot_route` | function | `SnapshotRoute` bound to `api_client` |
| `orders_route` | function | `OrdersRoute` bound to `api_client` |
| `stats_route` | function | `StatsRoute` bound to `api_client` |
| `market_feed_route` | function | `MarketFeedRoute` for WebSocket market feed |
| `solana_stream_route` | function | `SolanaStreamRoute` for Solana stream |

---

## 10. Test Coverage Matrix

### 10.1 REST API Coverage

| Endpoint | Method | Happy Path | Error Cases | Boundary | Schema | Finding |
|----------|--------|-----------|-------------|----------|--------|---------|
| `/health` | GET | TC-REST-001..007 | TC-REST-008..011 | TC-REST-012..015 | Pydantic strict | -- |
| `/markets` | GET | TC-REST-016..020 | -- | -- | Pydantic strict | -- |
| `/markets/{id}/snapshot` | GET | TC-REST-034 | TC-REST-036 | Injection, traversal | Pydantic strict | F-REST-001, F-REST-002 |
| `/orders` | POST | TC-REST-037 | Boundary, invalid params | Invalid side/type, zero size | Pydantic strict | -- |
| `/stats` | GET | TC-REST-025..031 | TC-REST-033 | -- | Pydantic strict | -- |
| Error format | All | -- | TC-REST-040 | -- | `{"error": "..."}` | F-REST-004 |

**Total REST tests:** 72 test cases across 9 test files.

### 10.2 WebSocket Market Feed Coverage

| Area | Test File | Test Cases | Priority |
|------|-----------|-----------|----------|
| Connection lifecycle | test_connection.py | Hello message, schema, marketId | P0 |
| Ping/pong keepalive | test_ping_pong.py | Send ping, receive pong with `ts` | P0 |
| Order book deltas | test_book_delta.py | Delta schema, bid/ask arrays | P0 |
| Trade messages | test_trades.py | Trade schema, side enum, tradeId | P0 |
| Sequence integrity | test_sequence.py | Monotonic, contiguous, 50+ messages | P0 |
| Disconnect handling | test_disconnect.py | Graceful close, reconnect | P0 |
| Reconnection | test_reconnection.py | Multiple connections, fresh hello | P0 |

**Total WebSocket tests:** 44 test cases across 7 test files.

### 10.3 Solana Transaction Stream Coverage

| Area | Test File | Test Cases | Priority | Finding |
|------|-----------|-----------|----------|---------|
| Connection | test_stream_connect.py | Stream hello, schema | P0 | -- |
| Ping/pong | test_stream_ping.py | Keepalive | P0 | -- |
| Subscribe | test_subscribe.py | Data delivery after subscribe | P0 | F-SOL-001 |
| Filters | test_subscribe_filters.py | Filter combinations | P0 | F-SOL-002 |
| Schema validation | test_stream_schema.py | Transaction model, slot ordering, fees | P0 | -- |
| Signature validation | test_signature_validation.py | Base58 charset, length (86-88), solders | P0 | -- |
| Reorg detection | test_reorg.py | Slot rollbacks, rollback rate (<5%), redelivery | P0 | -- |
| Slot ordering | test_slot_ordering.py | Monotonic slots, plausibility, gap distribution | P0 | -- |

**Total Solana tests:** 54 test cases across 8 test files (including reorg detection and slot ordering).

### 10.4 Integration (E2E) Coverage

| Test | Components | Priority |
|------|-----------|----------|
| Health wsUrl connects to WS | REST + WS | P0 |
| Markets marketId matches WS hello | REST + WS | P0 |
| Book delta ts monotonic | WS internal | P0 |
| Sequence contiguity E2E | WS internal | P0 |
| Stats seq correlates with WS seq | REST + WS | P1 |
| Stats rate correlates with WS rate | REST + WS | P1 |

### 10.5 Performance Coverage

| Metric | Endpoint | Threshold | Priority |
|--------|----------|-----------|----------|
| p50 latency | `GET /health` | < 200ms | P1 |
| p95 latency | `GET /health` | < 500ms | P1 |
| p99 latency | `GET /health` | < 1000ms | P1 |
| p50 latency | `GET /markets` | < 200ms | P1 |
| p95 latency | `GET /markets` | < 500ms | P1 |
| p50 latency | `GET /snapshot` | < 300ms | P1 |
| p95 latency | `GET /snapshot` | < 800ms | P1 |
| Throughput | WS market feed | >= 1 msg/s | P1 |
| Hello latency | WS market feed | < 2000ms | P1 |
| Concurrent connections | WS market feed | 5 simultaneous (100%) | P1 |
| Burst tolerance | REST endpoints | 20 req/100%, 50 req/95% | P1 |
| Locust SLA | All REST | p95 < 1000ms, error < 1% | P2 |

---

## 11. Performance Testing Strategy

### 11.1 Methodology

**Latency measurement:** Each REST endpoint is called N times sequentially (N=100 for benchmarks). Response times are collected and percentiles computed using `numpy.percentile()`. A 5-request warm-up period is excluded from calculations.

**Throughput measurement:** WebSocket connections are maintained for a fixed duration (30-60s). Total message count divided by duration gives messages/second. Only `book_delta` and `trade` messages are counted (excluding hello, pong).

**Concurrent connections:** Multiple WebSocket connections are opened simultaneously using `asyncio.gather()`. Success criterion is that all connections receive a `hello` message and at least one `book_delta` within the timeout window.

**Load testing:** Locust is used for sustained load generation against REST endpoints. Two profiles are defined:
- **Smoke test:** 50 users, 120s, SLA: p95 < 1000ms and error rate < 1%
- **Stress test:** 100 users, 120s, same SLA thresholds

### 11.2 SLA Thresholds

| Metric | Threshold | Source |
|--------|-----------|--------|
| REST p50 latency | < 200ms | Appropriate for lightweight JSON endpoints |
| REST p95 latency | < 500ms | Standard for API endpoints |
| REST p99 latency | < 1000ms | Upper bound before timeout |
| REST /snapshot p50 | < 300ms | Higher due to order book aggregation |
| REST /snapshot p95 | < 800ms | Higher due to order book aggregation |
| WS message rate | >= 1 msg/s | OpenAPI spec indicates ~10 book updates/s |
| WS hello latency | < 2000ms | Including TLS handshake + upgrade |
| WS connection success | 100% for 5, 90% for 10 | Scaling requirement |
| Burst 20 success rate | 100% | No rate limiting at low burst levels |
| Burst 50 success rate | >= 95% | Tolerance for higher concurrency |
| Locust p95 | < 1000ms | SLA compliance threshold |
| Locust error rate | < 1% | Service reliability minimum |

### 11.3 Tools

| Tool | Purpose | Integration |
|------|---------|-------------|
| `LatencyTracker` (smfs_qa) | Percentile computation for pytest benchmarks | `tests/performance/` |
| `numpy` | Statistical percentile functions | Used by LatencyTracker |
| `locust` | Sustained HTTP load generation | `locustfile.py` at project root |
| `allure` | Performance data attached to test reports | Allure attachments with latency tables |

---

## 12. Reporting

### 12.1 Allure Report Structure

Tests are decorated with Allure metadata for structured reporting:

| Decorator | Usage |
|-----------|-------|
| `@allure.epic("SMFS Quality Audit")` | Top-level grouping |
| `@allure.feature("REST API")` | Component grouping: REST, WebSocket, Solana, Performance |
| `@allure.story("Health Check")` | Feature-level grouping within component |
| `@allure.severity(CRITICAL)` | P0 = CRITICAL, P1 = NORMAL, P2 = MINOR |
| `@allure.tag("rest", "schema")` | Cross-cutting tags for filtering |

### 12.2 Failure Categorization

Allure categories (defined in `allure/categories.json`) classify failures:

| Category | Trigger |
|----------|---------|
| Schema Violations | `validation error` in failure message |
| Timeout Failures | `timeout` in failure message |
| Network Errors | `ConnectionRefused` in failure message |
| Sequence Integrity | `sequence.*gap` in failure message |

### 12.3 CI Artifacts

Each workflow uploads downloadable artifacts to the GitHub Actions run page:

| Workflow | Artifact Name | Contents | Format |
|----------|--------------|----------|--------|
| Smoke | `smoke-results` | `results/smoke.xml` | JUnit XML |
| Smoke | `allure-report-smoke` | Allure HTML report (smoke tests) | HTML |
| Regression | `regression-results` | `results/rest.xml`, `websocket.xml`, `solana.xml` | JUnit XML |
| Regression | `allure-report` | Allure HTML report (full regression) | HTML |
| Performance | `perf-benchmark-results` | `results/perf-benchmark.xml` | JUnit XML |
| Performance | `allure-report-perf` | Allure HTML report (pytest benchmarks) | HTML |
| Performance | `locust-results` | `locust-report.html`, `locust_stats.csv`, `locust_failures.csv` | HTML + CSV |

To view Allure HTML reports after downloading, serve them via a local HTTP server (Allure requires HTTP, not `file://`):

```bash
cd allure-report && python3 -m http.server 8080
# Open http://localhost:8080
```

---

## 13. Schedule and Dependencies

### 13.1 Phase Dependencies

```
Phase 0 (Setup)
    |
    v
Phase 0.5 (Test Case Generation)
    |
    v
Phase 1 (Strategy) -----> THIS DOCUMENT (TEST_PLAN.md)
    |
    v
Phase 2 (Implementation) --> REST, WebSocket, Solana, Performance agents (parallel)
    |
    v
Phase 3 (Analysis) --> FINDINGS.md
    |
    v
Phase 4 (Assembly) --> README.md, CI pipelines, final review
```

### 13.2 Agent Dependencies

| Agent | Depends On | Produces |
|-------|-----------|----------|
| Strategy Architect | OpenAPI spec, test case blueprints | TEST_PLAN.md |
| REST Engineer | TEST_PLAN.md, smfs_qa package | `tests/rest/` |
| WebSocket Engineer | TEST_PLAN.md, smfs_qa package | `tests/websocket/` |
| Solana Engineer | TEST_PLAN.md, smfs_qa package | `tests/solana/` |
| Performance Engineer | TEST_PLAN.md, smfs_qa package | `tests/performance/`, PERFORMANCE.md |
| Findings Analyst | All test results | FINDINGS.md |
| Code Reviewer | All test packages | Review feedback |
| QA Lead | All deliverables | README.md, CI pipelines, quality gates |

### 13.3 Shared Resources

| Resource | Owner | Consumers |
|----------|-------|-----------|
| `src/smfs_qa/` | QA Lead | All test agents |
| `src/smfs_qa/schemas.py` | Authoritative (first writer) | All agents (read-only after creation) |
| `docs/openapi.json` | QA Lead | All agents |
| Root `conftest.py` | QA Lead | All test packages |
| Root `pyproject.toml` | QA Lead | All agents |

---

## Appendix A: OpenAPI Endpoint Summary

| Endpoint | Method | Response Schema | Status |
|----------|--------|----------------|--------|
| `/health` | GET | `{ok: bool, serverTime: number, markets: string[], wsUrl: string}` | Working |
| `/markets` | GET | `{markets: [{marketId: string, base: string, quote: string}]}` | Working |
| `/markets/{id}/snapshot` | GET | `{marketId, ts, midPrice, bids, asks, recentTrades}` | Working — F-REST-001 (float artifacts), F-REST-002 (crossed book) |
| `/orders` | POST | `{accepted: bool, orderId: string, ts: number}` | Working (POST); GET returns 404 as expected (only POST documented) |
| `/stats` | GET | `{markets: {BTC-PERP: {bookUpdatesPerSecond, tradesPerSecond, currentSeq}, SOL-PERP: {...}}, connectedClients}` | Working (schema updated 2026-03-16) |

## Appendix B: WebSocket Message Schema Summary

| Message Type | Fields | Direction |
|-------------|--------|-----------|
| `hello` | `type, serverTime, marketId` | Server -> Client |
| `book_delta` | `type, ts, seq, bids[], asks[]` | Server -> Client |
| `trade` | `type, ts, tradeId, price, size, side` | Server -> Client |
| `pong` | `type, ts` | Server -> Client |
| `reset` | `type, reason, ts` | Server -> Client |
| `ping` | `type` | Client -> Server |

## Appendix C: Solana Domain Concepts

| Concept | Description | Testing Implication |
|---------|-------------|-------------------|
| **Slot** | Time unit on Solana (~400ms); sequential but gaps are normal | Assert generally increasing order; tolerate gaps between consecutive slots |
| **Signature** | Base58-encoded transaction identifier; 86-88 characters; charset: `123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz` | Validate format with `solders` library; test boundary lengths |
| **Program ID** | Base58-encoded address of the smart contract that processed a transaction | Validate Base58 format; may be used as subscription filter |
| **Reorg** | Rollback of recent blocks; transactions from rolled-back slots may be re-delivered | Statistical assertion: rollback rate < 5%; detect via slot number regression |
| **blockTime** | Unix timestamp in seconds; may be `null` for unconfirmed slots | Schema must accept `Optional[int]`; null is valid for recent slots |
| **Lamports** | Smallest SOL unit; 1 SOL = 1,000,000,000 lamports; fees are in lamports | Validate fee >= 0; reject negative values in schema |
| **Fee** | Transaction fee in lamports; minimum is 5000 lamports (one signature) | Assert fee >= 5000 for single-signature transactions |
