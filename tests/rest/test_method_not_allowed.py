"""Tests for HTTP method enforcement on REST endpoints."""

from __future__ import annotations

import pytest

import allure
from smfs_qa.client import SMFSClient

pytestmark = [pytest.mark.rest]


@allure.feature("REST API")
@allure.story("HTTP Method Enforcement")
class TestMethodNotAllowed:
    """HTTP method enforcement tests."""

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("POST", "/health"),
            ("PUT", "/health"),
            ("PATCH", "/health"),
            ("DELETE", "/health"),
            ("PUT", "/markets"),
            ("DELETE", "/stats"),
        ],
    )
    async def test_unsupported_method_returns_4xx(
        self, api_client: SMFSClient, method: str, path: str
    ) -> None:
        """Unsupported HTTP method returns 4xx, not 5xx."""
        resp = await api_client.request(method, path)
        assert 400 <= resp.status_code < 500, (
            f"Expected 4xx for {method} {path}, got {resp.status_code}"
        )
