"""SMFS WebSocket test client with structured QA logging."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from smfs_qa.logger import QALogger


class WSTestClient:
    """Async WebSocket client for SMFS market feed and Solana stream.

    All interactions are logged via QALogger with:
    - Connect/disconnect with URL and close code
    - Every sent and received message (JSON truncated)
    - Message collection summaries
    """

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self.url = url
        self.timeout = timeout
        self._ws: ClientConnection | None = None

    async def connect(self) -> WSTestClient:
        QALogger.log_ws_connect(self.url)
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                self._ws = await websockets.connect(self.url, open_timeout=self.timeout)
                return self
            except websockets.exceptions.InvalidStatus as e:
                last_err = e
                if e.response.status_code == 503 and attempt < 2:
                    QALogger.warn(f"WS connect got 503 (attempt {attempt + 1}/3), retrying...")
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    raise
        raise last_err  # type: ignore[misc]

    async def close(self) -> None:
        if self._ws:
            code = self._ws.close_code
            await self._ws.close()
            QALogger.log_ws_close(self.url, code)
            self._ws = None

    async def __aenter__(self) -> WSTestClient:
        return await self.connect()

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @property
    def ws(self) -> ClientConnection:
        if self._ws is None:
            raise RuntimeError(
                "WebSocket not connected. Use 'async with WSTestClient(...)' context."
            )
        return self._ws

    async def recv_json(self, timeout: float | None = None) -> dict[str, Any]:
        t = timeout or self.timeout
        raw = await asyncio.wait_for(self.ws.recv(), timeout=t)
        data: dict[str, Any] = json.loads(raw)
        QALogger.log_ws_recv(data)
        return data

    async def send_json(self, data: dict[str, Any]) -> None:
        QALogger.log_ws_send(data)
        await self.ws.send(json.dumps(data))

    async def collect_messages(
        self,
        count: int | None = None,
        duration: float | None = None,
        timeout: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Collect messages by count or duration (whichever comes first)."""
        messages: list[dict[str, Any]] = []
        deadline = asyncio.get_running_loop().time() + (duration or timeout)

        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            if count is not None and len(messages) >= count:
                break
            try:
                msg = await self.recv_json(timeout=min(remaining, 5.0))
                messages.append(msg)
            except TimeoutError:
                if duration is not None:
                    break
                if count is not None and len(messages) < count:
                    continue
                break

        QALogger.info(
            f"Collected {len(messages)} messages (requested: count={count}, duration={duration}s)"
        )
        return messages

    async def drain_until(self, msg_type: str, timeout: float = 10.0) -> dict[str, Any]:
        """Receive messages until one of the given type appears."""
        deadline = asyncio.get_running_loop().time() + timeout
        drained = 0
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                QALogger.warn(
                    f"Timeout waiting for '{msg_type}' -- drained {drained} other messages"
                )
                raise TimeoutError(f"No '{msg_type}' message within {timeout}s")
            msg = await self.recv_json(timeout=remaining)
            if msg.get("type") == msg_type:
                return msg
            drained += 1
