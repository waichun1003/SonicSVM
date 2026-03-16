---
name: test-reporter
description: >
  Aggregate test execution results from JUnit XML, Allure, and Locust outputs
  and update the project's deliverable documents (README.md, TEST_PLAN.md,
  PERFORMANCE.md, FINDINGS.md) with current numbers. Inspired by
  addyosmani/agent-skills /ship pre-launch checklist pattern.
---

# Test Report Generator

After a full test run, update all deliverable documents with fresh results.

## When to Use

- After running `make test` (full suite)
- After a CI pipeline completes successfully
- Before submission or review -- to ensure documents reflect reality

## Required Context

**Result files:**
- `results/live.xml` -- JUnit XML from full test run
- `results/locust*.csv` -- Locust load test results (if available)
- `allure-results/` -- Allure result files (if available)

**Documents to update:**
- `README.md` -- test count table, findings table
- `TEST_PLAN.md` -- test counts per suite, execution matrix
- `PERFORMANCE.md` -- latency tables, Locust results
- `FINDINGS.md` -- severity distribution, test mapping
- `docs/testcases/test-execution-report.md` -- execution summary

## Workflow

### Step 1: Parse JUnit XML

```bash
python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('results/live.xml')
root = tree.getroot()
suites = {}
for tc in root.iter('testcase'):
    cls = tc.get('classname', '')
    suite = cls.split('.')[1] if '.' in cls else 'other'
    if suite not in suites:
        suites[suite] = {'passed': 0, 'xfail': 0, 'failed': 0}
    f = tc.find('failure')
    s = tc.find('skipped')
    if f is not None:
        suites[suite]['failed'] += 1
    elif s is not None and 'xfail' in s.get('type', ''):
        suites[suite]['xfail'] += 1
    else:
        suites[suite]['passed'] += 1
for name in sorted(suites):
    s = suites[name]
    total = s['passed'] + s['xfail'] + s['failed']
    print(f'{name}: {s[\"passed\"]} passed, {s[\"xfail\"]} xfail, {s[\"failed\"]} failed ({total} total)')
"
```

### Step 2: Update README.md

Update the test results table:
```markdown
| Suite | Passed | xFail | Total |
|-------|--------|-------|-------|
| REST API | {N} | {N} | {N} |
| WebSocket | {N} | {N} | {N} |
| Solana | {N} | {N} | {N} |
| Performance | {N} | {N} | {N} |
| **Total** | **{N}** | **{N}** | **{N}** |
```

Also update the total test count in the header line.

### Step 3: Update TEST_PLAN.md

Update the test count references:
- `REST API tests ({N} tests, {N} files)`
- `WebSocket tests ({N} tests, {N} files)`
- `Solana tests ({N} tests, {N} files)`
- `Performance tests ({N} tests, {N} files)`
- Total test counts in any summary sections

### Step 4: Update PERFORMANCE.md (if perf results available)

If `results/locust*.csv` files exist, update:
- Per-endpoint breakdown table (requests, failures, p50, p95, p99)
- Error analysis table
- SLA compliance table

### Step 5: Update FINDINGS.md

Verify the severity distribution table matches actual xfail counts.
Update the Test Mapping table if any tests were added or renamed.

### Step 6: Regenerate Test Execution Report

Update `docs/testcases/test-execution-report.md` with:
- Run date and duration
- Per-suite results
- xfail details (which findings are still active)
- Any new failures or resolved findings

## Output

All updated documents should be consistent with each other:
- README test count == TEST_PLAN test count == actual pytest collection count
- FINDINGS severity distribution == actual xfail count
- PERFORMANCE numbers == latest Locust/pytest results

Run `pytest tests/ --collect-only -q | tail -1` to verify the total count.
