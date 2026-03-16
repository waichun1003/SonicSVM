"""Tests for REST API error handling and security edge cases.

Validates that the API handles malformed requests, unknown paths,
injection attempts, and method mismatches gracefully without
returning 5xx server errors.
"""

from __future__ import annotations

import pytest

import allure

pytestmark = [pytest.mark.rest]


@allure.feature("REST API")
@allure.story("Error Handling")
class TestErrorCases:
    """Error handling and security edge-case tests."""

    async def test_nonexistent_path_returns_404(self, api_client) -> None:
        """GET to a non-existent path returns 404 Not Found."""
        resp = await api_client.get("/nonexistent-path-that-does-not-exist")
        assert resp.status_code == 404

    async def test_invalid_market_id_no_5xx(self, api_client) -> None:
        """Snapshot with invalid marketId does not cause a server error."""
        resp = await api_client.get("/markets/TOTALLY-INVALID-MARKET/snapshot")
        assert resp.status_code < 500, f"Expected non-5xx, got {resp.status_code}"

    async def test_sql_injection_in_market_id(self, api_client) -> None:
        """SQL injection attempt in marketId does not cause a server error."""
        resp = await api_client.get("/markets/' OR 1=1 --/snapshot")
        assert resp.status_code < 500, f"SQL injection caused {resp.status_code}"

    async def test_xss_in_market_id(self, api_client) -> None:
        """XSS payload in marketId does not cause a server error."""
        resp = await api_client.get("/markets/<script>alert(1)</script>/snapshot")
        assert resp.status_code < 500, f"XSS payload caused {resp.status_code}"

    async def test_path_traversal_in_market_id(self, api_client) -> None:
        """Path traversal attempt in marketId does not cause a server error."""
        resp = await api_client.get("/markets/../../etc/passwd/snapshot")
        assert resp.status_code < 500, f"Path traversal caused {resp.status_code}"

    async def test_head_health_returns_200(self, api_client) -> None:
        """HEAD /health returns 200 with no body."""
        resp = await api_client.request("HEAD", "/health")
        assert resp.status_code == 200

    async def test_extra_query_params_ignored(self, api_client) -> None:
        """Extra query parameters are ignored and do not cause errors."""
        resp = await api_client.get("/health", params={"foo": "bar", "baz": "123"})
        assert resp.status_code == 200

    async def test_invalid_market_returns_4xx_not_just_non5xx(self, api_client) -> None:
        """Invalid marketId should return a proper 4xx client error."""
        resp = await api_client.get("/markets/TOTALLY-INVALID-MARKET/snapshot")
        assert 400 <= resp.status_code < 500, (
            f"Expected 4xx for invalid market, got {resp.status_code}"
        )

    async def test_404_body_contains_error_or_text(self, api_client) -> None:
        """404 response body should contain meaningful error information."""
        resp = await api_client.get("/nonexistent-path-that-does-not-exist")
        assert resp.status_code == 404
        assert len(resp.text) > 0, "404 response body should not be empty"


@allure.feature("REST API")
@allure.story("Error Handling")
class TestCorsHeaders:
    """CORS header validation tests."""

    async def test_options_health_returns_204(self, api_client) -> None:
        """OPTIONS /health returns 204 No Content (CORS preflight)."""
        resp = await api_client.request("OPTIONS", "/health")
        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}"

    async def test_options_includes_allow_methods(self, api_client) -> None:
        """OPTIONS response includes Access-Control-Allow-Methods header."""
        resp = await api_client.request("OPTIONS", "/health")
        allow = resp.headers.get("access-control-allow-methods", "")
        assert "GET" in allow, f"Expected 'GET' in Access-Control-Allow-Methods, got: {allow!r}"

    async def test_cors_allow_origin_on_success(self, api_client) -> None:
        """Successful responses include Access-Control-Allow-Origin header."""
        resp = await api_client.get("/health")
        origin = resp.headers.get("access-control-allow-origin", "")
        assert origin == "*", f"Expected ACAO '*' on /health, got: {origin!r}"

    async def test_cors_allow_origin_on_error(self, api_client) -> None:
        """Error responses also include CORS headers."""
        resp = await api_client.get("/nonexistent")
        origin = resp.headers.get("access-control-allow-origin", "")
        assert origin == "*", f"Expected ACAO '*' on 404, got: {origin!r}"

    async def test_options_markets_returns_204(self, api_client) -> None:
        """OPTIONS /markets returns 204."""
        resp = await api_client.request("OPTIONS", "/markets")
        assert resp.status_code == 204

    async def test_options_stats_returns_204(self, api_client) -> None:
        """OPTIONS /stats returns 204."""
        resp = await api_client.request("OPTIONS", "/stats")
        assert resp.status_code == 204
