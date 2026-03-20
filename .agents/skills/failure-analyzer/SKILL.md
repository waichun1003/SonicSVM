---
name: failure-analyzer
description: >
  Analyze test failures from JUnit XML results or pytest output. Classify each
  failure as transient, rate-limited, known finding, or new bug. Cross-reference
  against FINDINGS.md and draft new finding entries when warranted.
---

# Test Failure Analyzer

Parse test results, classify failures by root cause, and either correlate them
with known findings or draft new finding entries.

## When to Use

- After a test run produces failures
- When CI reports test failures that need triage
- To determine if a failure is a known issue or a new bug

## Required Context

- `FINDINGS.md` -- current finding IDs and descriptions
- `results/*.xml` -- JUnit XML test results
- `src/smfs_qa/logger.py` -- QALogger output format
- Allure results in `allure-results/` (if available)

## Workflow

### Step 1: Parse Test Results

Use the automated analysis script for initial classification:
```bash
python scripts/analyze_results.py results/*.xml --findings FINDINGS.md
```

For deeper manual inspection, read JUnit XML files from `results/`:
```bash
ls results/*.xml
```

### Step 2: Classify Each Failure

Apply these classification rules in order:

| Pattern in Error Message | Category | Severity |
|--------------------------|----------|----------|
| `HTTP 503` / `InvalidStatus: 503` | Transient | Low -- server restart |
| `HTTP 429` / `Too many requests` | Rate Limited | Low -- known F-PERF-002 |
| `XPASS(strict)` | Finding Resolved | Info -- update xfail marker |
| `TimeoutError` / `asyncio.TimeoutError` | Transient | Low -- network latency |
| `ValidationError` (Pydantic) | Schema Change | High -- API contract changed |
| `AssertionError` with `F-REST-*` or `F-WS-*` in xfail reason | Known Finding | Info -- expected |
| `ConnectionRefused` / `DNS` | Infrastructure | Medium -- server down |
| Any other `AssertionError` | Potential New Bug | High -- investigate |

### Step 3: Cross-Reference FINDINGS.md

For each failure:
1. Read `FINDINGS.md` and extract all finding IDs (F-INFRA-001, F-REST-001, etc.)
2. Check if the failing test is listed in the Test Mapping table
3. If listed: this is a known finding, note it
4. If NOT listed: this may be a new finding

### Step 4: Draft New Findings (if any)

For failures classified as "Potential New Bug", draft a finding entry:

```markdown
### F-{COMPONENT}-{NNN}: {Title}

- **Severity:** {Critical/High/Medium/Low}
- **Component:** {REST API / WebSocket / Solana / Performance}
- **Reproduction Rate:** {percentage or "always"}
- **Test:** `{test_name}` in `{test_file}`

**Description:**
{What the test expected vs what actually happened}

**Evidence:**
{Error message and relevant response data}

**Root Cause Hypothesis:**
{Best guess at why this happens}
```

### Step 5: Check for Resolved Findings

If any xfail tests passed (XPASS) or previously-failing tests now pass:
- Flag the corresponding finding as potentially resolved
- Recommend updating the xfail marker or removing it

## Output Format

```markdown
## Failure Analysis Report

**Run:** {date/time or run ID}
**Total tests:** {N} | **Passed:** {N} | **Failed:** {N} | **xFail:** {N}

### Failures by Category

| # | Test | Category | Known Finding | Action |
|---|------|----------|---------------|--------|
| 1 | test_foo | Transient (503) | -- | Rerun |
| 2 | test_bar | Schema Change | -- | Investigate: draft F-REST-005 |
| 3 | test_baz | Known Finding | F-PERF-002 | Expected -- no action |

### New Findings to Add
{Draft finding entries, if any}

### Potentially Resolved Findings
{List of findings whose tests now pass}

### Recommended Actions
1. {Action item}
2. {Action item}
```
