"""Pydantic v2 strict models for SMFS API responses."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

# --- REST Models ---


class HealthResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    ok: bool
    serverTime: int | float
    markets: list[str]
    wsUrl: str


class Market(BaseModel):
    model_config = ConfigDict(strict=True)
    marketId: str
    base: str
    quote: str


class MarketsResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    markets: list[Market]


class OrderBookLevel(BaseModel):
    model_config = ConfigDict(strict=True)
    price: int | float
    size: int | float


class Trade(BaseModel):
    model_config = ConfigDict(strict=True)
    tradeId: str
    ts: int | float
    price: int | float
    size: int | float
    side: str

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        if v not in ("buy", "sell"):
            raise ValueError(f"side must be 'buy' or 'sell', got '{v}'")
        return v


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    marketId: str
    ts: int | float
    midPrice: int | float
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    recentTrades: list[Trade]


class OrderRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    marketId: str
    side: str
    type: str
    size: int | float
    price: int | float | None = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    accepted: bool
    orderId: str
    ts: int | float


class MarketStats(BaseModel):
    model_config = ConfigDict(strict=True)
    bookUpdatesPerSecond: int | float
    tradesPerSecond: int | float
    currentSeq: int | float


class StatsResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    markets: dict[str, MarketStats]
    connectedClients: int | float


class ErrorResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    error: str


# --- WebSocket Market Feed Models ---


class WsHello(BaseModel):
    model_config = ConfigDict(strict=True)
    type: str
    serverTime: int | float
    marketId: str


class WsBookDelta(BaseModel):
    model_config = ConfigDict(strict=True)
    type: str
    ts: int | float
    seq: int | float
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]


class WsTrade(BaseModel):
    model_config = ConfigDict(strict=True)
    type: str
    ts: int | float
    tradeId: str
    price: int | float
    size: int | float
    side: str

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        if v not in ("buy", "sell"):
            raise ValueError(f"side must be 'buy' or 'sell', got '{v}'")
        return v


class WsPong(BaseModel):
    model_config = ConfigDict(strict=True)
    type: str
    ts: int | float


class WsReset(BaseModel):
    model_config = ConfigDict(strict=True)
    type: str
    reason: str
    ts: int | float


# --- Solana Stream Models ---


class StreamFilters(BaseModel):
    """Subscription filters reported in stream_hello."""

    model_config = ConfigDict(strict=True)

    programs: list[str] = []
    accounts: list[str] = []


class WsStreamHello(BaseModel):
    model_config = ConfigDict(strict=True)
    type: str
    serverTime: int | float
    filters: StreamFilters | None = None


class SolanaTransaction(BaseModel):
    """Model for Solana transaction messages from /ws/stream."""

    model_config = ConfigDict(strict=True)
    type: str
    slot: int
    signature: str
    blockTime: int | None = None
    fee: int
    programIds: list[str] = []

    @field_validator("fee")
    @classmethod
    def fee_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"fee must be non-negative, got {v}")
        return v

    @field_validator("signature")
    @classmethod
    def validate_signature(cls, v: str) -> str:
        from smfs_qa.solana import is_valid_solana_signature

        if not is_valid_solana_signature(v):
            raise ValueError(f"Invalid Solana signature (failed solders Ed25519 validation): {v}")
        return v
