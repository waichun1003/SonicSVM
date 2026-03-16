"""Tests for API documentation endpoints.

Validates that /docs serves the API explorer and /openapi.json serves the spec.
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.client import SMFSClient

pytestmark = [pytest.mark.rest]


@allure.feature("REST API")
@allure.story("API Documentation")
class TestDocsEndpoints:
    """API documentation endpoint availability tests."""

    async def test_docs_returns_200(self, api_client: SMFSClient) -> None:
        """GET /docs returns 200 with interactive API documentation (Scalar UI)."""
        resp = await api_client.get("/docs")
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/html" in content_type, f"Expected HTML docs page, got {content_type}"

    async def test_openapi_json_returns_200(self, api_client: SMFSClient) -> None:
        """GET /openapi.json returns 200 with the OpenAPI 3.1 specification."""
        resp = await api_client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("openapi", "").startswith("3."), (
            f"Expected OpenAPI 3.x spec, got version {data.get('openapi')}"
        )
        assert "paths" in data, "OpenAPI spec should contain paths"
