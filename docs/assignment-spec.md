# Sonic SVM – Senior Testing Engineer Technical Take-Home

Created: March 11, 2026
Tags: QA, Testing, TypeScript, WebSocket, Solana

## Objective

Perform a comprehensive **quality audit** of the Sonic Market Feed Service (SMFS) — a real-time market data and Solana transaction streaming service.

You will be given:

- A deployed, live instance of the service
- API documentation describing expected behavior
- **No source code access**

Your task is to systematically test the service, discover and document any anomalies, build an automated test suite, measure performance, and configure a CI pipeline — all without seeing the implementation.

---

## System Under Test

- **REST API:** `https://interviews-api.sonic.game`
- **Market Feed WebSocket:** `wss://interviews-api.sonic.game/ws?marketId=BTC-PERP`
- **Transaction Stream WebSocket:** `wss://interviews-api.sonic.game/ws/stream`
- **API Documentation:** See the attached `smfs-api-reference.md`
- **API Explorer:** `https://interviews-api.sonic.game/docs`

The service provides two main interfaces:

1. **REST API** — Market data endpoints (health, markets, order book snapshots, orders, stats)
2. **WebSocket feeds** — Real-time market data (`/ws`) and Solana transaction stream (`/ws/stream`)

> **Note:** This is a production service. Like any production system, it may exhibit unexpected behaviors. A senior testing engineer is expected to discover, document, and write resilient tests around any anomalies encountered.
> 

---

## Deployment Requirements

- Your test suite and documentation must be hosted on **GitHub**
- Your CI pipeline must run on **GitHub Actions**
- Provide:
    - GitHub repository link
    - CI pipeline status (green/passing)

---

## Core Deliverables

### 1. Test Plan (`TEST_PLAN.md`)

A structured document covering your testing strategy. Must include:

- **Scope** — What is being tested and what is explicitly out of scope
- **Risk analysis** — Which areas are highest risk and why
- **Test categories** — Functional, integration, performance, edge cases
- **Priority matrix** — Which tests are P0 (must have) vs P1/P2
- **Approach** — How you will handle intermittent/non-deterministic behaviors

### 2. Automated Test Suite

Runnable test code in your repository. Any language and framework is acceptable, but must:

- Execute via a **single command** (e.g., `make test`, `npm test`, `pytest`)
- Produce **machine-readable results** (JUnit XML, TAP, or JSON)
- Be designed to **handle intermittent failures gracefully** (not fail on every transient error)

**Minimum coverage requirements:**

- All 5 REST endpoints (happy path + error cases + boundary values)
- WebSocket market feed (`/ws`):
    - Connection lifecycle (connect, hello, ping/pong, disconnect)
    - Data integrity (sequence numbering, message schema)
    - At least ONE of: reconnection handling, concurrent connections, burst tolerance
- Solana transaction stream (`/ws/stream`):
    - Connection and filter verification
    - Transaction message schema validation
    - At least ONE of: reorg handling, signature format validation, slot ordering verification

### 3. Findings Report (`FINDINGS.md`)

Document any anomalies, bugs, or unexpected behaviors you discover. For each finding:

- **Title** and **severity** (Critical / High / Medium / Low)
- **Reproduction steps** (specific request or sequence to trigger)
- **Expected vs. actual behavior** (reference the API documentation)
- **Evidence** (logs, screenshots, test output, response samples)
- **Reproduction rate** (e.g., "occurs ~10% of requests" or "always")
- **Root cause hypothesis** (if you can determine one)
- **Suggested fix** (optional, but valued)

### 4. CI Pipeline (`.github/workflows/`)

A GitHub Actions workflow that:

- Runs your test suite against the live service
- Produces test result artifacts
- Has clear pass/fail status
- Handles test flakiness appropriately (retries, tolerance, or explicit flaky marking)

### 5. Performance Test Results (`PERFORMANCE.md`)

Document your performance testing methodology and results:

- **REST endpoint latency** — p50, p95, p99 under load
- **WebSocket throughput** — Messages received per second
- **Concurrent connection scaling** — Behavior under multiple simultaneous connections
- **Tool and methodology** — What you used and how
- **Thresholds and conclusions** — What is acceptable and what isn't

### 6. README

Setup instructions and testing strategy documentation:

- How to run the test suite locally
- Tool/framework selection rationale
- High-level testing strategy
- Coverage gaps you are aware of
- Any assumptions made

---

## Time Window

**48 hours** from receipt of this document.

---

## Evaluation Criteria

| Category | Weight | What We Look For |
| --- | --- | --- |
| Test Plan Quality | 10% | Risk-prioritized, structured, covers REST + WS + stream |
| REST API Coverage | 10% | All endpoints, error cases, boundary values, schema validation |
| WebSocket Coverage | 15% | Connection lifecycle, sequence integrity, chaos resilience |
| SVM/Solana Awareness | 15% | Stream testing, reorg understanding, signature validation, slot mechanics |
| Test Resilience & Design | 15% | Handles intermittent failures, statistical assertions, chaos-aware |
| Findings Quality | 10% | Discovery depth, evidence quality, severity accuracy, root cause analysis |
| Performance Testing | 10% | Methodology, metrics, tooling, conclusions |
| CI Pipeline | 5% | Runs reliably, reports clearly, handles flakiness |
| Code Quality | 5% | Clean architecture, reusable helpers, well-named tests |
| Documentation | 5% | Strategy explanation, tool rationale, gap acknowledgment |

---

## Solana Context

The `/ws/stream` endpoint streams real Solana transactions. Key concepts for testing:

- **Slot** — A time unit on Solana (~400ms). Slots are sequential but gaps are normal (empty slots).
- **Signature** — A Base58-encoded unique identifier for each transaction. Valid characters: `123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz`
- **Program ID** — The address of a program (smart contract) that processed the transaction.
- **Reorg** — A rollback where recent blocks are invalidated. Transactions from rolled-back slots may be re-delivered.
- **blockTime** — Unix timestamp in seconds. May be `null` for very recent, unconfirmed slots.
- **Lamports** — The smallest unit of SOL. 1 SOL = 1,000,000,000 lamports. Fees are denominated in lamports.

---

## Submission

When complete, send us:

1. **GitHub repository URL** (public, or grant access to the provided GitHub username)
2. **Link to a passing CI run** (GitHub Actions)

---

> **Important:** During the review call, you will be asked to:
> 
> - Explain your test strategy and most significant findings
> - Write a new test for an edge case you may have missed
> - Debug a provided flaky test scenario
> - Discuss what production monitoring you would add beyond testing