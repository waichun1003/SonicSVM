# SMFS Test Cases (192 automated tests)

## REST API (70 tests)

### GET /health (7 tests) [test_health.py]
#### Positive
- TC-R01: Returns 200 OK (P0) -- Why: Health check is the primary availability signal
- TC-R02: Schema validates against HealthResponse {ok, serverTime, markets, wsUrl} (P0) -- Why: Contract compliance
- TC-R03: ok field is true (P0) -- Why: Service reports healthy state
- TC-R04: serverTime within 30s of local clock (P0) -- Why: Detect clock drift or stale responses
- TC-R05: markets array contains BTC-PERP (P0) -- Why: Confirm active market availability
- TC-R06: wsUrl starts with wss:// (P0) -- Why: Ensure secure WebSocket protocol
- TC-R07: Content-Type is application/json (P0) -- Why: API contract requires JSON responses

### GET /markets (5 tests) [test_markets.py]
#### Positive
- TC-R08: Returns 200 OK (P0) -- Why: Market listing must be available
- TC-R09: Schema validates against MarketsResponse (P0) -- Why: Contract compliance
- TC-R10: Markets array is non-empty (P0) -- Why: At least one market must exist
- TC-R11: BTC-PERP has base=BTC, quote=USDT (P0) -- Why: Verify market attributes
- TC-R12: Content-Type is application/json (P0) -- Why: API contract

### GET /stats (8 tests) [test_stats.py]
#### Positive
- TC-R13: Returns 200 OK (P0) -- Why: Server statistics endpoint must be available
- TC-R14: Schema validates against StatsResponse (P0) -- Why: Contract compliance
- TC-R15: bookUpdatesPerSecond > 0 (P0) -- Why: Active market should have book updates
- TC-R16: connectedClients >= 0 (P0) -- Why: Client count must be non-negative
- TC-R17: currentSeq increases across calls (P1) -- Why: Sequence counter monotonicity
- TC-R18: tradesPerSecond >= 0 (P0) -- Why: Trade rate must be non-negative
- TC-R19: currentSeq > 0 (P0) -- Why: Active feed should have positive sequence
- TC-R20: Content-Type is application/json (P0) -- Why: API contract

### GET /markets/BTC-PERP/snapshot (9 tests) [test_snapshot.py]
#### Positive
- TC-R21: Returns 200 OK (P0) -- Why: Snapshot provides order book state
- TC-R22: Schema validates against SnapshotResponse (P0) -- Why: Contract compliance
- TC-R23: Has non-empty bids and asks arrays (P0) -- Why: Active market has order book
- TC-R24: Timestamp is positive (P1) -- Why: Snapshot freshness indicator
- TC-R25: All bid/ask prices are positive (P1) -- Why: Prices must be valid
- TC-R26: Content-Type is application/json (P0) -- Why: API contract
- TC-R27: Invalid marketId returns 4xx (P1) -- Why: Input validation
#### Findings (xfail)
- TC-R28: Prices have clean decimals (P1, xfail F-REST-001) -- Why: IEEE 754 float artifacts
- TC-R29: Best bid < best ask (P1, xfail F-REST-002) -- Why: Crossed book = data integrity issue

### POST /orders (15 tests) [test_orders.py]
#### Positive
- TC-R30: Valid limit order accepted (P0) -- Why: Core trading function
- TC-R31: Valid market order accepted (P0) -- Why: Core trading function
#### Negative
- TC-R32: Invalid marketId returns 4xx (P1) -- Why: Input validation
- TC-R33: Missing required fields returns error (P1) -- Why: Parameter validation
- TC-R34: Negative size returns error (P1) -- Why: Boundary value
- TC-R35: Zero size returns error (P1) -- Why: Boundary value
- TC-R36: Invalid side value returns error (P1) -- Why: Enum validation
- TC-R37: Invalid type value returns error (P1) -- Why: Enum validation
- TC-R38: Limit order without price returns error (P1) -- Why: Required field for limit
- TC-R39: Invalid market returns 4xx specifically (P1) -- Why: Precise error code
- TC-R40: Error response has 'error' field (P1) -- Why: Error body structure
- TC-R41: GET /orders returns 404 (P1) -- Why: Only POST is supported
#### Idempotency and Concurrency
- TC-R42: Duplicate orders get different IDs (P1) -- Why: No accidental dedup
- TC-R43: 5 concurrent orders all processed (P1) -- Why: Race condition safety
- TC-R44: Concurrent orders have unique IDs (P1) -- Why: ID generation under load

