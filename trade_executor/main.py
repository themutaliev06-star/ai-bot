from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import os, json, time, threading, httpx

app = FastAPI(title="Trade Executor (paper/live) + Risk", version="0.4.0")

ROOT = os.path.dirname(__file__)
SETTINGS_FILE = os.path.join(ROOT, "settings.json")
RISK_FILE = os.path.join(ROOT, "risk.json")
STATE_FILE = os.path.join(ROOT, "risk_state.json")

# send alerts via gateway proxy (single egress)
ALERT_HOOK = os.environ.get("ALERT_HOOK", "http://127.0.0.1:8800/proxy/alerts/notify")

_positions: List[Dict[str, Any]] = []
_balance = {"paper": 10000.0, "live": 0.0}

# keep trade history in memory and on disk
HISTORY_FILE = os.path.join(ROOT, "trades.json")
_history: List[Dict[str, Any]] = []

def _load_history():
    """Load trade history from disk into memory."""
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                _history.clear()
                _history.extend(data)
    except Exception:
        pass

def _save_history():
    """Persist trade history to disk."""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# defaults
_settings: Dict[str, Any] = {"mode": "paper", "max_risk": 0.02}
_risk: Dict[str, Any] = {
    "max_orders_per_min": 30,
    "daily_loss_limit": 200.0,   # absolute amount
    "max_position_qty": 1.0,     # per order hard cap
    "max_notional": 2000.0       # notional cap (price * qty), 0 = ignore
}
_state: Dict[str, Any] = {
    "day": str(date.today()),
    "orders_last_min": [],   # timestamps
    "pnl_day": 0.0,
    "blocked": False,
    "block_reason": ""
}

def _load_json(p, default):
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
            if isinstance(d, dict):
                default.update(d)
    except Exception:
        pass

def _save_json(p, d):
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass

def load_all():
    _load_json(SETTINGS_FILE, _settings)
    _load_json(RISK_FILE, _risk)
    _load_json(STATE_FILE, _state)
    # load history lazily on startup
    _load_history()
    # reset day if needed
    if _state.get("day") != str(date.today()):
        _state["day"] = str(date.today())
        _state["pnl_day"] = 0.0
        _state["orders_last_min"] = []
        _state["blocked"] = False
        _state["block_reason"] = ""
        _save_json(STATE_FILE, _state)

def _alert(level: str, message: str, extra: Dict[str, Any] = None):
    payload = {"channel": "log", "level": level, "message": message}
    if extra:
        payload.update({"extra": extra})
    def _send():
        try:
            with httpx.Client(timeout=3) as c:
                c.post(ALERT_HOOK, json=payload)
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()

load_all()

class Order(BaseModel):
    symbol: str
    side: str
    qty: float
    price: Optional[float] = None

@app.get("/health")
def health():
    return {"ok": True, "name": "trade_executor", "version": "0.4.0"}

@app.get("/trades")
def trades(limit: int = 100):
    """Return recent executed trades from the history.

    Optional query parameter `limit` controls how many latest trades to return.
    """
    _load_history()
    # ensure positive integer limit
    try:
        limit = int(limit)
    except Exception:
        limit = 100
    if limit <= 0:
        limit = 100
    # slice from the end (most recent first)
    if limit >= len(_history):
        out = list(_history)
    else:
        out = _history[-limit:]
    return {"ok": True, "trades": out}

@app.get("/positions")
def positions():
    """
    Compute open positions based on trade history.

    A position is represented by its symbol, net quantity and
    average entry price. Buys contribute positively to quantity
    while sells contribute negatively. The average price is
    calculated as the weighted average of executed trades. If
    the net quantity becomes zero the average price is omitted.
    
    Returns a list of positions instead of the raw order list.
    """
    # ensure history is up to date
    _load_history()
    exposures: Dict[str, Dict[str, float]] = {}
    # accumulate quantity and cost per symbol
    for entry in _history:
        sym = entry.get("symbol")
        side = (entry.get("side") or "").lower()
        qty = float(entry.get("qty") or 0.0)
        # price may be None (market order); treat as zero in cost
        price = entry.get("price")
        # if price is None or not a number, use 0 for cost accumulation
        try:
            cost_price = float(price) if price is not None else 0.0
        except Exception:
            cost_price = 0.0
        # positive qty for buys, negative for sells
        sign = 1.0 if side == "buy" else -1.0
        if not sym:
            continue
        pos = exposures.setdefault(sym, {"qty": 0.0, "total_cost": 0.0})
        pos["qty"] += sign * qty
        # accumulate cost; cost price multiplied by signed qty
        pos["total_cost"] += sign * qty * cost_price
    # compute average price per symbol
    result = []
    for sym, data in exposures.items():
        qty = data.get("qty", 0.0)
        total_cost = data.get("total_cost", 0.0)
        avg_price = None
        if abs(qty) > 1e-8:
            avg_price = total_cost / qty
        result.append({"symbol": sym, "qty": qty, "avg_price": avg_price})
    return {"ok": True, "positions": result}

@app.get("/balance")
def balance():
    load_all()
    mode = _settings.get("mode", "paper")
    return {"ok": True, "mode": mode, "equity": _balance.get(mode, 0.0)}

@app.get("/settings")
def get_settings():
    load_all()
    return {"ok": True, "settings": _settings}

@app.post("/settings")
def set_settings(new: Dict[str, Any]):
    _settings.update(new or {})
    _save_json(SETTINGS_FILE, _settings)
    return {"ok": True, "settings": _settings}

@app.get("/risk")
def get_risk():
    load_all()
    return {"ok": True, "risk": _risk}

