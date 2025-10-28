
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import threading, time, json, os
import httpx

app = FastAPI(title="AI Radar (v0.2)", version="0.2.0")

STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")
_lock = threading.Lock()
_running = False
_state = {
    "running": False,
    "equity": 10000.0,
    "pnl_total": 0.0,
    "pnl_day": 0.0,
    "max_drawdown": 0.0,
    "sharpe": 0.0,
    "win_rate": 0.0,
    "trades_count": 0,
    "episode": 0,
    "avg_reward": 0.0,
    "timestamp": None,
    # new metrics
    "volatility": 0.0,
    "var95": 0.0,
    # additional metrics
    "profit_factor": 0.0,
    "sortino": 0.0,
}

# Symbols to scan across the market. This should mirror the SYMBOLS
# defined for the exchange_ingestor service. If multiple symbols are
# supplied (comma separated), the radar will attempt to collect
# price updates for each symbol and compute simple price change
# statistics. You can override this via the environment variable
# SYMBOLS. Example: "BTCUSDT,ETHUSDT,BNBUSDT".
SYMBOLS = [s.strip().upper() for s in os.getenv("SYMBOLS", "BTCUSDT").split(",") if s.strip()]

# Base URL of the exchange ingestor service. The radar will query
# the /last endpoint on this service to fetch the most recent price
# for each symbol. Override this using the INGESTOR_URL environment
# variable to point at the correct host/port (e.g. "http://localhost:8700").
INGESTOR_URL = os.getenv("INGESTOR_URL", "http://localhost:8700")

# Maintain a cache of the last observed price per symbol. When scanning the
# market, changes are computed relative to the previously stored price.
symbol_prices: dict[str, float] = {}
_price_lock = threading.Lock()
HISTORY_FILE = None  # not used here but for potential training logs

class TrainData(BaseModel):
    """Payload for training the AI radar on a list of returns."""
    returns: list[float]

def _compute_metrics(returns):
    """Compute simple metrics from a list of returns."""
    if not returns:
        return None
    n = len(returns)
    total = sum(returns)
    pnl_total = total
    pnl_day = total  # naive: all returns belong to current day
    # win rate
    wins = sum(1 for r in returns if r > 0)
    win_rate = wins / n if n else 0.0
    # sharpe ratio: mean divided by std deviation (annualization omitted)
    mean_r = total / n
    variance = sum((r - mean_r)**2 for r in returns) / n if n else 0.0
    std = variance**0.5
    sharpe = (mean_r / std) if std > 0 else 0.0
    # volatility: standard deviation of returns
    volatility = std
    # Value at Risk (95% confidence): negative 5th percentile of returns
    sorted_returns = sorted(returns)
    var95 = 0.0
    if n:
        idx = max(0, int(0.05 * n) - 1)
        # ensure index is within bounds
        if idx < 0:
            idx = 0
        elif idx >= n:
            idx = n - 1
        var95 = -sorted_returns[idx]
    # profit factor: ratio of sum of positive returns to absolute sum of negative returns
    sum_pos = sum(r for r in returns if r > 0)
    sum_neg = -sum(r for r in returns if r < 0)
    profit_factor = (sum_pos / sum_neg) if sum_neg > 0 else 0.0
    # Sortino ratio: mean divided by downside deviation
    downs = [r for r in returns if r < 0]
    downside_var = sum((r)**2 for r in downs) / n if n else 0.0
    downside_std = downside_var**0.5 if downside_var > 0 else 0.0
    sortino = (mean_r / downside_std) if downside_std > 0 else 0.0
    # max drawdown
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in returns:
        cumulative += r
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_dd:
            max_dd = drawdown
    return {
        "pnl_total": pnl_total,
        "pnl_day": pnl_day,
        "win_rate": win_rate,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "trades_count": n,
        "avg_reward": mean_r,
        "volatility": volatility,
        "var95": var95,
        "profit_factor": profit_factor,
        "sortino": sortino,
    }

