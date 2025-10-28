from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

app = FastAPI(title="Alerts", version="0.1.0")

class Alert(BaseModel):
    channel: str = "log"
    message: str
    level: str = "info"

@app.get("/health")
def health():
    return {"ok": True, "name": "alerts", "ts": datetime.utcnow().isoformat()}

@app.post("/notify")
def notify(a: Alert):
    print(f"[ALERT][{a.level.upper()}][{a.channel}] {a.message}")
    return {"ok": True, "ts": datetime.utcnow().isoformat()}
