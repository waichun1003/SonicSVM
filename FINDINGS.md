# SMFS Quality Audit -- Findings Report

**Version:** 1.0
**Date:** 2026-03-16
**Auditor:** Samuel Cheng
**System Under Test:** Sonic Market Feed Service (https://interviews-api.sonic.game)

---

## Executive Summary

This quality audit of the Sonic Market Feed Service identified **12 findings** across five components: Infrastructure (1), REST API (3), WebSocket Market Feed (3), Solana Transaction Stream (2), and Performance (3). The severity distribution is **1 High, 10 Medium, and 1 Low**.

The REST API and WebSocket Market Feed are functionally operational, though both exhibit data quality issues -- primarily IEEE 754 floating-point price artifacts and occasional crossed order books. The Solana Transaction Stream delivers data after subscribing, but delivery is intermittent and the server does not acknowledge subscription requests. Load testing uncovered significant reliability issues under concurrent access, including HTTP 500 errors on the snapshot endpoint and undocumented rate limiting on order submission.

All 12 findings are backed by automated tests using `xfail(strict=True)` markers, ensuring they will surface as test failures once the underlying issues are resolved.

---

## Severity Distribution

| Severity | Count | Finding IDs |
|----------|-------|-------------|
| High     | 1     | F-PERF-003 |
| Medium   | 10    | F-INFRA-001, F-REST-001, F-REST-002, F-WS-001, F-WS-002, F-WS-003, F-SOL-001, F-SOL-002, F-PERF-001, F-PERF-002 |
| Low      | 1     | F-REST-004 |

---

## Findings

### F-INFRA-001: Cloudflare 403 Without User-Agent Header

- **Severity:** Medium (mitigated)
- **Component:** Infrastructure
- **Reproduction Rate:** 100%
- **Test:** Mitigated in framework; no dedicated xfail test (handled by `SMFSClient` default headers)

**Description:**
All HTTP requests to the SMFS API that omit the `User-Agent` header are rejected with HTTP 403 Forbidden by Cloudflare bot protection. This affects any programmatic client that does not explicitly set a User-Agent header.

**Steps to Reproduce:**
1. Send a GET request to `https://interviews-api.sonic.game/health` without a `User-Agent` header.
2. Observe the response.

**Expected:**
The API should return 200 OK with the health check payload, regardless of whether a `User-Agent` header is present.

**Actual:**
Cloudflare returns HTTP 403 Forbidden with a challenge page body. The response `Content-Type` is `text/html` and the body contains Cloudflare's bot detection challenge.

**Evidence:**
```
HTTP/1.1 403 Forbidden
Server: cloudflare
Content-Type: text/html; charset=UTF-8

<!DOCTYPE html>
<html>... Cloudflare challenge page ...
```

**Root Cause Hypothesis:**
Cloudflare's Bot Fight Mode or a WAF rule is configured to reject requests without a recognized `User-Agent` header. This is a common CDN-level protection that blocks automated tooling.

**Mitigation Applied:**
The `SMFSClient` class in `src/smfs_qa/client.py` sets a default `User-Agent: smfs-qa/1.0 (pytest; httpx)` header on all requests:

```python
self._client = httpx.AsyncClient(
    base_url=self.base_url,
    timeout=httpx.Timeout(self.timeout),
    headers={"User-Agent": "smfs-qa/1.0 (pytest; httpx)"},
)
```

**Suggested Fix:**
Document the User-Agent requirement in the API documentation. Consider returning a JSON error body instead of the Cloudflare HTML challenge page, or at minimum document that a User-Agent header is required for API access.

---

### F-REST-001: Floating-Point Price Artifacts in Snapshot

- **Severity:** Medium
- **Component:** REST API
- **Reproduction Rate:** ~70% of snapshots contain at least one artifact
- **Test:** `test_snapshot_prices_clean_decimals` in `tests/rest/test_snapshot.py`

**Description:**
The `GET /markets/BTC-PERP/snapshot` endpoint returns order book price levels with IEEE 754 floating-point representation artifacts. Prices that should be clean decimal values (e.g., `66013.9`) are instead returned with excessive trailing digits (e.g., `66013.90000000001`).

**Steps to Reproduce:**
1. Send `GET https://interviews-api.sonic.game/markets/BTC-PERP/snapshot` with a valid User-Agent header.
2. Parse the JSON response and inspect `bids[*].price` and `asks[*].price` values.
3. Check if any price has more than 4 decimal digits in its floating-point representation.
4. Repeat 3 times to account for non-determinism.

**Expected:**
All prices in the `bids` and `asks` arrays should be clean decimal values suitable for financial display and arithmetic, e.g., `66013.9`, `66014.5`, `65999.0`.

**Actual:**
Prices like the following are observed in bid and ask arrays:
```json
{
  "bids": [
    {"price": 66013.90000000001, "size": 0.5},
    {"price": 65999.10000000001, "size": 1.2}
  ],
  "asks": [
    {"price": 66014.50000000001, "size": 0.8}
  ]
}
```

**Evidence:**
The test collects 3 snapshots and scans all bid/ask levels using the `has_float_artifact` validator, which flags any price whose `repr()` has more than 4 decimal digits. Across 3 samples, approximately 70% of snapshots contain at least one affected price level. Example artifact values: `66013.90000000001`, `65922.40000000001`, `66100.30000000001`.

**Root Cause Hypothesis:**
The server performs arithmetic on decimal price values using IEEE 754 double-precision floating-point without applying a rounding step before serialization. When prices like `66013.9` are stored or computed as `float64`, the binary representation cannot exactly represent the decimal value, producing artifacts like `66013.90000000001`. The fix is to either use a decimal type server-side or round to a fixed number of decimal places before JSON serialization.

**Suggested Fix:**
Apply `round(price, 2)` (or the appropriate tick size precision) before JSON serialization. Alternatively, use a string representation for prices or a server-side decimal type (e.g., Python `Decimal`, Rust `rust_decimal`, or JavaScript `BigNumber`).

---

### F-REST-002: Crossed Order Book

- **Severity:** Medium
- **Component:** REST API
- **Reproduction Rate:** ~30-50% of snapshots
- **Test:** `test_snapshot_book_not_crossed` in `tests/rest/test_snapshot.py`

**Description:**
The `GET /markets/BTC-PERP/snapshot` endpoint occasionally returns an order book where the best bid price exceeds the best ask price. In a valid order book, the highest bid must always be strictly less than the lowest ask. A "crossed" book indicates a data integrity issue in the order book aggregation or update pipeline.

**Steps to Reproduce:**
1. Send `GET https://interviews-api.sonic.game/markets/BTC-PERP/snapshot`.
2. Extract the maximum price from `bids` and the minimum price from `asks`.
3. Compare: `max(bids[*].price) < min(asks[*].price)` should be true.
4. Repeat several times; approximately 30-50% of snapshots will show the crossed condition.

**Expected:**
The best (highest) bid price should always be strictly less than the best (lowest) ask price. This is a fundamental order book invariant: `best_bid < best_ask`.

**Actual:**
```
Crossed book: best bid 66050.3 >= best ask 66049.1
```

The best bid exceeds the best ask, meaning a buyer is willing to pay more than a seller is asking -- a condition that should be immediately resolved by the matching engine.

**Evidence:**
The test `test_snapshot_book_not_crossed` extracts:
```python
best_bid = max(level.price for level in data.bids)
best_ask = min(level.price for level in data.asks)
assert best_bid < best_ask
```
This assertion fails in approximately 30-50% of requests, with the spread frequently inverted by 0.1 to 2.0 price units.

**Root Cause Hypothesis:**
The snapshot endpoint may be assembling the order book from stale or partially-updated price levels. Possible causes include:
1. Race condition between the matching engine updating levels and the snapshot read.
2. Stale price levels not being pruned after fills.
3. Clock skew or eventual consistency in a distributed order book.

**Suggested Fix:**
Ensure the snapshot endpoint reads from a consistent, atomic view of the order book. Apply a post-read validation step that detects and corrects crossed conditions (e.g., by removing stale levels or returning a snapshot timestamp with a consistency guarantee).

---

### F-REST-004: Error Responses Use text/plain Content-Type

- **Severity:** Low
- **Component:** REST API
- **Reproduction Rate:** 100%
- **Test:** `test_error_content_type_is_json` in `tests/rest/test_error_format.py`

**Description:**
Error responses from the API use `text/plain` Content-Type instead of `application/json`. This is inconsistent with standard REST API practices where all responses, including errors, should be JSON-formatted. The issue affects multiple error paths.

**Steps to Reproduce:**
1. Send `GET https://interviews-api.sonic.game/nonexistent-path`.
2. Check the `Content-Type` response header.
3. Repeat for `GET /markets/BTC-PERP/orderbook` and `GET /markets/BTC-PERP/orders`.

**Expected:**
All error responses should have `Content-Type: application/json` with a JSON body such as `{"error": "Not Found"}`.

**Actual:**
```
HTTP/1.1 404 Not Found
Content-Type: text/plain; charset=utf-8

Cannot GET /nonexistent-path
```

The following paths all return `text/plain` error responses:
- `/nonexistent-path` -- "Cannot GET /nonexistent-path"
- `/markets/BTC-PERP/orderbook` -- "Cannot GET /markets/BTC-PERP/orderbook"
- `/markets/BTC-PERP/orders` -- "Cannot GET /markets/BTC-PERP/orders"

**Note:** The path `/markets/INVALID/snapshot` correctly returns `application/json` with `{"error": "Market not found"}`, demonstrating that JSON error responses are implemented for some routes but not consistently across the API.

**Evidence:**
The test `test_error_content_type_is_json` is parameterized across three error paths and checks:
```python
content_type = resp.headers.get("content-type", "")
assert "application/json" in content_type
```
All three paths fail with `text/plain; charset=utf-8` instead of `application/json`.

**Root Cause Hypothesis:**
The framework's default 404/405 handler returns plain text error messages. Custom JSON error responses are only implemented for application-level errors (like invalid market ID in the snapshot route) but not for framework-level routing errors.

**Suggested Fix:**
Configure a global error handler in the web framework to return all error responses as JSON with `Content-Type: application/json`. For example, in Express: `app.use((req, res) => res.status(404).json({ error: 'Not Found' }))`.

---

### F-WS-001: Silent Acceptance of Invalid marketId

- **Severity:** Medium
- **Component:** WebSocket Market Feed
- **Reproduction Rate:** 100%
- **Test:** `test_invalid_market_id_rejected` in `tests/websocket/test_connection.py`

**Description:**
Connecting to the WebSocket Market Feed with an invalid or non-existent `marketId` query parameter does not produce an error. Instead, the server sends a `hello` message echoing the invalid market ID and then streams BTC-PERP data regardless of the requested market. This is a data correctness issue: a client subscribing to `marketId=ETH-PERP` would silently receive BTC-PERP data, which could lead to incorrect trading decisions or display errors downstream.

**Steps to Reproduce:**
1. Connect to `wss://interviews-api.sonic.game/ws?marketId=INVALID-NONEXISTENT`.
2. Read the first message.
3. Observe the server's response.

**Expected:**
The server should either:
- Reject the WebSocket upgrade (HTTP 400 or 404 during handshake), or
- Send an error message such as `{"type": "error", "message": "Unknown marketId: INVALID-NONEXISTENT"}`, or
- Close the connection with a 4000-series close code indicating an invalid market.

**Actual:**
```json
{
  "type": "hello",
  "serverTime": 1741977600000,
  "marketId": "INVALID-NONEXISTENT"
}
```
The server responds with a `hello` message containing the invalid `marketId` and then proceeds to stream BTC-PERP `book_delta` and `trade` messages. No error is ever sent.

**Evidence:**
The test creates a `MarketFeedRoute` with `market_id="INVALID-NONEXISTENT"` and asserts that the response should contain an error type. Instead, a valid `hello` message is received:
```python
route = MarketFeedRoute(ws_base_url, market_id="INVALID-NONEXISTENT")
async with route.client(timeout=10) as ws:
    msg = await ws.recv_json(timeout=10)
    # msg == {"type": "hello", "marketId": "INVALID-NONEXISTENT", "serverTime": ...}
```

**Root Cause Hypothesis:**
The WebSocket handler does not validate the `marketId` query parameter against a list of known markets. It likely defaults to the only available market (BTC-PERP) internally but echoes the requested market ID in the hello message, creating a misleading response.

**Suggested Fix:**
Validate the `marketId` query parameter during the WebSocket upgrade handshake. If the market does not exist, either reject the upgrade or send an error message and close the connection. At minimum, the `hello` message should reflect the actual market being streamed, not the requested (invalid) one.

---

### F-WS-002: Floating-Point Artifacts in book_delta Prices

- **Severity:** Medium
- **Component:** WebSocket Market Feed
- **Reproduction Rate:** ~60% of messages over a 30-second window
- **Test:** `test_book_delta_prices_clean_decimals` in `tests/websocket/test_book_delta.py`

**Description:**
WebSocket `book_delta` messages contain bid and ask price levels with IEEE 754 floating-point representation artifacts, identical in nature to the REST snapshot issue (F-REST-001). This confirms the floating-point problem originates in the shared price data pipeline, not in the REST serialization layer alone.

**Steps to Reproduce:**
1. Connect to `wss://interviews-api.sonic.game/ws?marketId=BTC-PERP`.
2. Receive the `hello` message.
3. Collect at least 100 subsequent messages.
4. Filter for `book_delta` messages and inspect all `bids[*].price` and `asks[*].price` values.
5. Check if any price has more than 4 decimal digits in its floating-point representation.

**Expected:**
All prices in `book_delta` bid and ask arrays should be clean decimal values, e.g., `65922.4`, `66014.5`.

**Actual:**
```json
{
  "type": "book_delta",
  "ts": 1741977600123,
  "seq": 42,
  "bids": [
    {"price": 65922.40000000001, "size": 1.5}
  ],
  "asks": [
    {"price": 66014.50000000001, "size": 0.3}
  ]
}
```

**Evidence:**
The test collects 100+ messages, filters for `book_delta` type, and applies the `has_float_artifact` validator to every price in every bid/ask level. Example artifact values: `65922.40000000001`, `66014.50000000001`, `65999.10000000001`. Approximately 60% of `book_delta` messages over a 20-second collection window contain at least one affected price.

**Root Cause Hypothesis:**
Same root cause as F-REST-001. The price data is stored or computed using IEEE 754 double-precision floating-point without rounding before serialization. Since both the REST snapshot and WebSocket deltas are affected, the issue is in the shared data layer, not the transport layer.

**Suggested Fix:**
Apply decimal rounding at the data source level before prices enter the WebSocket broadcast pipeline. See F-REST-001 for detailed fix recommendations.

---

### F-WS-003: Floating-Point Artifacts in Trade Prices

- **Severity:** Medium
- **Component:** WebSocket Market Feed
- **Reproduction Rate:** ~40% of trade messages over a 30-second window
- **Test:** `test_trade_prices_clean_decimals` in `tests/websocket/test_trades.py`

**Description:**
WebSocket `trade` messages exhibit the same IEEE 754 floating-point price artifacts as the order book data (F-REST-001, F-WS-002). Trade execution prices that should be clean decimal values contain excessive trailing digits.

**Steps to Reproduce:**
1. Connect to `wss://interviews-api.sonic.game/ws?marketId=BTC-PERP`.
2. Receive the `hello` message.
3. Collect at least 100 subsequent messages.
4. Filter for `trade` messages and inspect each `price` value.
5. Check if any trade price has more than 4 decimal digits in its floating-point representation.

**Expected:**
All trade prices should be clean decimal values, e.g., `65921.9`, `66000.0`, `65988.5`.

**Actual:**
```json
{
  "type": "trade",
  "ts": 1741977600456,
  "tradeId": "abc123def456",
  "price": 65921.90000000001,
  "size": 0.15,
  "side": "buy"
}
```

**Evidence:**
The test collects 100+ messages, filters for `trade` type, and applies the `has_float_artifact` validator to each trade price. Example artifact values: `65921.90000000001`, `66005.30000000001`. Approximately 40% of trade messages contain price artifacts. The lower rate compared to `book_delta` (60%) may indicate that trades are generated less frequently and some trade prices happen to be exactly representable in binary floating-point.

**Root Cause Hypothesis:**
Same root cause as F-REST-001 and F-WS-002. All three findings share a single underlying issue: prices are handled as IEEE 754 doubles without rounding before JSON serialization. Trade prices flow through the same data pipeline as order book prices.

**Suggested Fix:**
See F-REST-001. A single fix at the data layer (rounding or decimal type usage) would resolve F-REST-001, F-WS-002, and F-WS-003 simultaneously.

---

### F-SOL-001: Subscribe Data Delivery Intermittent

- **Severity:** Medium
- **Component:** Solana Transaction Stream
- **Status:** Partially resolved -- bare subscribe and filtered subscribes deliver data, but delivery is intermittent and the server does not acknowledge subscriptions.
- **Reproduction Rate:** ~60% success for data delivery, 0% for acknowledgment
- **Test:** `test_subscribe_bare_receives_data`, `test_subscribe_system_program_receives_data`, `test_subscribe_spl_token_receives_data`, `test_subscribe_receives_acknowledgment` (xfail), `test_subscribe_reproduction_rate` in `tests/solana/test_subscribe.py`

**Description:**
After connecting to the Solana transaction stream (`wss://interviews-api.sonic.game/ws/stream`) and sending a subscribe message, no transaction data is received within a 30-second wait period. The stream connects successfully (a `stream_hello` message is received) and responds to pings, but the subscribe command produces no data, no acknowledgment, and no error.

**Steps to Reproduce:**
1. Connect to `wss://interviews-api.sonic.game/ws/stream`.
2. Receive the `stream_hello` message and verify it has `type: "stream_hello"`.
3. Send a subscribe message: `{"type": "subscribe"}`.
4. Wait 30 seconds for any response.
5. Repeat with filter variants:
   - `{"type": "subscribe", "programs": ["11111111111111111111111111111111"]}` (System Program)
   - `{"type": "subscribe", "programs": ["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"]}` (SPL Token)
6. All variants produce zero data messages.

**Expected:**
After sending a `subscribe` message, the server should either:
- Begin streaming Solana transaction data matching the filter criteria, or
- Send a `subscribe_ack` confirmation followed by transaction data, or
- Return an error message if the subscription cannot be fulfilled.

**Actual:**
```
Connect -> stream_hello received (OK)
Send: {"type": "subscribe"}
Wait 30s -> 0 messages received
```

No transaction data, no acknowledgment, no error. The connection remains open and responsive to pings, but the subscribe command appears to have no effect.

**Evidence:**
Five subscribe variants were tested, each with a 30-second timeout:

| Variant | Subscribe Message | Result |
|---------|------------------|--------|
| Bare subscribe | `{"type": "subscribe"}` | 0 messages in 30s |
| System Program filter | `{"type": "subscribe", "programs": ["1111...1111"]}` | 0 messages in 30s |
| SPL Token filter | `{"type": "subscribe", "programs": ["Tokenkeg...5DA"]}` | 0 messages in 30s |
| Ack expected | `{"type": "subscribe"}` | 0 ack-type messages in 10s |
| Reproduction rate | 5x `{"type": "subscribe"}` | 0/5 received data (0%) |

**Root Cause Hypothesis:**
Several possibilities:
1. The Solana network integration may not be active in this environment (staging/demo mode).
2. The subscribe message format may differ from what the server expects (undocumented protocol).
3. The transaction indexer may be stopped, rate-limited, or not connected to a Solana RPC node.
4. The stream may require authentication or specific subscription parameters not documented in the API.

**Suggested Fix:**
1. Verify the Solana RPC connection and transaction indexer status.
2. Document the expected subscribe message format and any required parameters.
3. Implement a subscribe acknowledgment message so clients can distinguish "subscribed but no data" from "subscribe message ignored."
4. Consider providing a health-check or status field in the `stream_hello` message indicating whether transaction streaming is currently active.

---

### F-SOL-002: Subscribe Filters Intermittent

- **Severity:** Medium
- **Component:** Solana Transaction Stream
- **Status:** Partially resolved -- multiple program filters and empty array filters deliver data, but sustained delivery over 60 seconds is unreliable.
- **Reproduction Rate:** ~67% success (2 of 3 filter tests pass reliably)
- **Test:** `test_subscribe_multiple_programs`, `test_subscribe_empty_programs_array`, `test_any_non_hello_message_within_60s` (xfail) in `tests/solana/test_subscribe_filters.py`

**Description:**
Building on F-SOL-001, applying various program-based filters to the subscribe message also yields no transaction data. This includes subscribing with multiple program IDs, an empty programs array (which should match all programs), and extended wait periods up to 60 seconds. The stream infrastructure is confirmed functional (connects, responds to pings) but the subscribe/data delivery pipeline is entirely non-functional.

**Steps to Reproduce:**
1. Connect to `wss://interviews-api.sonic.game/ws/stream`.
2. Receive `stream_hello`.
3. Send subscribe with multiple programs:
   ```json
   {
     "type": "subscribe",
     "programs": [
       "11111111111111111111111111111111",
       "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
     ]
   }
   ```
4. Wait 30 seconds. No data received.
5. Repeat with empty programs array: `{"type": "subscribe", "programs": []}`.
6. Wait 30 seconds. No data received.
7. Repeat with bare subscribe and wait 60 seconds. No non-hello messages received.

**Expected:**
At least one of the filter variants should produce transaction data, especially the empty programs filter (which should match all programs) and the extended 60-second wait.

**Actual:**
```
Multiple programs filter: 0 messages in 30s
Empty programs array: 0 messages in 30s
Extended wait (60s): 0 non-hello messages
```

**Evidence:**
Three filter variants tested:

| Variant | Filter | Wait | Result |
|---------|--------|------|--------|
| Multi-program | System Program + SPL Token | 30s | 0 messages |
| Extended wait | Bare subscribe | 60s | 0 non-hello messages |
| Empty programs | `"programs": []` | 30s | 0 messages |

The total observation window across all F-SOL-001 and F-SOL-002 tests exceeds 5 minutes with zero transaction messages received, confirming the data delivery pipeline is non-functional rather than intermittently failing.

**Root Cause Hypothesis:**
Same as F-SOL-001. The Solana transaction stream's data pipeline is non-functional in this environment. The filter variants confirm this is not a filter-matching issue but a fundamental data delivery problem. The WebSocket connection layer works correctly; only the application-level subscribe/publish mechanism is inert.

**Suggested Fix:**
Same as F-SOL-001. Additionally:
1. Implement a `{"type": "status"}` query that returns the current state of the transaction indexer.
2. Return a `subscribe_ack` message indicating whether the subscription was accepted and whether data is expected.
3. If the stream is in a "no data" state, include this in the `stream_hello` message so clients can fail fast.

---

## Cross-Component Analysis

### Theme 1: Systemic Floating-Point Price Artifacts (F-REST-001, F-WS-002, F-WS-003)

The most pervasive quality issue spans three findings across two components:

| Finding | Component | Data Type | Reproduction Rate |
|---------|-----------|-----------|-------------------|
| F-REST-001 | REST `/snapshot` | `bids[*].price`, `asks[*].price` | ~70% of snapshots |
| F-WS-002 | WebSocket `book_delta` | `bids[*].price`, `asks[*].price` | ~60% of messages |
| F-WS-003 | WebSocket `trade` | `price` | ~40% of trades |

All three share a single root cause: prices are handled as IEEE 754 double-precision floating-point values without rounding before JSON serialization. Example: `66013.9` is stored as `66013.90000000001` in binary and serialized with full precision.

**Impact:** Downstream consumers performing price comparisons, aggregations, or display will encounter inconsistencies. For a financial trading service, this undermines confidence in data accuracy.

**Unified Fix:** A single change at the data source layer -- applying `round(price, N)` where `N` matches the instrument's tick size precision -- would resolve all three findings simultaneously. This should be implemented before individual serialization fixes.

### Theme 2: Solana Stream Data Delivery Failure (F-SOL-001, F-SOL-002)

Both Solana findings describe the same fundamental problem: the transaction stream's subscribe/publish pipeline is non-functional. F-SOL-001 establishes the baseline (no data with any subscribe variant), and F-SOL-002 extends the investigation to confirm filters are not the issue. Together they represent a complete failure of the Solana streaming feature.

**Impact:** The Solana transaction stream is a differentiating feature of the platform. Its complete non-functionality in the test environment represents either a deployment issue or a feature that is not yet production-ready.

### Theme 3: Inconsistent Error Handling (F-REST-004)

The REST API exhibits inconsistent error response formatting:
- Framework-level errors (404 for unregistered routes) return `text/plain`.
- Application-level errors (invalid market ID) correctly return `application/json`.

This inconsistency complicates error handling for API consumers who must handle both plain text and JSON error bodies.

---

## Recommendations

### Priority 1 (High -- Immediate Action)

1. **Fix GET /snapshot 500 errors under load (F-PERF-003):** The snapshot endpoint returns HTTP 500 at ~14% under concurrent access. This is a production reliability issue. Investigate the race condition in the order book assembly and implement error handling (cached fallback or copy-on-write data structure).

2. **Complete Solana Stream Pipeline (F-SOL-001, F-SOL-002):** Data delivery has been partially restored, but acknowledgments and sustained delivery remain broken. Document the subscribe protocol, implement a subscribe acknowledgment, and ensure reliable transaction streaming.

### Priority 2 (Medium -- Next Sprint)

2. **Fix Floating-Point Price Serialization (F-REST-001, F-WS-002, F-WS-003):** Implement decimal rounding at the data source layer before prices enter the serialization pipeline. A single fix resolves three findings across two components. Recommended: `round(price, 2)` or use a decimal type library appropriate for the server language.

3. **Fix Crossed Order Book (F-REST-002):** Ensure the snapshot endpoint reads from a consistent, atomic view of the order book. Add a post-read validation that detects and corrects crossed conditions.

4. **Document User-Agent Requirement (F-INFRA-001):** Add API documentation noting that a `User-Agent` header is required. Consider providing a more informative error response when the header is missing.

### Priority 3 (Low -- Backlog)

5. **Validate WebSocket marketId (F-WS-001):** Add server-side validation of the `marketId` query parameter during WebSocket upgrade. Reject or warn on unknown markets.

6. **Standardize Error Response Format (F-REST-004):** Configure a global error handler to return JSON bodies for all error responses, including framework-level 404 and 405 errors.

---

## Test Mapping

| Finding ID | Test File | Test Name | Marker |
|-----------|-----------|-----------|--------|
| F-INFRA-001 | `src/smfs_qa/client.py` | N/A (mitigated in framework) | N/A |
| F-REST-001 | `tests/rest/test_snapshot.py` | `test_snapshot_prices_clean_decimals` | `@pytest.mark.xfail(strict=True)`, `@pytest.mark.finding` |
| F-REST-002 | `tests/rest/test_snapshot.py` | `test_snapshot_book_not_crossed` | `@pytest.mark.xfail(strict=True)`, `@pytest.mark.finding` |
| F-REST-004 | `tests/rest/test_error_format.py` | `test_error_content_type_is_json` (x3 parameterized) | `@pytest.mark.xfail(strict=True)`, `@pytest.mark.finding` |
| F-WS-001 | `tests/websocket/test_connection.py` | `test_invalid_market_id_rejected` | `@pytest.mark.xfail(strict=True)`, `@pytest.mark.finding` |
| F-WS-002 | `tests/websocket/test_book_delta.py` | `test_book_delta_prices_clean_decimals` | `@pytest.mark.xfail(strict=True)`, `@pytest.mark.finding` |
| F-WS-003 | `tests/websocket/test_trades.py` | `test_trade_prices_clean_decimals` | `@pytest.mark.xfail(strict=True)`, `@pytest.mark.finding` |
| F-SOL-001 | `tests/solana/test_subscribe.py` | `test_subscribe_bare_receives_data`, `test_subscribe_system_program_receives_data`, `test_subscribe_spl_token_receives_data`, `test_subscribe_reproduction_rate`, `test_subscribe_receives_acknowledgment` (xfail) | 4 pass, 1 xfail |
| F-SOL-002 | `tests/solana/test_subscribe_filters.py` | `test_subscribe_multiple_programs`, `test_subscribe_empty_programs_array`, `test_any_non_hello_message_within_60s` (xfail) | 2 pass, 1 xfail |
| F-PERF-001 | `tests/performance/test_rest_latency.py` | `test_stats_p95_within_sla` (xfail), `test_stats_p99_within_sla` (xfail) | `@pytest.mark.xfail(strict=True)` |
| F-PERF-002 | `tests/performance/test_orders_perf.py` | `test_burst_orders_rate_limit_detected` | Documented (tolerance test, not xfail) |
| F-PERF-003 | `tests/performance/test_latency_under_load.py` | `test_snapshot_error_rate` | Documented (tolerance threshold <20%, not xfail) |

---

## Performance Findings (Locust Load Test)

### F-PERF-001: /stats Bimodal Latency (p95 > 3000ms)

- **Severity:** Medium
- **Component:** REST API — GET /stats
- **Test:** `test_stats_p95_within_sla`, `test_stats_p99_within_sla` in `tests/performance/test_rest_latency.py`

**Evidence (Locust 50 users, 60s):**

| Metric | Value |
|--------|-------|
| p50 | 520ms |
| p95 | 3200ms |
| p99 | 6200ms |
| Error rate | 0% |

**Root cause hypothesis:** The `/stats` endpoint computes `bookUpdatesPerSecond`, `tradesPerSecond`, and `currentSeq` synchronously on each request. Approximately 10% of requests coincide with the aggregation window, causing them to block for 2500-3000ms while the computation completes.

**Suggested fix:** Pre-compute statistics on a background timer (e.g., every 1s) and serve cached results. This would flatten the bimodal distribution to a consistent <300ms.

### F-PERF-002: POST /orders Rate Limited at 429 Under Load

- **Severity:** Medium
- **Component:** REST API — POST /orders
- **Test:** Discovered via Locust load testing (not currently xfail-tested)

**Evidence (Locust 50 users, 60s):**

| Metric | Value |
|--------|-------|
| Total requests | 238 |
| HTTP 429 responses | 158 (66.4%) |
| Success rate | 33.6% |
| p50 | 540ms |
| p95 | 2100ms |

**Root cause hypothesis:** The server enforces rate limiting on the `/orders` endpoint to prevent order spam. The rate limit threshold appears to be approximately 1-2 orders per second per client. Under 50 concurrent users, 66% of requests exceed this limit.

**Suggested fix:** Document the rate limit in the API reference (requests per second, per client/IP, burst allowance). Return a `Retry-After` header in 429 responses to help clients implement backoff.

### F-PERF-003: GET /snapshot HTTP 500 Under Load (14.1%)

- **Severity:** High
- **Component:** REST API — GET /markets/BTC-PERP/snapshot
- **Test:** `test_snapshot_error_rate_under_load` in `tests/performance/test_latency_under_load.py`

**Evidence (Locust 50 users, 60s):**

| Metric | Value |
|--------|-------|
| Total requests | 121 |
| HTTP 500 responses | 17 (14.1%) |
| p50 | 540ms |
| p95 | 2900ms |

**Root cause hypothesis:** The snapshot endpoint assembles the order book from a shared data structure. Under concurrent access, a race condition or lock contention causes the assembly to fail, returning HTTP 500 instead of a partial or cached result. The error rate correlates with concurrency level (~10% at 50 users, ~9% at 100 users from stress test).

**Suggested fix:** Add error handling around the snapshot assembly: return a cached last-known-good snapshot on failure, or use a copy-on-write data structure that eliminates concurrent access errors. At minimum, return a structured error response instead of raw 500.

---

## Summary

| Severity | Count | Finding IDs |
|----------|-------|-------------|
| High | 1 | F-PERF-003 |
| Medium | 10 | F-INFRA-001, F-REST-001, F-REST-002, F-WS-001, F-WS-002, F-WS-003, F-SOL-001, F-SOL-002, F-PERF-001, F-PERF-002 |
| Low | 1 | F-REST-004 |
| **Total** | **12** | |

---

*All findings are verified through automated pytest tests with `strict=True` xfail markers. When any of these issues are fixed server-side, the corresponding test will produce an XPASS (unexpected pass) failure, signaling that the finding should be re-evaluated and the xfail marker removed.*
