
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

class RiskSettings(BaseModel):
    max_orders_per_min: int = Field(..., ge=0)
    daily_loss_limit: float
    max_position_qty: float
    max_notional: float

class RiskState(BaseModel):
    pnl_day: Optional[float] = None
    blocked: Optional[bool] = None

class RiskResponse(BaseModel):
    ok: bool
    risk: Optional[RiskSettings] = None
    state: Optional[RiskState] = None

class Position(BaseModel):
    id: Optional[str] = None
    symbol: str
    side: Literal["buy", "sell"]
    qty: float
    price: Optional[float] = None
    mode: Optional[str] = None
    ts: Optional[float] = None

class PositionsResponse(BaseModel):
    ok: bool
    positions: List[Position] = []

class Trade(BaseModel):
    ts: Optional[float] = None
    kind: Optional[str] = "paper"
    symbol: Optional[str] = None
    side: Optional[str] = None
    qty: Optional[float] = None
    extra: Dict[str, Any] = {}

class TradesResponse(BaseModel):
    ok: bool
    trades: List[Trade] = []

class TickerLast(BaseModel):
    ok: bool
    last: Optional[Dict[str, Any]] = None

class MetricsResponse(BaseModel):
    __root__: Dict[str, Any]