@app.post("/risk")
def set_risk(new: Dict[str, Any]):
    _risk.update({k:v for k,v in (new or {}).items() if v is not None})
    _save_json(RISK_FILE, _risk)
    return {"ok": True, "risk": _risk}

@app.get("/risk_state")
def risk_state():
    load_all()
    # prune window
    t = time.time()
    _state["orders_last_min"] = [x for x in _state.get("orders_last_min", []) if t - x < 60]
    return {"ok": True, "state": _state}

@app.post("/risk_reset")
def risk_reset():
    load_all()
    _state["blocked"] = False
    _state["block_reason"] = ""
    _save_json(STATE_FILE, _state)
    _alert("info", "risk unblocked by user")
    return {"ok": True, "state": _state}

class RiskStatePatch(BaseModel):
    pnl_day: Optional[float] = None
    blocked: Optional[bool] = None
    block_reason: Optional[str] = None

@app.post("/risk_set_state")
def risk_set_state(p: RiskStatePatch):
    load_all()
    if p.pnl_day is not None:
        _state["pnl_day"] = float(p.pnl_day)
    if p.blocked is not None:
        _state["blocked"] = bool(p.blocked)
    if p.block_reason is not None:
        _state["block_reason"] = p.block_reason
    _save_json(STATE_FILE, _state)
    _alert("info", "risk state patched", {"state": _state})
    return {"ok": True, "state": _state}

def _enforce_risk(order: Order) -> Optional[Dict[str, Any]]:
    # reset day if date changed
    if _state.get("day") != str(date.today()):
        _state["day"] = str(date.today())
        _state["pnl_day"] = 0.0
        _state["orders_last_min"] = []
        _state["blocked"] = False
        _state["block_reason"] = ""

    # global block
    if _state.get("blocked"):
        return {"ok": False, "code": "RISK_BLOCKED", "reason": _state.get("block_reason","")}

    # qty cap
    if _risk.get("max_position_qty", 0) and order.qty > _risk["max_position_qty"]:
        _alert("warn", "risk violation: qty cap", {"qty": order.qty, "cap": _risk["max_position_qty"]})
        return {"ok": False, "code":"RISK_QTY_CAP", "reason": f"qty>{_risk['max_position_qty']}"}

    # notional cap (price must be provided; if not — skip)
    if _risk.get("max_notional", 0) and order.price:
        if order.qty * float(order.price) > _risk["max_notional"]:
            _alert("warn", "risk violation: notional cap", {"notional": order.qty*float(order.price), "cap": _risk["max_notional"]})
            return {"ok": False, "code":"RISK_NOTIONAL_CAP", "reason": "notional limit"}

    # rate limit
    t = time.time()
    window = [x for x in _state.get("orders_last_min", []) if t - x < 60]
    if len(window) >= int(_risk.get("max_orders_per_min", 30)):
        _alert("warn", "risk violation: rate limit", {"count": len(window), "limit": _risk.get("max_orders_per_min", 30)})
        return {"ok": False, "code":"RISK_RATE_LIMIT", "reason": "too many orders per minute"}

    # daily loss limit
    if float(_risk.get("daily_loss_limit", 0)) > 0 and (-_state.get("pnl_day", 0.0)) >= float(_risk["daily_loss_limit"]):
        _state["blocked"] = True
        _state["block_reason"] = "daily loss limit exceeded"
        _save_json(STATE_FILE, _state)
        _alert("error", "risk BLOCKED: daily loss limit exceeded", {"pnl_day": _state["pnl_day"], "limit": _risk["daily_loss_limit"]})
        return {"ok": False, "code":"RISK_DAILY_LOSS", "reason": _state["block_reason"]}

    return None

def _after_fill(pnl_delta: float = 0.0):
    # update day pnl and rate window
    t = time.time()
    _state.setdefault("orders_last_min", []).append(t)
    _state["orders_last_min"] = [x for x in _state["orders_last_min"] if t - x < 60]
    _state["pnl_day"] = float(_state.get("pnl_day", 0.0)) + float(pnl_delta)
    _save_json(STATE_FILE, _state)

@app.post("/order_paper")
def order_paper(order: Order):
    load_all()
    risk = _enforce_risk(order)
    if risk:
        return risk
    oid = hex(len(_positions)+1)
    ts_now = datetime.utcnow().isoformat()
    _positions.append({"id": oid, "ts": ts_now, **order.dict(), "mode": "paper"})
    # record history entry
    try:
        entry = {
            "id": oid,
            "ts": ts_now,
            "symbol": order.symbol,
            "side": order.side,
            "qty": float(order.qty),
            "price": float(order.price) if order.price is not None else None,
            "mode": "paper"
        }
        _history.append(entry)
        _save_history()
    except Exception:
        pass
    _balance["paper"] -= 1.0
    _after_fill(+0.0)  # mock PnL impact; change if you simulate fills
    return {"ok": True, "order_id": oid}

@app.post("/order_live")
def order_live(order: Order):
    load_all()
    risk = _enforce_risk(order)
    if risk:
        return risk
    oid = hex(len(_positions)+1)
    ts_now = datetime.utcnow().isoformat()
    _positions.append({"id": oid, "ts": ts_now, **order.dict(), "mode": "live"})
    # record history entry
    try:
        entry = {
            "id": oid,
            "ts": ts_now,
            "symbol": order.symbol,
            "side": order.side,
            "qty": float(order.qty),
            "price": float(order.price) if order.price is not None else None,
            "mode": "live"
        }
        _history.append(entry)
        _save_history()
    except Exception:
        pass
    _balance["live"] -= 1.0
    _after_fill(+0.0)
    return {"ok": True, "order_id": oid}