"""Tests for error response Content-Type consistency.

Documents finding F-REST-004: error responses use text/plain Content-Type
instead of the expected application/json.
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.client import SMFSClient

pytestmark = [pytest.mark.rest]

ERROR_PATHS = [
    "/nonexistent-path",
    "/markets/BTC-PERP/orderbook",
    "/markets/BTC-PERP/orders",
]


@allure.feature("REST API")
@allure.story("Error Response Format")
class TestErrorFormat:
    """Error response format consistency tests."""

    @pytest.mark.xfail(
        reason="F-REST-004: Error responses use text/plain instead of application/json",
        strict=True,
    )
    @pytest.mark.finding
    @pytest.mark.parametrize("path", ERROR_PATHS)
    async def test_error_content_type_is_json(self, api_client: SMFSClient, path: str) -> None:
        """Error responses should have application/json Content-Type."""
        resp = await api_client.get(path)
        content_type = resp.headers.get("content-type", "")
        assert "application/json" in content_type, (
            f"Expected application/json for {path}, got '{content_type}'"
        )
