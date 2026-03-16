# SMFS Detailed Test Cases

## REST API -- GET /health

| ID | Title | P | Type | Why | Expected | Actual | Auto | File |
|----|-------|---|------|-----|----------|--------|------|------|
| TC-R01 | Returns 200 | P0 | Positive | Primary availability signal | 200 OK | 200 OK | Yes | test_health.py |
| TC-R02 | Schema validates | P0 | Positive | Contract compliance | {ok, serverTime, markets, wsUrl} | Matches | Yes | test_health.py |
| TC-R03 | ok is true | P0 | Positive | Service health state | ok == true | true | Yes | test_health.py |
| TC-R04 | serverTime current | P0 | Positive | Clock drift detection | Within 30s of UTC | Within 30s | Yes | test_health.py |
| TC-R05 | Markets has BTC-PERP | P0 | Positive | Market availability | "BTC-PERP" in markets | Present | Yes | test_health.py |
| TC-R06 | wsUrl uses wss:// | P0 | Positive | Secure protocol | Starts with "wss://" | Starts with wss:// | Yes | test_health.py |
| TC-R07 | Content-Type JSON | P0 | Positive | API contract | application/json | application/json | Yes | test_health.py |

## REST API -- GET /markets

| ID | Title | P | Type | Why | Expected | Actual | Auto | File |
|----|-------|---|------|-----|----------|--------|------|------|
| TC-R08 | Returns 200 | P0 | Positive | Market listing available | 200 OK | 200 OK | Yes | test_markets.py |
| TC-R09 | Schema validates | P0 | Positive | Contract compliance | {markets: [{marketId, base, quote}]} | Matches | Yes | test_markets.py |
| TC-R10 | Non-empty | P0 | Positive | At least one market | len >= 1 | 1 (BTC-PERP) | Yes | test_markets.py |
| TC-R11 | BTC-PERP details | P0 | Positive | Market attributes | base=BTC, quote=USDT | Correct | Yes | test_markets.py |
| TC-R12 | Content-Type JSON | P0 | Positive | API contract | application/json | application/json | Yes | test_markets.py |

## REST API -- GET /stats

| ID | Title | P | Type | Why | Expected | Actual | Auto | File |
|----|-------|---|------|-----|----------|--------|------|------|
| TC-R13 | Returns 200 | P0 | Positive | Stats endpoint available | 200 OK | 200 OK | Yes | test_stats.py |
| TC-R14 | Schema validates | P0 | Positive | Contract compliance | {bookUpdatesPerSecond, tradesPerSecond, connectedClients, currentSeq} | Matches | Yes | test_stats.py |
| TC-R15 | bookUpdates > 0 | P0 | Positive | Active feed | Positive integer | 30 | Yes | test_stats.py |
| TC-R16 | clients >= 0 | P0 | Positive | Valid count | Non-negative | 0+ | Yes | test_stats.py |
| TC-R17 | seq increases | P1 | Positive | Monotonicity | seq2 > seq1 | Increases | Yes | test_stats.py |
| TC-R18 | trades >= 0 | P0 | Positive | Valid rate | Non-negative | 10 | Yes | test_stats.py |
| TC-R19 | seq > 0 | P0 | Positive | Active feed | Positive | Positive | Yes | test_stats.py |
| TC-R20 | Content-Type JSON | P0 | Positive | API contract | application/json | application/json | Yes | test_stats.py |

## REST API -- GET /snapshot

| ID | Title | P | Type | Why | Expected | Actual | Auto | File |
|----|-------|---|------|-----|----------|--------|------|------|
| TC-R21 | Returns 200 | P0 | Positive | Snapshot available | 200 OK | 200 OK | Yes | test_snapshot.py |
| TC-R22 | Schema validates | P0 | Positive | Contract compliance | SnapshotResponse model | Matches | Yes | test_snapshot.py |
| TC-R23 | Has bids and asks | P0 | Positive | Order book data | Non-empty arrays | Present | Yes | test_snapshot.py |
| TC-R24 | Has timestamp | P1 | Positive | Freshness | ts > 0 | Positive | Yes | test_snapshot.py |
| TC-R25 | Prices positive | P1 | Positive | Valid prices | All > 0 | All positive | Yes | test_snapshot.py |
| TC-R26 | Content-Type JSON | P0 | Positive | API contract | application/json | application/json | Yes | test_snapshot.py |
| TC-R27 | Invalid market 4xx | P1 | Negative | Input validation | 400-499 | 4xx | Yes | test_snapshot.py |
| TC-R28 | Clean decimals | P1 | Finding | Float precision | No artifacts | **F-REST-001: artifacts present** | xfail | test_snapshot.py |
| TC-R29 | Book not crossed | P1 | Finding | Data integrity | bid < ask | **F-REST-002: sometimes crossed** | xfail | test_snapshot.py |

