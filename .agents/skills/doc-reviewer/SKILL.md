---
name: doc-reviewer
description: >
  Review API documentation (OpenAPI, markdown PRD, or spec files) against the
  existing test suite to identify coverage gaps, missing error cases, and schema
  mismatches. Inspired by addyosmani/agent-skills /spec + /review pattern.
---

# API Documentation Reviewer

Analyze an API specification and compare it against the current test coverage
to produce a structured gap report.

## When to Use

- A new or updated API reference document is provided
- You want to verify test coverage matches the documented API surface
- Before writing new tests, to know what is missing

## Required Context

Read these files before starting:

- `src/smfs_qa/schemas.py` -- current Pydantic response models
- `src/smfs_qa/routes/` -- current route model definitions
- `docs/testcases/smfs-testcases-detail.md` -- existing test case inventory
- `FINDINGS.md` -- known issues that may explain intentional gaps
- `tests/` directory structure -- to map which endpoints have test files

## Workflow

### Step 1: Parse the API Document

Extract a complete list of:
- Endpoints (method + path)
- Request parameters (query, body, headers)
- Response schemas (status codes, body fields, types)
- Error responses (4xx, 5xx scenarios documented)
- WebSocket message types and their schemas
- Any rate limits, authentication, or special requirements mentioned

### Step 2: Inventory Existing Coverage

Scan the test suite:
```
tests/rest/       -- REST endpoint tests
tests/websocket/  -- WebSocket tests
tests/solana/     -- Solana stream tests
tests/performance/ -- Performance benchmarks
```

For each endpoint, check:
- Happy path test exists?
- Error/boundary cases covered?
- Schema validation test exists?
- Performance benchmark exists?

### Step 3: Diff and Classify Gaps

For each gap found, classify as:

| Priority | Type | Example |
|----------|------|---------|
| P0 | Untested endpoint | No tests at all for a documented endpoint |
| P1 | Missing error case | Happy path tested but no 4xx/5xx tests |
| P1 | Schema mismatch | Pydantic model doesn't match documented schema |
| P2 | Missing boundary | No edge cases (empty arrays, max values, etc.) |
| P2 | Missing perf test | No latency/throughput benchmark for endpoint |
| P3 | Documentation gap | Endpoint works but undocumented behavior found |

### Step 4: Cross-Reference Findings

Check FINDINGS.md for each gap:
- Is this gap explained by a known finding? (e.g., F-REST-004 explains why error format tests exist)
- Should a new finding be opened for undocumented behavior?

## Output Format

Produce a markdown table:

```markdown
## Coverage Gap Report

| # | Endpoint | Method | Gap Type | Priority | Notes |
|---|----------|--------|----------|----------|-------|
| 1 | /orders  | POST   | Missing boundary: negative price | P2 | Only negative size tested |
| 2 | /ws      | WS     | Missing: idle timeout test | P1 | No test for server-initiated disconnect |
```

Followed by a summary:
- Total gaps found
- Gaps by priority (P0/P1/P2/P3)
- Recommended next action (invoke testcase-generator for P0/P1 gaps)
