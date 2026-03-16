---
name: testcase-generator
description: >
  Generate pytest test files following the project's POM pattern, Pydantic
  validation, Allure decorators, and QALogger assertions. Takes a coverage gap
  report or endpoint spec as input. Inspired by LambdaTest/agent-skills pytest pattern.
---

# Test Case Generator

Generate production-ready pytest test files that follow the project's established
conventions and patterns.

## When to Use

- After doc-reviewer produces a coverage gap report
- When a new endpoint or feature needs test coverage
- When existing tests need expansion for edge cases

## Required Context

Read these files to learn the project conventions:

**Framework code:**
- `src/smfs_qa/client.py` -- SMFSClient (async httpx wrapper with QA logging)
- `src/smfs_qa/ws_client.py` -- WSTestClient (async websockets wrapper with retry)
- `src/smfs_qa/schemas.py` -- Pydantic v2 strict models for all responses
- `src/smfs_qa/logger.py` -- QALogger (PASS/FAIL assertions + Allure attach)
- `src/smfs_qa/routes/` -- POM route models for REST endpoints
- `src/smfs_qa/ws_routes/` -- POM route models for WebSocket endpoints

**Fixtures (from conftest.py):**
- `api_client` -- async SMFSClient instance
- `health_route`, `markets_route`, `snapshot_route`, `orders_route`, `stats_route` -- REST route fixtures
- `market_feed_route` -- WebSocket market feed route
- `solana_stream_route` -- Solana stream route

**Template files (read one from each category):**
- `tests/rest/test_health.py` -- REST test pattern
- `tests/websocket/test_connection.py` -- WebSocket test pattern
- `tests/solana/test_stream_connect.py` -- Solana stream test pattern
- `tests/performance/test_rest_latency.py` -- Performance test pattern

## Conventions to Follow

### File Structure
```python
"""One-line description of what this file tests.

Explains the testing scope and any relevant context about
the endpoint or feature being tested.
"""

from __future__ import annotations

import pytest
import allure
# import project modules as needed

pytestmark = [pytest.mark.rest]  # or websocket, solana, perf


@allure.feature("REST API")  # or "WebSocket Market Feed", "Solana Transaction Stream", "Performance"
@allure.story("Specific Area")
class TestClassName:
    """Class-level docstring."""

    async def test_descriptive_name(self, fixture_name) -> None:
        """What this test verifies."""
        # test body
```

### Rules

1. Every test file has a module docstring (no changelog language)
2. Every test class has `@allure.feature()` and `@allure.story()` decorators
3. Every test method has a one-line docstring
4. Use `pytestmark` for suite markers (`rest`, `websocket`, `solana`, `perf`)
5. All tests are `async def` (the framework uses pytest-asyncio)
6. Use route fixtures for endpoint interactions, not raw `api_client.get()`
7. Use Pydantic `model_validate()` for schema assertions
8. Use `QALogger.assert_*()` for assertions that should appear in Allure
9. Known defects use `@pytest.mark.xfail(reason="...", strict=True/False)`
10. Intermittent findings use `strict=False`; deterministic use `strict=True`

### xfail Pattern for Findings
```python
@pytest.mark.xfail(
    reason="Description of the known defect",
    strict=False,  # False for intermittent, True for 100% reproducible
)
@pytest.mark.finding
async def test_expected_behavior(self, fixture) -> None:
    """What correct behavior should be."""
    # Assert the CORRECT behavior -- test fails = finding confirmed
```

## Workflow

### Step 1: Determine Test Category

Based on the endpoint/feature, place the file in:
- `tests/rest/` for REST API endpoints
- `tests/websocket/` for WebSocket market feed
- `tests/solana/` for Solana transaction stream
- `tests/performance/` for latency/throughput benchmarks

### Step 2: Generate Test File

Create the file following the conventions above. Include:
- Happy path tests (P0)
- Error case tests -- invalid inputs, missing fields (P1)
- Boundary value tests -- zero, negative, max values (P2)
- Schema validation tests -- Pydantic model_validate (P0)

### Step 3: Validate

Run these commands to verify the generated tests:
```bash
ruff check tests/path/to/new_test.py
ruff format tests/path/to/new_test.py
pytest tests/path/to/new_test.py --collect-only
```

### Step 4: Update Test Case Inventory

Add new test cases to `docs/testcases/smfs-testcases-detail.md` following the
existing table format.

## Output

- One or more new test files in `tests/`
- Updated `docs/testcases/smfs-testcases-detail.md`
- All files pass `ruff check` and `pytest --collect-only`
