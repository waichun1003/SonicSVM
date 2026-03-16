"""QA logging utilities with console output and Allure integration.

Provides:
- Console PASS/FAIL logging for every assertion
- Allure step integration for rich HTML reports
- Automatic failure detail capture (response body, headers)
- Text log attachment to Allure on test completion
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import UTC, datetime
from io import StringIO
from typing import Any

import allure

_LEVEL_MAP = {
    "PASS": logging.INFO,
    "FAIL": logging.WARNING,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "STEP": logging.INFO,
    "ERR": logging.ERROR,
}

logger = logging.getLogger("smfs_qa")

if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.DEBUG)


class QALogger:
    """Test assertion helpers with console logging and Allure integration.

    Usage:
        from smfs_qa.logger import QALogger

        QALogger.assert_status(resp, 200, "GET /health")
        QALogger.assert_equal(data["ok"], True, "health.ok")
        QALogger.info("Custom message")
    """

    _buffer = StringIO()

    @classmethod
    def _ts(cls) -> str:
        return datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3]

    @classmethod
    def _log(cls, level: str, message: str) -> None:
        line = f"[{cls._ts()}] {level:<4} | {message}"
        cls._buffer.write(line + "\n")
        py_level = _LEVEL_MAP.get(level, logging.INFO)
        logger.log(py_level, line)

    @classmethod
    def reset(cls) -> None:
        """Reset the log buffer. Called at test setup."""
        cls._buffer = StringIO()

    @classmethod
    def flush_to_allure(cls, name: str = "QA Log") -> None:
        """Attach the accumulated log buffer to the Allure report."""
        content = cls._buffer.getvalue()
        if content.strip():
            allure.attach(content, name=name, attachment_type=allure.attachment_type.TEXT)

    # --- Assertions ---

    @classmethod
    def assert_status(cls, response: Any, expected: int, msg: str = "") -> None:
        """Assert HTTP status code and log the result."""
        actual = response.status_code
        endpoint = msg or "endpoint"
        if actual == expected:
            cls._log("PASS", f"HTTP {actual} == {expected} ({endpoint})")
        else:
            cls._log("FAIL", f"HTTP {actual} != {expected} ({endpoint})")
            cls._log("ERR", f"  Response body: {response.text[:500]}")
            cls._log(
                "ERR",
                f"  Headers: {dict(response.headers)}",
            )
        with allure.step(f"Assert HTTP {expected} on {endpoint} (got {actual})"):
            assert actual == expected, (
                f"Expected HTTP {expected}, got {actual} on {endpoint}\n"
                f"Body: {response.text[:500]}"
            )

    @classmethod
    def assert_equal(cls, actual: Any, expected: Any, label: str = "") -> None:
        if actual == expected:
            cls._log("PASS", f"{label}: {actual!r} == {expected!r}")
        else:
            cls._log("FAIL", f"{label}: {actual!r} != {expected!r}")
        with allure.step(f"Assert {label}: {actual!r} == {expected!r}"):
            assert actual == expected, f"{label}: expected {expected!r}, got {actual!r}"

    @classmethod
    def assert_true(
        cls, condition: bool, pass_msg: str = "", fail_msg: str = ""
    ) -> None:
        label = pass_msg if condition else (fail_msg or pass_msg)
        if condition:
            cls._log("PASS", label)
        else:
            cls._log("FAIL", label)
        with allure.step(f"Assert: {label}"):
            assert condition, f"Assertion failed: {fail_msg or pass_msg}"

    @classmethod
    def assert_in(cls, item: Any, container: Any, label: str = "") -> None:
        found = item in container
        if found:
            cls._log("PASS", f"{label}: {item!r} found")
        else:
            cls._log("FAIL", f"{label}: {item!r} not in {container!r}")
        with allure.step(f"Assert {label}: {item!r} in container"):
            assert found, f"{label}: {item!r} not in {container!r}"

    @classmethod
    def assert_less_than(cls, actual: float, threshold: float, label: str = "") -> None:
        if actual < threshold:
            cls._log("PASS", f"{label}: {actual:.2f} < {threshold:.2f}")
        else:
            cls._log("FAIL", f"{label}: {actual:.2f} >= {threshold:.2f}")
        with allure.step(f"Assert {label}: {actual:.2f} < {threshold:.2f}"):
            assert actual < threshold, (
                f"{label}: {actual:.2f} exceeds threshold {threshold:.2f}"
            )

    # --- Logging ---

    @classmethod
    def info(cls, message: str) -> None:
        cls._log("INFO", message)

    @classmethod
    def warn(cls, message: str) -> None:
        cls._log("WARN", message)

    @classmethod
    def step(cls, description: str) -> None:
        cls._log("STEP", description)
        allure.dynamic.description(description)

    @classmethod
    def log_request(cls, method: str, url: str, **kwargs: Any) -> None:
        cls._log("INFO", f">>> {method} {url}")
        if kwargs.get("params"):
            cls._log("INFO", f"    Params: {kwargs['params']}")
        if kwargs.get("json"):
            cls._log("INFO", f"    Body: {json.dumps(kwargs['json'])[:300]}")

    @classmethod
    def log_response(
        cls,
        method: str,
        url: str,
        status: int,
        elapsed_ms: float,
        body: str = "",
    ) -> None:
        cls._log("INFO", f"<<< {status} {method} {url} ({elapsed_ms:.0f}ms)")
        if body:
            cls._log("INFO", f"    Body: {body[:300]}")

    @classmethod
    def log_ws_connect(cls, url: str) -> None:
        cls._log("INFO", f"WS CONNECT {url}")

    @classmethod
    def log_ws_close(cls, url: str, code: int | None = None) -> None:
        code_str = f" (code={code})" if code is not None else ""
        cls._log("INFO", f"WS CLOSE   {url}{code_str}")

    @classmethod
    def log_ws_send(cls, data: dict[str, Any]) -> None:
        cls._log("INFO", f"WS >>> {json.dumps(data, separators=(',', ':'))[:200]}")

    @classmethod
    def log_ws_recv(cls, data: dict[str, Any]) -> None:
        compact = json.dumps(data, separators=(",", ":"))
        if len(compact) > 200:
            compact = compact[:200] + "..."
        cls._log("INFO", f"WS <<< {compact}")

    @classmethod
    def log_failure(cls, test_name: str, error: Exception) -> None:
        """Log a test failure with traceback and attach to Allure."""
        cls._log("FAIL", f"TEST FAILED: {test_name}")
        cls._log("ERR", f"  Error: {error}")
        tb = traceback.format_exc()
        if tb and "NoneType" not in tb:
            cls._log("ERR", f"  Traceback:\n{tb}")
        allure.attach(
            f"Error: {error}\n\nTraceback:\n{tb}",
            name=f"Failure: {test_name}",
            attachment_type=allure.attachment_type.TEXT,
        )

    # --- Attachments ---

    @classmethod
    def attach_json(cls, data: Any, name: str = "response") -> None:
        allure.attach(
            json.dumps(data, indent=2),
            name=name,
            attachment_type=allure.attachment_type.JSON,
        )

    @classmethod
    def attach_text(cls, text: str, name: str = "details") -> None:
        allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)