### Error Handling (15 tests) [test_error_cases.py, test_error_format.py]
#### Security
- TC-R45: Nonexistent path returns 404 (P1)
- TC-R46: Invalid marketId does not cause 5xx (P1) -- Why: Server robustness
- TC-R47: SQL injection does not cause 5xx (P1) -- Why: Security
- TC-R48: XSS payload does not cause 5xx (P1) -- Why: Security
- TC-R49: Path traversal does not cause 5xx (P1) -- Why: Security
- TC-R50: Invalid market returns precise 4xx (P1)
- TC-R51: 404 body is not empty (P2)
#### HTTP Semantics
- TC-R52: HEAD /health returns 200 (P2) -- Why: HTTP spec compliance
- TC-R53: Extra query params are ignored (P2) -- Why: API robustness
#### Findings (xfail)
- TC-R54: Error Content-Type is JSON [3 paths] (P1, xfail F-REST-004) -- Why: Error format consistency

### HTTP Method Enforcement (6 tests) [test_method_not_allowed.py]
- TC-R55: POST, PUT, PATCH, DELETE /health return 4xx (P1)
- TC-R56: PUT /markets returns 4xx (P1)
- TC-R57: DELETE /stats returns 4xx (P1)

### CORS (6 tests) [test_error_cases.py]
- TC-R58: OPTIONS /health returns 204 (P2) -- Why: CORS preflight
- TC-R59: OPTIONS includes Allow-Methods (P2) -- Why: CORS compliance
- TC-R60: CORS origin on success responses (P2) -- Why: Cross-origin access
- TC-R61: CORS origin on error responses (P2) -- Why: Cross-origin errors
- TC-R62: OPTIONS /markets returns 204 (P2)
- TC-R63: OPTIONS /stats returns 204 (P2)

### API Documentation (2 tests) [test_docs_endpoints.py]
- TC-R64: GET /docs returns 200 (P2) -- Why: API explorer availability
- TC-R65: GET /openapi.json returns 200 (P2) -- Why: Machine-readable spec

---

## WebSocket Market Feed (44 tests)

### Connection Lifecycle (9 tests) [test_connection.py]
#### Positive
- TC-W01: First message is hello (P0) -- Why: Connection handshake contract
- TC-W02: Hello validates against WsHello schema (P0) -- Why: Schema compliance
- TC-W03: Hello marketId matches BTC-PERP (P0) -- Why: Subscription confirmation
- TC-W04: Hello serverTime within 30s (P0) -- Why: Clock drift detection
- TC-W05: Type field is exactly "hello" (P0)
- TC-W06: Data flows after hello (P0) -- Why: Feed is active
#### Edge Cases
- TC-W07: Invalid marketId rejected (P1, xfail F-WS-001) -- Why: Input validation
- TC-W08: No marketId defaults to BTC-PERP (P1) -- Why: Default behavior
- TC-W09: Empty marketId handled gracefully (P1) -- Why: Boundary value

### Ping/Pong (4 tests) [test_ping_pong.py]
- TC-W10: Ping receives pong (P0) -- Why: Keepalive mechanism
- TC-W11: Pong validates against WsPong schema (P0) -- Why: Schema compliance
- TC-W12: Pong timestamp is recent (P1) -- Why: Server time accuracy
- TC-W13: 3 consecutive pings all get pongs (P1) -- Why: Sustained keepalive

