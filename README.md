# SMFS Quality Audit

[![Smoke Test](https://github.com/waichun1003/SonicSVM/actions/workflows/smoke.yml/badge.svg)](https://github.com/waichun1003/SonicSVM/actions/workflows/smoke.yml)
[![Full Regression](https://github.com/waichun1003/SonicSVM/actions/workflows/regression.yml/badge.svg)](https://github.com/waichun1003/SonicSVM/actions/workflows/regression.yml)
[![Performance](https://github.com/waichun1003/SonicSVM/actions/workflows/performance.yml/badge.svg)](https://github.com/waichun1003/SonicSVM/actions/workflows/performance.yml)

A comprehensive quality audit of the **Sonic Market Feed Service** (SMFS) on the Sonic SVM (Solana Virtual Machine) network.

**Version:** 1.0
**Date:** 2026-03-16
**Auditor:** Samuel Cheng

**208 automated tests** | **12 findings** | **4-phase CI pipeline** | **6 agent skills**

## System Under Test

| Property | Value |
|----------|-------|
| REST API | `https://interviews-api.sonic.game` |
| WebSocket Feed | `wss://interviews-api.sonic.game/ws?marketId=BTC-PERP` |
| Solana Stream | `wss://interviews-api.sonic.game/ws/stream` |
| API Docs | `https://interviews-api.sonic.game/docs` |

## Quick Start

```bash
# Install
pip install -e ".[test,dev]"

# Run all tests
make test

# Run by component
make test-rest
make test-ws
make test-solana
make test-perf

# Load testing (Locust)
make load-test      # 50 users, 60s
make stress-test    # 100 users, 120s
make locust-ui      # Web UI at localhost:8089
```

## Architecture

All tests run live against the production SMFS API -- no mocks, no stubs.

```
src/smfs_qa/               # Framework package (pip-installable)
├── client.py              # Async HTTP client (httpx + structured logging)
├── ws_client.py           # Async WebSocket client (websockets + ping drain)
├── logger.py              # QA Logger (console PASS/FAIL + Allure attachments)
├── schemas.py             # Pydantic v2 strict response models
├── solana.py              # Base58 + solders Ed25519 signature validation
├── perf.py                # Latency tracker (numpy percentiles)
├── locustfile.py          # Locust load test user classes
├── routes/                # POM route models for REST endpoints
└── ws_routes/             # POM route models for WebSocket endpoints

tests/                     # Test cases only -- no framework code
├── rest/                  # 72 tests across 9 files
├── websocket/             # 44 tests across 7 files
├── solana/                # 54 tests across 8 files
└── performance/           # 38 tests across 7 files
```

### Design Patterns

- **POM Route Model** -- each endpoint is encapsulated in a route class for reusability
- **Pydantic v2 strict mode** -- every response is validated against typed models
- **xfail with strict=True** -- known defects are documented as findings while keeping CI green
- **solders** (Rust-backed) -- cryptographically correct Ed25519 signature validation
- **QA Logger** -- every HTTP/WS interaction is logged with PASS/FAIL and attached to Allure

## Test Results

| Suite | Passed | xFail | Total |
|-------|--------|-------|-------|
| REST API | 67 | 5 | 72 |
| WebSocket | 41 | 3 | 44 |
| Solana | 52 | 2 | 54 |
| Performance | 36 | 2 | 38 |
| **Total** | **196** | **12** | **208** |

## Findings (12 total)

| ID | Severity | Finding |
|----|----------|---------|
| F-INFRA-001 | Medium | Cloudflare 403 without User-Agent (mitigated in framework) |
| F-REST-001 | Medium | Floating-point price artifacts in snapshot |
| F-REST-002 | Medium | Crossed order book (best bid >= best ask) |
| F-REST-004 | Low | Error responses use text/plain instead of JSON |
| F-WS-001 | Medium | Invalid marketId silently accepted (data misrouting) |
| F-WS-002 | Medium | Floating-point artifacts in book_delta prices |
| F-WS-003 | Medium | Floating-point artifacts in trade prices |
| F-SOL-001 | Medium | Subscribe data delivery intermittent |
| F-SOL-002 | Medium | Subscribe filters intermittent |
| F-PERF-001 | Medium | /stats bimodal latency (p95 ~3000ms) |
| F-PERF-002 | Medium | POST /orders rate-limited at ~74% under load |
| F-PERF-003 | High | GET /snapshot returns 500 under concurrent access |

Full details in [FINDINGS.md](FINDINGS.md).

## CI/CD Pipeline

Four-phase cascading pipeline with automated failure analysis:

| Phase | Workflow | Trigger | Schedule | Timeout |
|-------|----------|---------|----------|---------|
| Smoke | `smoke.yml` | Every push/PR | Twice daily (6am + 6pm UTC) | 5 min |
| Regression | `regression.yml` | After smoke passes | Twice daily (6:10am + 6:10pm UTC) | 20 min |
| Performance | `performance.yml` | After regression passes | Daily (3am UTC) | 30 min |
| QA Analysis | `qa-analyze.yml` | When smoke or regression fails | -- | 5 min |

The pipeline cascades: **push -> smoke -> regression (if smoke passes) -> performance (if regression passes)**. If any phase fails, the QA Analysis workflow automatically classifies failures and posts a summary on the PR.

## Agent Skills

Six reusable [Agent Skills](https://github.com/vercel-labs/skills) in `.agents/skills/` that extend the QA framework. Compatible with Cursor, Claude Code, Copilot, and 38+ other AI agents.

| Skill | Purpose | Inspired By |
|-------|---------|-------------|
| `doc-reviewer` | Review API docs, find coverage gaps | [addyosmani /spec + /review](https://github.com/addyosmani/agent-skills) |
| `testcase-generator` | Generate pytest tests following project conventions | [LambdaTest pytest skill](https://github.com/LambdaTest/agent-skills) |
| `ci-watcher` | Diagnose CI failures, apply minimal patches | [tobrun/FIX_CI](https://gist.github.com/tobrun/68311698160d7ca1e354dfe522acb592) |
| `failure-analyzer` | Classify test failures, cross-reference findings | Custom |
| `test-reporter` | Update all deliverable docs with fresh results | [addyosmani /ship](https://github.com/addyosmani/agent-skills) |
| `qa-orchestrator` | Chain skills together for end-to-end QA cycles | Custom |

Install via the [skills CLI](https://github.com/vercel-labs/skills):
```bash
npx skills add ./  # installs from this repo's .agents/skills/
```

## Deliverables

| # | Document | Description |
|---|----------|-------------|
| 1 | [TEST_PLAN.md](TEST_PLAN.md) | Testing strategy, risk analysis, priority matrix |
| 2 | `tests/` (208 tests) | Automated test suite covering REST, WebSocket, Solana, and performance |
| 3 | [FINDINGS.md](FINDINGS.md) | 12 findings with severity, reproduction steps, and root cause analysis |
| 4 | `.github/workflows/` | 4-phase CI: smoke, regression, performance, QA analysis |
| 5 | [PERFORMANCE.md](PERFORMANCE.md) | Latency benchmarks and Locust load test results |
| 6 | `.agents/skills/` | 6 agent skills for automated QA workflows |
| 7 | This README | Project setup, architecture, and testing strategy |

## Why Python/pytest

| Concern | Advantage |
|---------|-----------|
| Async testing | `pytest-asyncio` for native async/await with WebSocket + HTTP |
| Schema validation | Pydantic v2 strict mode catches type coercion and missing fields |
| Solana primitives | `solders` (Rust-backed) for Ed25519 signature and pubkey validation |
| Performance | `numpy` for percentile calculations, `locust` for load simulation |
| Resilience | `pytest-rerunfailures` + `tenacity` for retry at both test and HTTP levels |
| Reporting | `allure-pytest` for rich HTML reports, JUnit XML for CI integration |

## Coverage Gaps

| Gap | Reason | Impact |
|-----|--------|--------|
| WebSocket scaling beyond 10 connections | 10 concurrent connections showed no degradation | Low |
| API reference-based expected values | Official API reference not provided | Medium |

## Assumptions

| Assumption | Rationale |
|------------|-----------|
| Black-box testing only | No access to source code or internal systems |
| Live service is available | Retries and reruns handle transient network issues |
| BTC-PERP is the primary market | Tests focus on BTC-PERP; SOL-PERP also available in /stats |
| No authentication required | No 401/403 responses observed during testing |
| Timestamps are in milliseconds | All server timestamps are 13-digit Unix epoch values |
| Stats response is nested | `/stats` returns per-market stats under a `markets` dictionary |