## REST API -- POST /orders

| ID | Title | P | Type | Why | Expected | Actual | Auto | File |
|----|-------|---|------|-----|----------|--------|------|------|
| TC-R30 | Limit order accepted | P0 | Positive | Core trading | 200, accepted=true, orderId | Accepted | Yes | test_orders.py |
| TC-R31 | Market order accepted | P0 | Positive | Core trading | 200, accepted=true | Accepted | Yes | test_orders.py |
| TC-R32 | Invalid market error | P1 | Negative | Input validation | < 500 | 4xx | Yes | test_orders.py |
| TC-R33 | Missing fields error | P1 | Negative | Param validation | < 500 | Error | Yes | test_orders.py |
| TC-R34 | Negative size error | P1 | Boundary | Size boundary | < 500 | Error | Yes | test_orders.py |
| TC-R35 | Zero size error | P1 | Boundary | Size boundary | < 500 | Error | Yes | test_orders.py |
| TC-R36 | Invalid side error | P1 | Negative | Enum validation | < 500 | Error | Yes | test_orders.py |
| TC-R37 | Invalid type error | P1 | Negative | Enum validation | < 500 | Error | Yes | test_orders.py |
| TC-R38 | Limit no price | P1 | Negative | Required field | < 500 | Error | Yes | test_orders.py |
| TC-R39 | Invalid market 4xx | P1 | Negative | Precise error | 400-499 | 4xx | Yes | test_orders.py |
| TC-R40 | Error has 'error' field | P1 | Negative | Error structure | JSON with error key | Has key | Yes | test_orders.py |
| TC-R41 | GET /orders 404 | P1 | Negative | Method support | 404 | 404 | Yes | test_orders.py |
| TC-R42 | Duplicate orders unique IDs | P1 | Idempotency | No accidental dedup | Different orderIds | Different | Yes | test_orders.py |
| TC-R43 | 5 concurrent accepted | P1 | Concurrency | Race safety | No 5xx | All processed | Yes | test_orders.py |
| TC-R44 | Concurrent unique IDs | P1 | Concurrency | ID generation | All unique | Unique | Yes | test_orders.py |

## REST API -- Error Handling, CORS, Methods

| ID | Title | P | Type | Why | Expected | Actual | Auto | File |
|----|-------|---|------|-----|----------|--------|------|------|
| TC-R45 | 404 on unknown path | P1 | Negative | Routing | 404 | 404 | Yes | test_error_cases.py |
| TC-R46 | Invalid market no 5xx | P1 | Security | Robustness | < 500 | 4xx | Yes | test_error_cases.py |
| TC-R47 | SQL injection safe | P1 | Security | Injection prevention | < 500 | 404 | Yes | test_error_cases.py |
| TC-R48 | XSS safe | P1 | Security | XSS prevention | < 500 | 404 | Yes | test_error_cases.py |
| TC-R49 | Path traversal safe | P1 | Security | Traversal prevention | < 500 | 404 | Yes | test_error_cases.py |
| TC-R54 | Error CT is JSON x3 | P1 | Finding | Error format | application/json | **F-REST-004: text/plain** | xfail | test_error_format.py |
| TC-R55-57 | Unsupported methods x6 | P1 | Negative | HTTP compliance | 4xx | 404 | Yes | test_method_not_allowed.py |
| TC-R58-63 | CORS/OPTIONS x6 | P2 | CORS | Cross-origin access | 204, ACAO headers | Correct | Yes | test_error_cases.py |
| TC-R64-65 | Docs endpoints x2 | P2 | Positive | API docs | 200 | Pending CTO deploy | Yes | test_docs_endpoints.py |

## WebSocket -- Connection and Ping/Pong

| ID | Title | P | Type | Why | Expected | Actual | Auto | File |
|----|-------|---|------|-----|----------|--------|------|------|
| TC-W01-06 | Connection lifecycle x6 | P0 | Positive | Handshake contract | hello with correct fields | Correct | Yes | test_connection.py |
| TC-W07 | Invalid marketId | P1 | Finding | Input validation | Rejected | **F-WS-001: accepted** | xfail | test_connection.py |
| TC-W08-09 | Missing/empty marketId x2 | P1 | Edge | Default behavior | Error or default | Defaults to BTC-PERP | Yes | test_connection.py |
| TC-W10-13 | Ping/pong x4 | P0 | Positive | Keepalive | Pong with ts | Correct | Yes | test_ping_pong.py |

## WebSocket -- Data Integrity