### Book Delta (7 tests) [test_book_delta.py]
- TC-W14: Schema validates against WsBookDelta (P0) -- Why: Data contract
- TC-W15: Has bids and asks lists (P0) -- Why: Structure compliance
- TC-W16: Levels have price and size (P0) -- Why: Field completeness
- TC-W17: Has seq field (P0) -- Why: Sequence tracking
- TC-W18: Has timestamp (P1) -- Why: Data freshness
- TC-W19: Prices clean decimals (P1, xfail F-WS-002) -- Why: Float artifact detection
- TC-W20: Zero-size is valid removal (P2) -- Why: Order book level removal semantics

### Sequence Numbers (5 tests) [test_sequence.py]
- TC-W21: Seq monotonically increasing (P0) -- Why: Data ordering guarantee
- TC-W22: No seq gaps (P0) -- Why: Message loss detection
- TC-W23: Seq only on book_delta (P0) -- Why: Type isolation
- TC-W24: Seq are positive integers (P0) -- Why: Type validation
- TC-W25: Timestamps non-decreasing (P1) -- Why: Temporal ordering

### Trades (6 tests) [test_trades.py]
- TC-W26: Schema validates against WsTrade (P0) -- Why: Data contract
- TC-W27: Has required fields (P0) -- Why: Field completeness
- TC-W28: Side is buy or sell (P1) -- Why: Enum validation
- TC-W29: TradeIds are unique (P1) -- Why: Dedup detection
- TC-W30: Size is positive (P1) -- Why: Boundary validation
- TC-W31: Prices clean decimals (P1, xfail F-WS-003) -- Why: Float artifact detection

### Disconnect (5 tests) [test_disconnect.py]
- TC-W32: Clean close without error (P0) -- Why: Graceful shutdown
- TC-W33: Close during data stream (P0) -- Why: Mid-stream disconnect safety
- TC-W34: Recv after close raises (P1) -- Why: State enforcement
- TC-W35: Double close is safe (P1) -- Why: Idempotent close
- TC-W36: Close then reconnect works (P0) -- Why: Connection lifecycle

### Server Behavior (4 tests) [test_disconnect.py]
- TC-W37: Server keeps alive during 30s idle (P1) -- Why: No premature timeout
- TC-W38: Client A close does not affect client B (P1) -- Why: Connection isolation
- TC-W39: Binary frame does not crash (P2) -- Why: Protocol resilience
- TC-W40: Oversized message does not crash (P2) -- Why: Input boundary

### Reconnection (4 tests) [test_reconnection.py]
- TC-W41: Reconnect receives new hello (P0) -- Why: Clean reconnection
- TC-W42: Data stream resumes after reconnect (P1) -- Why: Service continuity
- TC-W43: Seq continues from server state (P1) -- Why: No seq reset on client reconnect
- TC-W44: Rapid reconnect succeeds (P1) -- Why: Rate limit detection

---

## Solana Transaction Stream (46 tests)

### Connection (7 tests) [test_stream_connect.py]
- TC-S01: First message is stream_hello (P0) -- Why: Handshake contract
- TC-S02: Schema validates against WsStreamHello (P0) -- Why: Schema compliance
- TC-S03: serverTime within 30s (P0) -- Why: Clock drift detection
- TC-S04: Multiple connections independent (P1) -- Why: Connection isolation
- TC-S05: Graceful close (P1) -- Why: Clean shutdown
- TC-S06: Invalid JSON does not crash (P1) -- Why: Error resilience
- TC-S07: Plain text does not crash (P1) -- Why: Protocol resilience

### Ping/Pong (3 tests) [test_stream_ping.py]
- TC-S08: Ping receives pong (P0) -- Why: Stream keepalive
- TC-S09: Pong validates schema (P0) -- Why: Schema compliance
- TC-S10: Pong timestamp recent (P1) -- Why: Server time accuracy

### Subscribe (5 tests, all xfail F-SOL-001) [test_subscribe.py]
- TC-S11: Bare subscribe receives data (P0, xfail) -- Why: Core stream function
- TC-S12: System Program filter receives data (P0, xfail) -- Why: Program filter
- TC-S13: SPL Token filter receives data (P0, xfail) -- Why: Token filter
- TC-S14: Subscribe acknowledgment (P1, xfail) -- Why: Protocol confirmation
- TC-S15: Reproduction rate measurement (P1, xfail) -- Why: Defect quantification

