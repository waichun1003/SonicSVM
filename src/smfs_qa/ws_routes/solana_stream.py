"""Solana transaction stream WebSocket route."""

from __future__ import annotations

from typing import Any

from smfs_qa.schemas import WsStreamHello
from smfs_qa.solana import WELL_KNOWN_PROGRAMS
from smfs_qa.ws_client import WSTestClient


class SolanaStreamRoute:
    """POM route for the /ws/stream Solana transaction stream."""

    def __init__(self, ws_base_url: str) -> None:
        self.url = f"{ws_base_url}/ws/stream"

    def client(self, timeout: float = 10.0) -> WSTestClient:
        return WSTestClient(self.url, timeout=timeout)

    @staticmethod
    def parse_hello(msg: dict[str, Any]) -> WsStreamHello:
        return WsStreamHello.model_validate(msg)

    @staticmethod
    def build_subscribe(
        programs: list[str] | None = None,
        accounts: list[str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": "subscribe"}
        if programs is not None:
            payload["programs"] = programs
        if accounts is not None:
            payload["accounts"] = accounts
        return payload

    @classmethod
    def build_subscribe_system_program(cls) -> dict[str, Any]:
        return cls.build_subscribe(programs=[WELL_KNOWN_PROGRAMS["SYSTEM_PROGRAM"]])

    @classmethod
    def build_subscribe_spl_token(cls) -> dict[str, Any]:
        return cls.build_subscribe(programs=[WELL_KNOWN_PROGRAMS["SPL_TOKEN"]])

    @classmethod
    def build_subscribe_all(cls) -> dict[str, Any]:
        return cls.build_subscribe()