def _load_state():
    global _state
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                _state.update(data)
    except Exception:
        pass

def _save_state():
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(_state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _loop():
    global _state
    while True:
        with _lock:
            if not _running:
                break
            # simple evolving mock metrics to visualize progress
            _state["episode"] += 1
            _state["trades_count"] += 1
            _state["pnl_day"] += 1.0
            _state["pnl_total"] += 1.0
            _state["equity"] = 10000.0 + _state["pnl_total"]
            _state["avg_reward"] = 0.10
            _state["win_rate"] = 0.55
            _state["sharpe"] = 1.2
            _state["timestamp"] = datetime.utcnow().isoformat()
            _save_state()
        time.sleep(1.0)

class Health(BaseModel):
    ok: bool = True
    name: str = "ai_radar"
    version: str = "0.2.0"

@app.get("/health")
def health():
    return Health()

@app.post("/start")
def start():
    global _running
    _load_state()
    with _lock:
        if not _running:
            _running = True
            t = threading.Thread(target=_loop, daemon=True)
            t.start()
        _state["running"] = True
        _save_state()
    return {"ok": True, "running": True}

@app.post("/stop")
def stop():
    global _running
    with _lock:
        _running = False
        _state["running"] = False
        _save_state()
    return {"ok": True, "running": False}

@app.get("/metrics")
def metrics():
    _load_state()
    # Build a metrics dictionary including a basic recommendation. The
    # recommendation is a human-readable summary of the performance of
    # the system based on Sharpe ratio and win rate. This can help
    # users interpret the metrics without deep quantitative knowledge.
    metrics = {
        "equity": _state["equity"],
        "pnl_total": _state["pnl_total"],
        "pnl_day": _state["pnl_day"],
        "max_drawdown": _state["max_drawdown"],
        "sharpe": _state["sharpe"],
        "win_rate": _state["win_rate"],
        "trades_count": _state["trades_count"],
        "episode": _state["episode"],
        "avg_reward": _state["avg_reward"],
        "volatility": _state.get("volatility", 0.0),
        "var95": _state.get("var95", 0.0),
        "profit_factor": _state.get("profit_factor", 0.0),
        "sortino": _state.get("sortino", 0.0),
        "timestamp": _state["timestamp"] or datetime.utcnow().isoformat()
    }
    # simple recommendation logic: evaluate metrics
    def _recommend(m: dict) -> str:
        try:
            sharpe = m.get("sharpe", 0.0) or 0.0
            win_rate = m.get("win_rate", 0.0) or 0.0
            if sharpe >= 2.0 and win_rate >= 0.6:
                return "Отличные показатели: стратегия показывает высокую эффективность."
            elif sharpe >= 1.0 and win_rate >= 0.5:
                return "Умеренные результаты: стратегия работает стабильно."
            else:
                return "Слабые показатели: рассмотрите изменение параметров или повторное обучение."
        except Exception:
            return ""
    metrics["recommendation"] = _recommend(metrics)
    return {"ok": True, "metrics": metrics}

@app.post("/train")
def train(data: TrainData):
    """Train the AI radar on a sequence of returns (simple analytics).

    The endpoint accepts a JSON body with a 'returns' field containing a list
    of floats representing trade PnL or returns. It updates the internal state
    metrics based on this sequence and returns the computed metrics.
    """
    returns = data.returns or []
    metrics = _compute_metrics(returns)
    if metrics is None:
        return {"ok": False, "error": "no_returns"}
    with _lock:
        # update state with new metrics
        _state["pnl_total"] = metrics["pnl_total"]
        _state["pnl_day"] = metrics["pnl_day"]
        _state["win_rate"] = metrics["win_rate"]
        _state["sharpe"] = metrics["sharpe"]
        _state["max_drawdown"] = metrics["max_drawdown"]
        _state["trades_count"] = metrics["trades_count"]
        _state["episode"] += 1
        _state["avg_reward"] = metrics["avg_reward"]
        _state["equity"] = 10000.0 + metrics["pnl_total"]
        _state["volatility"] = metrics.get("volatility", 0.0)
        _state["var95"] = metrics.get("var95", 0.0)
        _state["profit_factor"] = metrics.get("profit_factor", 0.0)
        _state["sortino"] = metrics.get("sortino", 0.0)
        _state["timestamp"] = datetime.utcnow().isoformat()
        _save_state()
    # return metrics to client
    # build metrics dict and attach recommendation
    metrics_out = {
        "equity": _state["equity"],
        "pnl_total": _state["pnl_total"],
        "pnl_day": _state["pnl_day"],
        "max_drawdown": _state["max_drawdown"],
        "sharpe": _state["sharpe"],
        "win_rate": _state["win_rate"],
        "trades_count": _state["trades_count"],
        "episode": _state["episode"],
        "avg_reward": _state["avg_reward"],
        "volatility": _state["volatility"],
        "var95": _state["var95"],
        "profit_factor": _state["profit_factor"],
        "sortino": _state["sortino"],
        "timestamp": _state["timestamp"]
    }
    # same recommendation logic as metrics()
    def _recommend(m: dict) -> str:
        try:
            sharpe = m.get("sharpe", 0.0) or 0.0
            win_rate = m.get("win_rate", 0.0) or 0.0
            if sharpe >= 2.0 and win_rate >= 0.6:
                return "Отличные показатели: стратегия показывает высокую эффективность."
            elif sharpe >= 1.0 and win_rate >= 0.5:
                return "Умеренные результаты: стратегия работает стабильно."
            else:
                return "Слабые показатели: рассмотрите изменение параметров или повторное обучение."
        except Exception:
            return ""
    metrics_out["recommendation"] = _recommend(metrics_out)
    return {"ok": True, "metrics": metrics_out}


# ---------------------------------------------------------------------------
# Market scanning logic
# ---------------------------------------------------------------------------
@app.get("/scan")
def scan(threshold: float = 0.005):
    """Scan the configured list of symbols and return those that have moved
    beyond a percentage threshold since the previous scan.

    This endpoint queries the exchange ingestor's /last API for each symbol
    specified in the SYMBOLS environment variable. It tracks the last
    observed price per symbol and computes the relative change between
    successive observations. Only symbols whose absolute change exceeds
    the provided `threshold` (default 0.005, i.e. 0.5%) are included in
    the results. The results are sorted by descending absolute change.

    Note: this is a simple baseline implementation intended to identify
    potential trading opportunities by highlighting assets experiencing
    notable price movements. For real-world use, consider enhancing this
    with more sophisticated indicators (e.g., moving average crossovers,
    RSI or volume filters).

    Args:
        threshold (float): Minimum absolute relative change required to
            include a symbol in the results. A value of 0.01 corresponds
            to a 1% change between scans.

    Returns:
        dict: An object with `ok` flag and a list of results, each
            containing the symbol, latest price, and relative change.
    """
    results: list[dict] = []
    for sym in SYMBOLS:
        symbol = sym.upper()
        try:
            url = f"{INGESTOR_URL}/last?symbol={symbol}"
            resp = httpx.get(url, timeout=3.0)
            if resp.status_code != 200:
                continue
            data = resp.json()
            last = data.get("last") if isinstance(data, dict) else None
            # fallback: some ingestor implementations may not nest 'last'
            if last is None:
                last = data
            if not isinstance(last, dict):
                continue
            price_str = last.get("price")
            if price_str is None:
                continue
            price = float(price_str)
            # compute change relative to previous price
            with _price_lock:
                prev = symbol_prices.get(symbol)
                symbol_prices[symbol] = price
            if prev and prev > 0:
                change = (price - prev) / prev
                if abs(change) >= threshold:
                    results.append({"symbol": symbol, "price": price, "change": change})
        except Exception:
            # ignore issues for this symbol
            continue
    # sort by absolute change descending
    results.sort(key=lambda x: abs(x.get("change", 0.0)), reverse=True)
    return {"ok": True, "results": results}
