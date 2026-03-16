---
name: ci-watcher
description: >
  Monitor GitHub Actions CI checks on the current branch, diagnose failures,
  and apply minimal patches to resolve deterministic issues. Adapted from
  tobrun/FIX_CI pattern, customized for the SMFS 3-phase pipeline
  (smoke/regression/performance) with QA-specific failure classification.
---

# CI Watcher + Auto-Patcher

You are operating on the current branch. Your job is to detect failing GitHub
Actions checks, classify failures against known findings, and apply the smallest
safe patch to get CI green -- or escalate if the failure requires human judgment.

## When to Use

- CI pipeline fails after a push or PR
- You need to diagnose why a workflow is red
- You want to auto-fix a deterministic CI failure

## Guardrails

- Minimal diffs only. No refactors.
- Never disable tests to make CI green.
- Never commit secrets or tokens.
- If a failure looks flaky (503, timeout, rate limit), rerun first.
- If confidence is low, escalate with evidence instead of guessing.
- Do not modify CI workflow files without explicit approval.
- Maximum 2 patch iterations before escalating.

## SMFS Pipeline Context

This project has a 3-phase CI pipeline:

| Phase | Workflow | Trigger | What It Tests |
|-------|----------|---------|---------------|
| Smoke | `smoke.yml` | Every push/PR | Lint, mypy, ~50 core tests |
| Regression | `regression.yml` | Push to main, daily | Full REST + WS + Solana suite |
| Performance | `performance.yml` | After regression passes | 38 benchmarks + Locust load |

Known transient failure patterns (from FINDINGS.md):
- **HTTP 503** -- server temporarily unavailable (retry handles this)
- **HTTP 429** -- rate limiting on POST /orders (F-PERF-002)
- **HTTP 500** -- GET /snapshot under load (F-PERF-003)
- **XPASS** -- intermittent findings passing unexpectedly (strict=False handles this)

## Workflow

### Step 0: Resolve Context

```bash
gh pr view --json number,headRefName,title,url 2>/dev/null || echo "No PR -- direct push"
git branch --show-current
```

### Step 1: Identify Failing Checks

```bash
# For PRs
gh pr checks <PR_NUMBER>

# For direct pushes
gh run list --branch <BRANCH> --limit 10
```

Pick the latest failed run. Record its `RUN_ID`.

### Step 2: Collect Failing Logs

```bash
gh run view <RUN_ID> --log-failed
```

If artifacts are needed:
```bash
gh run download <RUN_ID>
```

### Step 3: Classify the Failure

| Pattern | Classification | Action |
|---------|---------------|--------|
| `HTTP 503` / `InvalidStatus` | Transient server error | Rerun: `gh run rerun <RUN_ID> --failed` |
| `HTTP 429` / `Too many requests` | Rate limiting (F-PERF-002) | Check if test has `skip` on 429; if not, add it |
| `XPASS(strict)` | Intermittent finding passed | Change `strict=True` to `strict=False` |
| `file not found` / `ImportError` | Missing file or bad import | Fix the path or import |
| `ruff format` / `ruff check` | Lint failure | Run `ruff format` and `ruff check --fix` |
| `mypy` error | Type check failure | Fix the type annotation |
| `AssertionError` in functional test | Possible real bug | Investigate -- read FINDINGS.md, check if new |
| `TimeoutError` | Network/server slow | Increase timeout or add retry |

### Step 4: Flake Gate

If classified as transient:
```bash
gh run rerun <RUN_ID> --failed
```

Wait for rerun. If it passes, stop -- no patch needed. Report as flaky.
If it fails again with the same error, proceed to patching.

### Step 5: Apply Minimal Patch

1. Fix only the files directly related to the failure
2. Run the local equivalent to verify:
   ```bash
   ruff check src/ tests/ conftest.py
   ruff format --check src/ tests/ conftest.py
   pytest tests/path/to/failing_test.py -v --reruns 1
   ```
3. Commit and push:
   ```bash
   git add -A
   git commit -m "fix(ci): <short cause>"
   git push
   ```

### Step 6: Monitor Until Green or Escalate

```bash
gh pr checks <PR_NUMBER> --watch
# or
gh run list --branch <BRANCH> --limit 5
```

Escalate if:
- Failure persists after 2 patch attempts
- Failure requires workflow file changes
- Failure involves secrets or permissions
- Failure is a genuine new bug that needs a finding entry

## Output Format

```markdown
## CI Analysis Report

- **Branch:** <branch name>
- **Failing workflow:** <workflow name> + run link
- **Root cause:** <1-2 sentence explanation>
- **Classification:** transient | lint | type-check | known-finding | new-bug
- **Action taken:** rerun | patch | escalate
- **Files changed:** <list>
- **Outcome:** fixed | flaky (rerun passed) | escalated
```
