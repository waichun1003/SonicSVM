#!/usr/bin/env python3
"""Analyze CI workflow failures from GitHub Actions job logs.

Fallback analyzer used when JUnit XML artifacts are not available
(e.g., lint/typecheck failures that prevent tests from running).

Fetches the failed workflow run's job logs via the `gh` CLI and
classifies the failure by matching known error patterns.

Requires environment variables:
    GH_TOKEN      - GitHub token (set by Actions)
    RUN_ID        - The failed workflow run ID
    WORKFLOW_NAME - Name of the failed workflow
    RUN_URL       - URL to the failed workflow run
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

FAILURE_PATTERNS: list[tuple[str, str, str, str]] = [
    # (pattern, category, description, action)
    (r"ruff check.*exit code 1", "Lint", "ruff check failed", "Run `ruff check --fix`"),
    (r"ruff format.*exit code 1", "Lint", "ruff format failed", "Run `ruff format`"),
    (r"Would reformat: (.+)", "Lint", "File needs reformatting", "Run `ruff format`"),
    (r"Found \d+ error", "Lint", "ruff lint errors detected", "Run `ruff check --fix`"),
    (r"W\d{3} \[", "Lint", "ruff warning (e.g., missing newline)", "Run `ruff format`"),
    (r"mypy.*exit code 1", "Type Check", "mypy type check failed", "Fix type annotations"),
    (r"error: .+\[(\w+-\w+)\]", "Type Check", "mypy error", "Fix type annotations"),
    (r"FAILED tests/", "Test Failure", "Test(s) failed", "Check test output"),
    (r"(\d+) failed", "Test Failure", "Test failures detected", "Check test output"),
    (r"TimeoutError|timed out", "Timeout", "Timed out", "Increase timeout or investigate"),
    (r"exit code 1", "General Failure", "Step exited with error", "Check step output"),
]


def fetch_failed_jobs(run_id: str) -> list[dict]:
    """Fetch job details for a workflow run via gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/${{GITHUB_REPOSITORY}}/actions/runs/{run_id}/jobs"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            repo = os.environ.get("GITHUB_REPOSITORY", "")
            result = subprocess.run(
                ["gh", "api", f"repos/{repo}/actions/runs/{run_id}/jobs"],
                capture_output=True,
                text=True,
                timeout=30,
            )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            return [j for j in data.get("jobs", []) if j.get("conclusion") == "failure"]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Warning: Could not fetch jobs: {e}", file=sys.stderr)
    return []


def fetch_job_logs(job_id: int) -> str:
    """Fetch logs for a specific job via gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "run", "view", "--job", str(job_id), "--log-failed"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return result.stdout[-5000:]
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Warning: Could not fetch logs for job {job_id}: {e}", file=sys.stderr)
    return ""


def classify_logs(logs: str) -> list[dict]:
    """Match log content against known failure patterns."""
    matches = []
    seen = set()
    for pattern, category, description, action in FAILURE_PATTERNS:
        for m in re.finditer(pattern, logs, re.IGNORECASE):
            key = (category, description)
            if key not in seen:
                seen.add(key)
                detail = m.group(0)[:120]
                matches.append(
                    {
                        "category": category,
                        "description": description,
                        "action": action,
                        "detail": detail,
                    }
                )
    return matches


def extract_failed_steps(job: dict) -> list[dict]:
    """Extract failed step names from a job's steps."""
    return [
        {"name": s["name"], "conclusion": s["conclusion"]}
        for s in job.get("steps", [])
        if s.get("conclusion") == "failure"
    ]


def generate_report(
    workflow_name: str,
    run_url: str,
    failed_jobs: list[dict],
    classifications: list[dict],
) -> str:
    """Generate a markdown analysis report."""
    lines: list[str] = []

    if not failed_jobs:
        lines.append(
            f"Could not fetch job details. Check the [workflow run logs]({run_url}) directly."
        )
        return "\n".join(lines)

    lines.append("### Failed Jobs")
    lines.append("")

    for job in failed_jobs:
        job_name = job.get("name", "unknown")
        job_url = job.get("html_url", "")
        lines.append(f"**Job:** [{job_name}]({job_url})")
        lines.append("")

        failed_steps = extract_failed_steps(job)
        if failed_steps:
            lines.append("| Step | Status |")
            lines.append("|------|--------|")
            for step in failed_steps:
                lines.append(f"| {step['name']} | {step['conclusion']} |")
            lines.append("")

    if classifications:
        lines.append("### Failure Classification")
        lines.append("")
        lines.append("| # | Category | Description | Recommended Action |")
        lines.append("|---|----------|-------------|-------------------|")
        for i, c in enumerate(classifications, 1):
            lines.append(f"| {i} | {c['category']} | {c['description']} | {c['action']} |")
        lines.append("")

        lines.append("### Matched Log Excerpts")
        lines.append("")
        for c in classifications:
            lines.append(f"- **{c['category']}**: `{c['detail']}`")
        lines.append("")

    severity_map = {
        "Lint": "Low",
        "Type Check": "Medium",
        "Test Failure": "High",
        "Timeout": "Medium",
        "General Failure": "Medium",
    }

    categories: dict[str, int] = {}
    for c in classifications:
        cat = c["category"]
        categories[cat] = categories.get(cat, 0) + 1

    if categories:
        lines.append("### Summary")
        lines.append("")
        lines.append("| Category | Count | Severity |")
        lines.append("|----------|-------|----------|")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            sev = severity_map.get(cat, "Medium")
            lines.append(f"| {cat} | {count} | {sev} |")

    return "\n".join(lines)


def main() -> None:
    run_id = os.environ.get("RUN_ID", "")
    workflow_name = os.environ.get("WORKFLOW_NAME", "Unknown")
    run_url = os.environ.get("RUN_URL", "")

    if not run_id:
        print("Error: RUN_ID environment variable not set", file=sys.stderr)
        sys.exit(1)

    failed_jobs = fetch_failed_jobs(run_id)

    all_classifications: list[dict] = []
    for job in failed_jobs:
        job_id = job.get("id")
        if job_id:
            logs = fetch_job_logs(job_id)
            if logs:
                all_classifications.extend(classify_logs(logs))

    report = generate_report(workflow_name, run_url, failed_jobs, all_classifications)
    print(report)


if __name__ == "__main__":
    main()