### Subscribe Filters (3 tests, xfail F-SOL-002) [test_subscribe_filters.py]
- TC-S16: Multiple programs filter (P1, xfail) -- Why: Multi-filter support
- TC-S17: Any message within 60s (P1, xfail) -- Why: Stream liveness
- TC-S18: Empty programs array (P1, xfail) -- Why: Wildcard behavior

### Schema Validation - SolanaTransaction (8 unit tests) [test_stream_schema.py]
- TC-S19: Valid transaction parses (P0) -- Why: Schema contract
- TC-S20: Negative fee rejected (P0) -- Why: Lamport constraint (fees >= 0)
- TC-S21: Null blockTime accepted (P0) -- Why: Unconfirmed slots have null
- TC-S22: Empty programIds accepted (P1) -- Why: Native SOL transfer
- TC-S23: Missing signature rejected (P0) -- Why: Required field
- TC-S24: Missing slot rejected (P0) -- Why: Required field
- TC-S25: Zero fee accepted (P1) -- Why: Fee-exempt transactions
- TC-S26: Multiple programIds accepted (P1) -- Why: Multi-instruction transactions

### Schema Validation - Slot Ordering (6 unit tests) [test_stream_schema.py]
- TC-S27: Monotonic slots no issues (P0) -- Why: Normal behavior
- TC-S28: Gap detected (P0) -- Why: Skipped slots (normal on Solana)
- TC-S29: Rollback detected (P0) -- Why: Reorg indicator
- TC-S30: Single slot handled (P1) -- Why: Edge case
- TC-S31: Empty list handled (P1) -- Why: Edge case
- TC-S32: Normal Solana gaps (P1) -- Why: Gaps of 2+ are expected behavior

### Signature Validation (14 unit tests) [test_signature_validation.py]
- TC-S33: Valid 87-char signature (P0) -- Why: Typical Solana sig length
- TC-S34: Valid 88-char signature (P0) -- Why: Maximum valid length
- TC-S35: 43-char rejected by solders (P1) -- Why: Too short for Ed25519
- TC-S36: 42-char rejected (P1) -- Why: Below minimum
- TC-S37: Short string rejected (P1) -- Why: Invalid length
- TC-S38: Non-Base58 chars rejected (P0) -- Why: Charset validation
- TC-S39: Empty string rejected (P1) -- Why: Edge case
- TC-S40: Base58 excludes 0, O, I, l (P0) -- Why: Solana Base58 alphabet
- TC-S41: 89-char overlong rejected (P1) -- Why: Above maximum
- TC-S42: Solders validates byte length (P1) -- Why: Cryptographic validation proof
- TC-S43: System Program pubkey valid (P0) -- Why: Well-known address
- TC-S44: SPL Token pubkey valid (P0) -- Why: Well-known address
- TC-S45: Invalid pubkey rejected (P1) -- Why: Bad chars
- TC-S46: Empty pubkey rejected (P1) -- Why: Edge case

---

## Performance (32 tests)

### REST Latency SLA (12 tests) [test_rest_latency.py]
#### Fast Endpoints (9 tests)
- TC-P01: /health p50 < 300ms (P1) -- Why: SLA compliance
- TC-P02: /markets p50 < 300ms (P1)
- TC-P03: /snapshot p50 < 400ms (P1)
- TC-P04: /health p95 < 600ms (P1)
- TC-P05: /markets p95 < 600ms (P1)
- TC-P06: /snapshot p95 < 800ms (P1)
- TC-P07: /health p99 < 1000ms (P1)
- TC-P08: /markets p99 < 1000ms (P1)
- TC-P09: /snapshot p99 < 1500ms (P1)
#### Stats Latency (3 tests, 2 xfail F-PERF-001)
- TC-P10: /stats p50 < 300ms (P1) -- Why: Fast-path baseline
- TC-P11: /stats p95 < 1000ms (P1, xfail F-PERF-001) -- Why: Bimodal aggregation tail
- TC-P12: /stats p99 < 2000ms (P1, xfail F-PERF-001) -- Why: Bimodal aggregation worst case

