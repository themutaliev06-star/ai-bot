# spark_panel/app.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import httpx

INGESTOR_BASE = "http://127.0.0.1:8700"
app = FastAPI(title="NewBot Spark Panel", version="0.1.1")

HTML = '''<!doctype html><html><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NewBot - Sparkline</title>
<style>
body{margin:0;background:#0b0f14;color:#d9e1ea;font:14px system-ui}
.wrap{max-width:760px;margin:16px auto;padding:0 12px}
.card{background:#111826;border:1px solid #1d2633;border-radius:12px;padding:12px}
.input{padding:6px 10px;border-radius:8px;border:1px solid #36465e;background:#0f1823;color:#d9e1ea}
.btn{padding:8px 10px;border-radius:8px;border:1px solid #36465e;background:#192334;color:#d9e1ea;cursor:pointer}
.canvasWrap{height:220px;border:1px solid #1d2633;border-radius:8px;background:#0f1823;margin-top:8px}
</style></head><body>
<div class="wrap">
  <h1>NewBot - Live Sparkline</h1>
  <div class="card">
    <div>
      <label>symbol</label>
      <input id="sym" class="input" value="BTCUSDT" style="width:160px"/>
      <button class="btn" onclick="resetSeries()">Reset</button>
    </div>
    <div class="canvasWrap"><canvas id="spark" width="720" height="220"></canvas></div>
    <pre id="lastBox"></pre>
  </div>
</div>
<script>
const $=(id)=>document.getElementById(id);
const series=[]; const MAXN=600;
function resetSeries(){ series.length=0; drawSpark(); }
function drawSpark(){
  const c=$("spark"); const ctx=c.getContext("2d"); const w=c.width,h=c.height;
  ctx.clearRect(0,0,w,h);
  ctx.strokeStyle="#1d2633"; ctx.lineWidth=1;
  for(let x=0;x<w;x+=60){ ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,h); ctx.stroke(); }
  if(series.length<2){ ctx.fillStyle="#8aa0b5"; ctx.fillText("collecting...",10,20); return; }
  const min=Math.min(...series), max=Math.max(...series); const pad=10, span=(max-min)||1;
  ctx.beginPath(); ctx.strokeStyle="#9ecbff"; ctx.lineWidth=2;
  for(let i=0;i<series.length;i++){
    const x = pad + (w-2*pad) * i/(MAXN-1);
    const y = pad + (h-2*pad) * (1 - (series[i]-min)/span);
    if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
  }
  ctx.stroke();
}
async function poll(){
  try{
    const s=$("sym").value||"BTCUSDT";
    const r = await fetch(`/last?symbol=${encodeURIComponent(s)}`);
    const js = await r.json();
    const px = Number(js.last.price);
    $("lastBox").textContent = JSON.stringify(js,null,2);
    if(!Number.isNaN(px)){ series.push(px); if(series.length>MAXN) series.shift(); drawSpark(); }
  }catch(e){}
}
setInterval(poll, 1000);
</script></body></html>'''

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(HTML)

@app.get("/last")
async def last(symbol: str = "BTCUSDT"):
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{INGESTOR_BASE}/last", params={"symbol": symbol})
    return r.json()