| ID | Title | P | Type | Why | Expected | Actual | Auto | File |
|----|-------|---|------|-----|----------|--------|------|------|
| TC-W14-18 | Book delta schema x5 | P0 | Positive | Data contract | Valid structure | Correct | Yes | test_book_delta.py |
| TC-W19 | Float artifacts | P1 | Finding | Precision | Clean decimals | **F-WS-002: artifacts** | xfail | test_book_delta.py |
| TC-W20 | Zero-size removal | P2 | Positive | Removal semantics | Valid | Valid | Yes | test_book_delta.py |
| TC-W21-25 | Sequence integrity x5 | P0 | Positive | Ordering guarantee | Monotonic, contiguous | Correct | Yes | test_sequence.py |
| TC-W26-30 | Trade fields x5 | P0 | Positive | Data contract | Valid fields | Correct | Yes | test_trades.py |
| TC-W31 | Trade float artifacts | P1 | Finding | Precision | Clean decimals | **F-WS-003: artifacts** | xfail | test_trades.py |

## WebSocket -- Disconnect and Server Behavior

| ID | Title | P | Type | Why | Expected | Actual | Auto | File |
|----|-------|---|------|-----|----------|--------|------|------|
| TC-W32-36 | Client disconnect x5 | P0 | Positive | Lifecycle | Clean close/reconnect | Correct | Yes | test_disconnect.py |
| TC-W37 | 30s idle keepalive | P1 | Positive | No premature timeout | Data continues | Data flows | Yes | test_disconnect.py |
| TC-W38 | Client isolation | P1 | Integration | Connection independence | B unaffected | B continues | Yes | test_disconnect.py |
| TC-W39 | Binary frame resilience | P2 | Edge | Protocol robustness | No crash | Survives | Yes | test_disconnect.py |
| TC-W40 | Oversized message | P2 | Edge | Input boundary | No crash | Survives or skip | Yes | test_disconnect.py |
| TC-W41-44 | Reconnection x4 | P0 | Positive | Service continuity | New hello, data resumes | Correct | Yes | test_reconnection.py |

## Solana Stream

| ID | Title | P | Type | Why | Expected | Actual | Auto | File |
|----|-------|---|------|-----|----------|--------|------|------|
| TC-S01-07 | Connection x7 | P0 | Positive | Stream handshake | stream_hello, resilience | Correct | Yes | test_stream_connect.py |
| TC-S08-10 | Ping/pong x3 | P0 | Positive | Stream keepalive | Pong response | Correct | Yes | test_stream_ping.py |
| TC-S11-15 | Subscribe x5 | P0 | Finding | Stream data delivery | Transaction data | **F-SOL-001: no data** | xfail | test_subscribe.py |
| TC-S16-18 | Subscribe filters x3 | P1 | Finding | Filter support | Filtered data | **F-SOL-002: no data** | xfail | test_subscribe_filters.py |
| TC-S19-26 | Transaction schema x8 | P0 | Unit | Solana data contract | Valid/invalid parsed correctly | Correct (ValidationError) | Yes | test_stream_schema.py |
| TC-S27-32 | Slot ordering x6 | P0 | Unit | Reorg/gap detection | Gaps and rollbacks detected | Correct | Yes | test_stream_schema.py |
| TC-S33-46 | Signature/pubkey x14 | P0 | Unit | Base58+solders Ed25519 | Valid/invalid discriminated | Correct (solders) | Yes | test_signature_validation.py |

## Performance

| ID | Title | P | Type | Metric | Threshold | Actual | Auto | File |
|----|-------|---|------|--------|-----------|--------|------|------|
| TC-P01-09 | Fast endpoint SLA x9 | P1 | Perf | p50/p95/p99 | 300-1500ms | Within SLA | Yes | test_rest_latency.py |
| TC-P10 | /stats p50 | P1 | Perf | p50 latency | < 300ms | ~200ms (PASS) | Yes | test_rest_latency.py |
| TC-P11 | /stats p95 | P1 | Finding | p95 latency | < 1000ms | **F-PERF-001: ~2800ms** | xfail | test_rest_latency.py |
| TC-P12 | /stats p99 | P1 | Finding | p99 latency | < 2000ms | **F-PERF-001: ~3100ms** | xfail | test_rest_latency.py |
| TC-P13-19 | Latency under load x7 | P1 | Perf | Concurrent latency | Various | See PERFORMANCE.md | Yes | test_latency_under_load.py |
| TC-P20-21 | WS throughput x2 | P1 | Perf | msg/sec, hello latency | >= 1/s, < 2s | ~30/s, ~650ms | Yes | test_ws_throughput.py |
| TC-P22-27 | WS advanced x6 | P1 | Perf | Inter-msg, establishment | < 200ms, < 2s | Within SLA | Yes | test_ws_advanced.py |
| TC-P28-29 | Concurrent WS x2 | P1 | Perf | Connection scaling | 100%, >= 90% | 100% | Yes | test_concurrent_ws.py |
| TC-P30-32 | Burst traffic x3 | P1 | Perf | Burst resilience | 100%, >= 95%, < 2s | Within SLA | Yes | test_burst.py |