### Latency Under Load (7 tests) [test_latency_under_load.py]
- TC-P13: /health stable under 5 concurrent (P1) -- Why: Connection pool sizing
- TC-P14: /health stable under 10 concurrent (P1) -- Why: Backpressure behavior
- TC-P15: /snapshot error rate under load (P1) -- Why: Validates F-PERF-003
- TC-P16: /stats bimodal distribution (P1) -- Why: Quantifies F-PERF-001
- TC-P17: Burst /markets 20 requests (P1) -- Why: Burst on non-health endpoint
- TC-P18: Burst /stats 20 requests (P1) -- Why: Burst on slow endpoint
- TC-P19: Burst /snapshot error rate (P1) -- Why: Burst on error-prone endpoint

### WS Throughput (2 tests) [test_ws_throughput.py]
- TC-P20: >= 1 msg/sec over 30s (P1) -- Why: Feed liveness
- TC-P21: Hello latency < 2s (P1) -- Why: Connection setup time

### WS Advanced (6 tests) [test_ws_advanced.py]
- TC-P22: Inter-message p95 < 200ms (P1) -- Why: Feed consistency
- TC-P23: No gap > 5s (P1) -- Why: Feed stall detection
- TC-P24: Connection establishment < 2s (P1) -- Why: Setup overhead
- TC-P25: 10 sequential connections avg < 1500ms (P1) -- Why: TLS session reuse
- TC-P26: book_delta rate matches /stats (P1) -- Why: Cross-component validation
- TC-P27: Trade rate is positive (P1) -- Why: Market activity

### Concurrent Connections (2 tests) [test_concurrent_ws.py]
- TC-P28: 5 connections all receive hello (P1) -- Why: Basic scaling
- TC-P29: 10 connections >= 90% success (P1) -- Why: Moderate scaling

### Burst Traffic (3 tests) [test_burst.py]
- TC-P30: 20 concurrent /health 100% success (P1) -- Why: Burst resilience
- TC-P31: 50 concurrent /health >= 95% success (P1) -- Why: Higher burst
- TC-P32: Recovery after burst < 2s (P1) -- Why: Recovery time

---

## Locust Load Testing (manual -- make targets)

### Available Profiles
- make load-test: 50 users, 60s, all endpoints + orders + WebSocket
- make stress-test: 100 users, 120s, full load
- make soak-test: 30 users, 300s, stability over time
- make load-test-rest: REST-only, 50 users
- make load-test-orders: Orders-only, 20 users
- make load-test-ws: WebSocket-only, 20 users
- make locust-ui: Interactive web UI at localhost:8089

### SLA Checked on Exit
- Aggregate p95 < 1000ms
- Aggregate error rate < 1%
- /snapshot error rate < 15%

---

## Findings Covered by Tests

| Finding | Severity | Tests | Status |
|---------|----------|-------|--------|
| F-REST-001 | Medium | TC-R28 (xfail) | Active -- float price artifacts |
| F-REST-002 | Medium | TC-R29 (xfail) | Active -- crossed order book |
| F-REST-004 | Low | TC-R54 (xfail x3) | Active -- text/plain errors |
| F-WS-001 | Low | TC-W07 (xfail) | Active -- invalid marketId accepted |
| F-WS-002 | Medium | TC-W19 (xfail) | Active -- book_delta float artifacts |
| F-WS-003 | Medium | TC-W31 (xfail) | Active -- trade float artifacts |
| F-SOL-001 | High | TC-S11-S15 (xfail x5) | Active -- no subscribe data |
| F-SOL-002 | High | TC-S16-S18 (xfail x3) | Active -- no filtered data |
| F-PERF-001 | Medium | TC-P11-P12 (xfail x2) | Active -- /stats bimodal latency |
| F-PERF-002 | Medium | Locust only | Active -- /orders 429 rate limit |
| F-PERF-003 | High | TC-P15, TC-P19 | Active -- /snapshot 500 under load |
| F-INFRA-001 | Medium | Mitigated in client | Mitigated -- Cloudflare 403 |
