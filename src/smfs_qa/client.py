"""SMFS HTTP client with retry logic and structured QA logging."""

from __future__ import annotations

import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from smfs_qa.logger import QALogger


class SMFSClient:
    """Async HTTP client for the Sonic Market Feed Service.

    All requests are logged via QALogger with:
    - Request: method, URL, params, body
    - Response: status code, elapsed time, body (truncated)
    """

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> SMFSClient:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers={"User-Agent": "smfs-qa/1.0 (pytest; httpx)"},
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Use 'async with SMFSClient(...)' context."
            )
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5))
    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        QALogger.log_request("GET", url, **kwargs)
        start = time.perf_counter()
        resp = await self.client.get(path, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        QALogger.log_response("GET", url, resp.status_code, elapsed, resp.text)
        return resp

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5))
    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        QALogger.log_request("POST", url, **kwargs)
        start = time.perf_counter()
        resp = await self.client.post(path, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        QALogger.log_response("POST", url, resp.status_code, elapsed, resp.text)
        return resp

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5))
    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        QALogger.log_request(method, url, **kwargs)
        start = time.perf_counter()
        resp = await self.client.request(method, path, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        QALogger.log_response(method, url, resp.status_code, elapsed, resp.text)
        return resp
