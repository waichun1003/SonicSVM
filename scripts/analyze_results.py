#!/usr/bin/env python3
"""Analyze JUnit XML test results and classify failures.

Parses test results, classifies each failure by root cause, cross-references
against known findings, and outputs a markdown report suitable for GitHub
Actions Job Summary or PR comments.

Usage:
    python scripts/analyze_results.py results/*.xml
    python scripts/analyze_results.py results/live.xml --findings FINDINGS.md
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

KNOWN_FINDING_PATTERNS = {
    "503": ("Transient", "Server returned 503 -- transient unavailability"),
    "429": ("Rate Limited", "Known rate limiting (F-PERF-002)"),
    "Too many requests": ("Rate Limited", "Known rate limiting (F-PERF-002)"),
    "XPASS(strict)": ("XPASS", "Intermittent finding passed unexpectedly"),
    "TimeoutError": ("Transient", "Network timeout -- likely transient"),
    "ConnectionRefused": ("Infrastructure", "Server unreachable"),
    "InvalidStatus": ("Transient", "WebSocket connection rejected (likely 503)"),
    "ruff": ("Lint", "Code formatting or lint issue"),
    "mypy": ("Type Check", "Type annotation error"),
    "ValidationError": ("Schema Change", "Pydantic model mismatch -- API may have changed"),
    "float": ("Known Finding", "Floating-point artifact (F-REST-001/F-WS-002/F-WS-003)"),
    "crossed": ("Known Finding", "Crossed order book (F-REST-002)"),
    "marketId": ("Known Finding", "Invalid marketId accepted (F-WS-001)"),
    "text/plain": ("Known Finding", "Error response format (F-REST-004)"),
    "bimodal": ("Known Finding", "Stats bimodal latency (F-PERF-001)"),
    "500": ("Known Finding", "Snapshot 500 under load (F-PERF-003)"),
}


def classify_failure(test_name: str, message: str) -> tuple[str, str]:
    """Classify a test failure by matching error patterns."""
    msg_lower = message.lower()
    for pattern, (category, description) in KNOWN_FINDING_PATTERNS.items():
        if pattern.lower() in msg_lower:
            return category, description
    return "New Bug", f"Unrecognized failure in {test_name} -- investigate"


def parse_junit_xml(path: Path) -> dict:
    """Parse a JUnit XML file and return structured results."""
    tree = ET.parse(path)
    root = tree.getroot()

    results = {"passed": 0, "failed": 0, "xfail": 0, "skipped": 0, "errors": 0, "failures": []}

    for tc in root.iter("testcase"):
        name = tc.get("name", "unknown")
        classname = tc.get("classname", "")

        failure = tc.find("failure")
        error = tc.find("error")
        skipped = tc.find("skipped")

        if failure is not None:
            results["failed"] += 1
            msg = failure.get("message", "")[:300]
            category, description = classify_failure(name, msg)
            results["failures"].append(
                {
                    "test": name,
                    "class": classname,
                    "message": msg,
                    "category": category,
                    "description": description,
                }
            )
        elif error is not None:
            results["errors"] += 1
        elif skipped is not None:
            if "xfail" in skipped.get("type", ""):
                results["xfail"] += 1
            else:
                results["skipped"] += 1
        else:
            results["passed"] += 1

    return results


def extract_finding_ids(findings_path: Path) -> set[str]:
    """Extract finding IDs (F-XXX-NNN) from FINDINGS.md."""
    if not findings_path.exists():
        return set()
    text = findings_path.read_text()
    return set(re.findall(r"F-[A-Z]+-\d{3}", text))


def generate_report(results: dict, finding_ids: set[str]) -> str:
    """Generate a markdown failure analysis report."""
    total = (
        results["passed"] + results["failed"] + results["xfail"]
        + results["skipped"] + results["errors"]
    )
    lines = [
        "## Test Failure Analysis",
        "",
        f"**Total:** {total} | "
        f"**Passed:** {results['passed']} | "
        f"**Failed:** {results['failed']} | "
        f"**Errors:** {results['errors']} | "
        f"**xFail:** {results['xfail']} | "
        f"**Skipped:** {results['skipped']}",
        "",
    ]

    if not results["failures"]:
        lines.append("All tests passed. No failures to analyze.")
        return "\n".join(lines)

    matched_findings = set()
    for f in results["failures"]:
        for fid in finding_ids:
            if fid.lower() in f["description"].lower() or fid.lower() in f["message"].lower():
                matched_findings.add(fid)

    if matched_findings:
        lines.append(f"**Known findings matched:** {', '.join(sorted(matched_findings))}")
        lines.append("")

    lines.extend(
        [
            "### Failures by Category",
            "",
            "| # | Test | Category | Description | Action |",
            "|---|------|----------|-------------|--------|",
        ]
    )

    categories: dict[str, int] = {}
    for i, f in enumerate(results["failures"], 1):
        cat = f["category"]
        categories[cat] = categories.get(cat, 0) + 1

        if cat == "Transient":
            action = "Rerun workflow"
        elif cat == "Rate Limited":
            action = "Expected (F-PERF-002)"
        elif cat == "Known Finding":
            action = "Expected -- no action"
        elif cat == "XPASS":
            action = "Update xfail marker"
        elif cat == "Lint":
            action = "Run `ruff format`"
        elif cat == "Type Check":
            action = "Fix type annotation"
        elif cat == "Schema Change":
            action = "Investigate API change"
        else:
            action = "Investigate -- may be new finding"

        lines.append(f"| {i} | `{f['test']}` | {cat} | {f['description'][:60]} | {action} |")

    lines.extend(
        [
            "",
            "### Summary by Category",
            "",
            "| Category | Count | Severity |",
            "|----------|-------|----------|",
        ]
    )

    severity_map = {
        "Transient": "Low",
        "Rate Limited": "Low",
        "Known Finding": "Info",
        "XPASS": "Info",
        "Lint": "Medium",
        "Type Check": "Medium",
        "Schema Change": "High",
        "Infrastructure": "High",
        "New Bug": "High",
    }

    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        sev = severity_map.get(cat, "Medium")
        lines.append(f"| {cat} | {count} | {sev} |")

    new_bugs = [f for f in results["failures"] if f["category"] == "New Bug"]
    if new_bugs:
        lines.extend(
            [
                "",
                "### Potential New Findings",
                "",
                "These failures do not match any known pattern and may represent new bugs:",
                "",
            ]
        )
        for f in new_bugs:
            lines.append(f"- **{f['test']}**: {f['message'][:200]}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze JUnit XML test results")
    parser.add_argument("xml_files", nargs="+", help="JUnit XML file(s) to analyze")
    parser.add_argument(
        "--findings",
        default="FINDINGS.md",
        help="Path to FINDINGS.md for cross-reference",
    )
    args = parser.parse_args()

    all_results: dict = {
        "passed": 0,
        "failed": 0,
        "xfail": 0,
        "skipped": 0,
        "errors": 0,
        "failures": [],
    }

    for xml_file in args.xml_files:
        path = Path(xml_file)
        if not path.exists():
            print(f"Warning: {xml_file} not found, skipping", file=sys.stderr)
            continue
        r = parse_junit_xml(path)
        for key in ("passed", "failed", "xfail", "skipped", "errors"):
            all_results[key] += r[key]
        all_results["failures"].extend(r["failures"])

    finding_ids = extract_finding_ids(Path(args.findings))
    report = generate_report(all_results, finding_ids)
    print(report)


if __name__ == "__main__":
    main()
