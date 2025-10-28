
import os, asyncio, json, time
from typing import Dict, Any, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import websockets

SYMBOL = os.getenv("SYMBOL", "BTCUSDT").upper()
SYMBOLS = [s.strip().upper() for s in os.getenv("SYMBOLS", SYMBOL).split(",") if s.strip()]
WS_BASE = os.getenv("BINANCE_WS_BASE", "wss://stream.binance.com:9443")

app = FastAPI(title="Exchange Ingestor (Binance WS)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class Ticker(BaseModel):
    s: str  # symbol
    c: str  # last price
    E: int  # event time

LATEST: Dict[str, Dict[str, Any]] = {}
RUNNING = False

@app.get("/health")
def health():
    return {"ok": True, "running": RUNNING, "symbols": SYMBOLS, "have": list(LATEST.keys())}

@app.get("/last")
def last(symbol: Optional[str] = None):
    if not symbol:
        symbol = SYMBOLS[0] if SYMBOLS else SYMBOL
    sym = symbol.upper()
    data = LATEST.get(sym)
    return {"ok": True, "last": data or {"symbol": sym, "price": None}}

async def consumer():
    global RUNNING
    streams = "/".join([f"{s.lower()}@ticker" for s in SYMBOLS])
    url = f"{WS_BASE}/stream?streams={streams}"
    backoff = 1
    while True:
        try:
            RUNNING = True
            async with websockets.connect(url, ping_interval=15, ping_timeout=15, max_size=1_000_000) as ws:
                while True:
                    raw = await ws.recv()
                    msg = json.loads(raw)
                    payload = msg.get("data") or msg
                    if not payload:
                        continue
                    if 's' in payload and 'c' in payload:
                        LATEST[payload['s']] = {"symbol": payload['s'], "price": payload['c'], "ts": payload.get('E', int(time.time()*1000))}
                        backoff = 1
        except Exception:
            RUNNING = False
            await asyncio.sleep(min(backoff, 30))
            backoff = min(backoff * 2, 30)

@app.on_event("startup")
async def on_start():
    asyncio.create_task(consumer())
