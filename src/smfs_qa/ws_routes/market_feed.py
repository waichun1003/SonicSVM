"""Market feed WebSocket route."""

from __future__ import annotations

from typing import Any

from smfs_qa.schemas import WsBookDelta, WsHello, WsPong, WsTrade
from smfs_qa.ws_client import WSTestClient


class MarketFeedRoute:
    """POM route for the /ws market feed WebSocket."""

    def __init__(self, ws_base_url: str, market_id: str = "BTC-PERP") -> None:
        self.url = f"{ws_base_url}/ws?marketId={market_id}"
        self.market_id = market_id

    def client(self, timeout: float = 10.0) -> WSTestClient:
        return WSTestClient(self.url, timeout=timeout)

    @staticmethod
    def parse_message(msg: dict[str, Any]) -> WsHello | WsBookDelta | WsTrade | WsPong | dict:
        msg_type = msg.get("type")
        if msg_type == "hello":
            return WsHello.model_validate(msg)
        elif msg_type == "book_delta":
            return WsBookDelta.model_validate(msg)
        elif msg_type == "trade":
            return WsTrade.model_validate(msg)
        elif msg_type == "pong":
            return WsPong.model_validate(msg)
        return msg
