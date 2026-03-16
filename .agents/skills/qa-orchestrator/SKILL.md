---
name: qa-orchestrator
description: >
  Orchestrate the full QA pipeline by chaining the other skills in the correct
  order based on the trigger context. Supports three workflows: API doc review
  cycle, CI failure response, and full audit.
---

# QA Pipeline Orchestrator

Chain the QA agent skills together based on what happened and what needs to be done.

## When to Use

- When you want to run a complete QA cycle
- When you are unsure which skill to invoke first
- When multiple skills need to run in sequence

## Available Skills

| Skill | Purpose | Invoke When |
|-------|---------|-------------|
| `doc-reviewer` | Find coverage gaps in API docs vs tests | New/updated API doc |
| `testcase-generator` | Generate pytest tests for gaps | Gaps identified |
| `ci-watcher` | Diagnose and fix CI failures | Pipeline is red |
| `failure-analyzer` | Classify test failures | Tests produced failures |
| `test-reporter` | Update all deliverable docs | After a test run |

## Workflow Chains

### Chain 1: API Doc Review Cycle

**Trigger:** A new or updated API specification is available.

```
doc-reviewer  -->  testcase-generator  -->  make test  -->  failure-analyzer  -->  test-reporter
```

1. Invoke **doc-reviewer** with the API spec file
2. Review the coverage gap report
3. Invoke **testcase-generator** for P0/P1 gaps
4. Run `make test` to execute all tests including new ones
5. If failures: invoke **failure-analyzer** to classify them
6. Invoke **test-reporter** to update all deliverable documents

### Chain 2: CI Failure Response

**Trigger:** GitHub Actions CI pipeline failed.

```
ci-watcher  -->  failure-analyzer  -->  test-reporter
```

1. Invoke **ci-watcher** to diagnose the failure
2. If ci-watcher patches and fixes: done
3. If ci-watcher escalates: invoke **failure-analyzer** for detailed classification
4. Invoke **test-reporter** to update documents if test counts changed

### Chain 3: Full Audit

**Trigger:** Manual request for a complete quality audit.

```
doc-reviewer  -->  testcase-generator  -->  make test  -->  failure-analyzer  -->  test-reporter  -->  ci-watcher
```

1. Invoke **doc-reviewer** to find all coverage gaps
2. Invoke **testcase-generator** for all gaps
3. Run `make test` for the full suite
4. Run `make load-test` for Locust benchmarks
5. Invoke **failure-analyzer** to classify any failures
6. Invoke **test-reporter** to update all documents
7. Commit and push
8. Invoke **ci-watcher** to monitor the CI pipeline

### Chain 4: Quick Report

**Trigger:** Just need to update documents after a test run.

```
test-reporter  (standalone)
```

1. Invoke **test-reporter** -- it reads results/ and updates all docs

## Decision Logic

When invoked without a specific chain, determine the right one:

```
Is there a new/updated API doc?
  YES --> Chain 1 (Doc Review Cycle)
  NO  -->
    Is CI currently failing?
      YES --> Chain 2 (CI Failure Response)
      NO  -->
        Does the user want a full audit?
          YES --> Chain 3 (Full Audit)
          NO  --> Chain 4 (Quick Report)
```

## Notes

- Always run `ruff check` and `ruff format` before committing
- Always run `pytest --collect-only` to verify new tests are valid
- Update the Allure report after test runs: `make report`
- Each skill produces output that feeds into the next skill in the chain
