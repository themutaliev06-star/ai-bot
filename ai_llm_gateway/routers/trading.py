
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import httpx

from ..schemas import (
    RiskSettings, RiskResponse, PositionsResponse, TradesResponse,
    MetricsResponse, TickerLast
)

router = APIRouter(tags=["trading"])

EXECUTOR_BASE   = "http://127.0.0.1:8600"
BACKTESTER_BASE = "http://127.0.0.1:8900"
INGESTOR_BASE   = "http://127.0.0.1:8700"
AI_BASE         = "http://127.0.0.1:8750"

timeout = httpx.Timeout(20.0, connect=5.0)

@router.get("/api/trading/positions", response_model=PositionsResponse)
async def api_positions():
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"{EXECUTOR_BASE}/positions")
        if r.status_code == 200:
            return r.json()
        return {"ok": False, "positions": []}

@router.get("/api/trading/trades", response_model=TradesResponse)
async def api_trades(
    limit: int = Query(50, ge=1, le=500),
    source: str = Query("executor", pattern="^(executor|backtester)$")
):
    async with httpx.AsyncClient(timeout=timeout) as client:
        if source == "executor":
            r = await client.get(f"{EXECUTOR_BASE}/trades", params={"limit": limit})
            if r.status_code == 200:
                try:
                    return r.json()
                except Exception:
                    pass
            r_pos = await client.get(f"{EXECUTOR_BASE}/positions")
            if r_pos.status_code == 200:
                js = r_pos.json() or {}
                pos = js.get("positions") or []
                trades = [{
                    "ts": p.get("ts"),
                    "kind": "paper",
                    "symbol": p.get("symbol"),
                    "side": p.get("side"),
                    "qty": p.get("qty"),
                    "extra": {
                        "px@trade": p.get("price"),
                        "px@now": None,
                        "dpx": None
                    }
                } for p in pos][-limit:]
                return {"ok": True, "trades": trades}
            return {"ok": True, "trades": []}
        else:
            r = await client.get(f"{BACKTESTER_BASE}/trades", params={"limit": limit})
            if r.status_code == 200:
                try:
                    return r.json()
                except Exception:
                    pass
            return {"ok": True, "trades": []}

@router.get("/api/trading/risk", response_model=RiskResponse)
async def api_risk_get():
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"{EXECUTOR_BASE}/risk")
        return JSONResponse(r.json(), status_code=r.status_code)

@router.post("/api/trading/risk", response_model=RiskResponse)
async def api_risk_set(body: RiskSettings):
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{EXECUTOR_BASE}/risk", json=body.model_dump())
        return JSONResponse(r.json(), status_code=r.status_code)

@router.post("/api/trading/risk/unblock", response_model=RiskResponse)
async def api_risk_unblock():
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{EXECUTOR_BASE}/risk/unblock")
        return JSONResponse(r.json(), status_code=r.status_code)

@router.get("/api/trading/metrics", response_model=MetricsResponse)
async def api_metrics():
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"{AI_BASE}/metrics")
        return JSONResponse(r.json(), status_code=r.status_code)

@router.get("/api/trading/ticker", response_model=TickerLast)
async def api_ticker(symbol: str = Query("BTCUSDT")):
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"{INGESTOR_BASE}/last", params={"symbol": symbol})
        return JSONResponse(r.json(), status_code=r.status_code)

@router.get("/api/trading/status")
async def api_status():
    out = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
        for name, url in [
            ("executor",   f"{EXECUTOR_BASE}/health"),
            ("backtester", f"{BACKTESTER_BASE}/health"),
            ("ingestor",   f"{INGESTOR_BASE}/health"),
            ("ai",         f"{AI_BASE}/health"),
        ]:
            ok = False
            try:
                r = await client.get(url)
                ok = (r.status_code == 200)
            except Exception:
                ok = False
            out.append({"name": name, "ok": ok})
    return {"ok": True, "services": out}
