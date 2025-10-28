
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import httpx, os, time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI LLM Gateway (Unified Ops)", version="2.6.1")

# ====== CONFIG ======
EXECUTOR_BASE   = os.getenv("EXECUTOR_BASE",   "http://127.0.0.1:8600")
BACKTESTER_BASE = os.getenv("BACKTESTER_BASE", "http://127.0.0.1:8900")
INGESTOR_BASE   = os.getenv("INGESTOR_BASE",   "http://127.0.0.1:8700")
AI_BASE         = os.getenv("AI_BASE",         "http://127.0.0.1:8750")
ALERTS_BASE     = os.getenv("ALERTS_BASE",     "http://127.0.0.1:8650")

# ====== LOGGER ======
class SimpleLogger(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        t0 = time.perf_counter()
        resp = await call_next(request)
        dt = (time.perf_counter() - t0) * 1000
        print(f"{request.method} {request.url.path} -> {resp.status_code} [{dt:.1f} ms]")
        return resp
app.add_middleware(SimpleLogger)

# Allow cross-origin requests from any domain for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== HEALTH ======
@app.get("/health")
async def health():
    return {"ok": True, "name": "ai_llm_gateway", "version": "2.6.1"}

# ====== PROXY CORE ======
async def _proxy(method: str, base: str, path: str, request: Request):
    url = f"{base}/{path.lstrip('/')}"
    headers = dict(request.headers); headers.pop("host", None)
    timeout = httpx.Timeout(30.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            r = await client.get(url, params=dict(request.query_params))
        else:
            body = await request.body()
            r = await client.post(url, content=body, headers=headers, params=dict(request.query_params))
    try:
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception:
        return HTMLResponse(r.text, status_code=r.status_code)

def mk_proxy(prefix: str, base: str):
    @app.get(f"/proxy/{prefix}" + "/{path:path}")
    async def _get(path: str, request: Request):
        return await _proxy("GET", base, path, request)
    @app.post(f"/proxy/{prefix}" + "/{path:path}")
    async def _post(path: str, request: Request):
        return await _proxy("POST", base, path, request)

mk_proxy("executor",   EXECUTOR_BASE)
mk_proxy("backtester", BACKTESTER_BASE)
mk_proxy("ingestor",   INGESTOR_BASE)
mk_proxy("ai",         AI_BASE)
mk_proxy("alerts",     ALERTS_BASE)

# ====== ADAPTIVE backtester log endpoint (UI дергает /proxy/backtester/log) ======
CANDIDATE_LOG_PATHS = ["log","logs","logs_tail","tail","last"]

@app.get("/proxy/backtester/log")
async def proxy_backtester_log(tail: int = Query(500, ge=10, le=5000)):
    timeout = httpx.Timeout(10.0, connect=3.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for p in CANDIDATE_LOG_PATHS:
            try:
                if p in ("tail","last"):
                    r = await client.get(f"{BACKTESTER_BASE}/{p}", params={"lines": tail})
                else:
                    r = await client.get(f"{BACKTESTER_BASE}/{p}", params={"tail": tail})
                if r.status_code == 200:
                    try:
                        return r.json()
                    except Exception:
                        return {"ok": True, "text": r.text}
            except Exception:
                pass
        return {"ok": False, "error": "no_log_endpoint", "tried": CANDIDATE_LOG_PATHS}

# ====== PUBLIC API (минимальный) ======
TIMEOUT = httpx.Timeout(20.0, connect=5.0)

@app.get("/api/trading/status")
async def api_status():
    out = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
        for name, url in [
            ("executor",   f"{EXECUTOR_BASE}/health"),
            ("backtester", f"{BACKTESTER_BASE}/health"),
            ("ingestor",   f"{INGESTOR_BASE}/health"),
            ("ai",         f"{AI_BASE}/health"),
            ("alerts",     f"{ALERTS_BASE}/health"),
        ]:
            ok = False
            try:
                r = await client.get(url)
                ok = (r.status_code == 200)
            except Exception:
                ok = False
            out.append({"name": name, "ok": ok})
    return {"ok": True, "services": out}

# ====== UNIFIED TRADING API ======
@app.get("/api/trading/metrics")
async def api_trading_metrics():
    """Return AI trading metrics such as equity, PnL, Sharpe ratio and trades count."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(f"{AI_BASE}/metrics")
            return r.json()
        except Exception as e:
            return {"error": str(e)}

@app.get("/api/trading/positions")
async def api_trading_positions():
    """Return current open positions from the executor."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(f"{EXECUTOR_BASE}/positions")
            return r.json()
        except Exception as e:
            return {"error": str(e)}

@app.get("/api/trading/risk")
async def api_trading_risk():
    """Return current risk settings and state from the executor."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(f"{EXECUTOR_BASE}/risk")
            return r.json()
        except Exception as e:
            return {"error": str(e)}

@app.get("/api/trading/trades")
async def api_trading_trades(limit: int = 50, source: str = "executor"):
    """Return recent trades history from either the executor or the backtester.

    Parameters:
        limit (int): maximum number of trades to return.
        source (str): 'executor' or 'backtester' to select the source service.
    """
    base = EXECUTOR_BASE if source == "executor" else BACKTESTER_BASE
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(f"{base}/trades", params={"limit": limit})
            return r.json()
        except Exception as e:
            return {"error": str(e)}

# ====== SIMPLE AI CHAT STUB ======
@app.post("/api/ai/chat")
async def api_ai_chat(data: dict):
    """Simple AI chat endpoint that echoes back the prompt. In a real deployment this would call an LLM service."""
    prompt = data.get("prompt", "")
    # trim to avoid extremely long responses
    reply = f"Echo: {prompt}" if prompt else "Please enter a question."
    return {"response": reply}

# ====== UI (полная страница + risk bar) ======
DASH_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>NewBot — Панель</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
  :root {
    --bg:#111827;
    --panel:#1f2937;
    --card:#273447;
    --txt:#e5e7eb;
    --muted:#9ca3af;
    --br:#374151;
    --ok:#10b981;
    --warn:#fbbf24;
    --err:#ef4444;
    --btn:#374151;
    --accent:#6366f1;
    /* moving average line colours */
    --ma1:#f59e0b;
    --ma2:#ef4444;
  }
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--txt);font:14px system-ui,Segoe UI,Roboto}
  .header{position:sticky;top:0;background:rgba(11,15,20,0.85);backdrop-filter:blur(8px);z-index:9;border-bottom:1px solid var(--br)}
  .h-inner{max-width:1280px;margin:0 auto;padding:10px 14px;display:flex;gap:10px;align-items:center;justify-content:space-between}
  .h-left{display:flex;gap:10px;align-items:center}
  .h-right{display:flex;gap:8px;align-items:center}
  .badge{padding:4px 8px;border-radius:8px;border:1px solid var(--br);background:var(--panel);font-size:12px}
  .ok{border-color:var(--ok)} .wn{border-color:var(--warn)} .er{border-color:var(--err)}
  .riskbar{display:flex;gap:6px;align-items:center}
  .rb-dot{width:10px;height:10px;border-radius:50%;background:var(--ok);border:1px solid var(--br)}
  .rb-dot.wn{background:var(--warn)} .rb-dot.er{background:var(--err)}
  .rb-text{font-size:12px;color:var(--muted)}
  .tooltip{position:relative;cursor:help}
  .tooltip .tip{display:none;position:absolute;top:20px;left:0;background:#0b1118;border:1px solid var(--br);padding:6px 8px;border-radius:8px;font-size:12px;white-space:pre}
  .tooltip:hover .tip{display:block}
  .wrap{max-width:1280px;margin:14px auto;padding:0 14px}
  .card{background:var(--panel);border:1px solid var(--br);border-radius:12px;padding:12px;margin-bottom:12px;box-shadow:0 2px 4px rgba(0,0,0,0.4)}
  .kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
  @media(max-width:768px){ .kpi{grid-template-columns:repeat(2,1fr);} }
  @media(max-width:480px){ .kpi{grid-template-columns:1fr;} }
  .kbox{background:var(--card);border:1px solid var(--br);border-radius:10px;padding:10px;min-height:70px;transition:background-color .3s}
  .kbox:hover{background:var(--panel)}
  .kbox .lbl{color:var(--muted);font-size:12px;margin-bottom:6px}
  .kbox .val{font-size:18px;font-weight:600}
  .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
  .btn{padding:8px 10px;border-radius:8px;border:1px solid var(--br);background:var(--btn);color:var(--txt);cursor:pointer;transition:background-color .3s,color .3s}
  .btn:hover{background:var(--accent);color:#fff}
  .input,select{padding:8px;border-radius:8px;border:1px solid var(--br);background:var(--card);color:var(--txt)}
  pre{background:var(--card);border:1px solid var(--br);border-radius:8px;padding:10px;max-height:240px;overflow:auto;margin:0}
  /* allow resizing of pre blocks for better log viewing */
  pre{resize:vertical;}
  table{width:100%;border-collapse:collapse}
  th,td{border-bottom:1px solid var(--br);padding:6px 8px;font-size:13px;text-align:left}
  /* theme toggle icon inside button can be styled separately if needed */

  /* legend for moving average lines */
  .ma-legend{display:flex;gap:14px;font-size:11px;color:var(--muted);margin-top:4px}
  .ma-legend .item{display:flex;align-items:center;gap:6px}
  .ma-box{width:14px;height:3px;display:inline-block;vertical-align:middle}

  /* sidebar navigation */
  .sidebar{position:fixed;top:0;left:0;width:200px;height:100%;background:var(--panel);border-right:1px solid var(--br);display:flex;flex-direction:column;z-index:10}
  .sidebar .logo{height:56px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:600;border-bottom:1px solid var(--br);}
  .sidebar a{color:var(--txt);text-decoration:none;padding:12px 20px;font-size:14px;border-radius:6px;margin:2px 8px;display:flex;align-items:center;gap:6px;transition:background-color .3s,color .3s;}
  .sidebar a:hover{background:var(--accent);color:#fff}
  /* layout adjustments when sidebar is present */
  .header{padding-left:210px;}
  .wrap{margin-left:210px;max-width:none;}
  @media(max-width:768px){
    .sidebar{display:none;}
    .header{padding-left:0;}
    .wrap{margin-left:0;}
  }
  /* risk meter bar */
  .risk-meter{width:80px;height:6px;background:var(--card);border:1px solid var(--br);border-radius:3px;overflow:hidden;margin-right:6px;}
  .risk-fill{height:100%;width:0%;background:var(--ok);transition:width .3s;}
  .riskbar .rb-text{font-size:12px;color:var(--muted);}
</style>
</head>
<body>
  <!-- Sidebar navigation -->
  <div class="sidebar">
    <div class="logo">NewBot</div>
    <a href="#overview">Обзор</a>
    <a href="#trading">Торговля</a>
    <a href="#risk">Риск</a>
    <a href="#trades">Сделки</a>
    <a href="#positions">Позиции</a>
    <a href="#live-price">График&nbsp;цены</a>
    <a href="#market-radar">Радар&nbsp;рынка</a>
    <a href="#backtest">Бэктест</a>
    <a href="#logs">Логи</a>
    <a href="#ai-training">Обучение&nbsp;ИИ</a>
    <a href="#ai-chat">ИИ&nbsp;трейдер</a>
  </div>
  <div class="header">
    <div class="h-inner">
      <div class="h-left">
        <strong>NewBot — Панель</strong>
        <span id="b_exec" class="badge">exec: …</span>
        <span id="b_alerts" class="badge">alerts: …</span>
        <span class="badge tooltip">
          <span class="riskbar">
            <div id="risk_meter" class="risk-meter"><div id="risk_fill" class="risk-fill"></div></div>
            <span id="rb_label" class="rb-text">риск: —</span>
          </span>
          <span id="rb_tip" class="tip">no data</span>
        </span>
      </div>
      <div class="h-right">
        <label>символ</label><input id="h_symbol" list="fav_list" class="input" value="BTCUSDT" style="width:130px"/>
        <datalist id="fav_list"></datalist>
        <button class="btn" id="h_apply">Применить</button>
        <!-- Theme toggle button: shows the next mode to switch to -->
        <button class="btn" id="theme_toggle">Светлая</button>
      </div>
    </div>
  </div>

  <div class="wrap">
    <div id="overview" class="card">
        <div class="kpi">
        <div class="kbox tooltip">
        <div class="lbl">Капитал</div>
          <div id="k_equity" class="val">—</div>
          <span class="tip">Current account equity\n(Assets minus liabilities)</span>
        </div>
        <div class="kbox tooltip">
        <div class="lbl">PNL (Всего)</div>
          <div id="k_pnl" class="val">—</div>
          <span class="tip">Суммарная реализованная прибыль/убыток</span>
        </div>
        <div class="kbox tooltip">
        <div class="lbl">Шарп</div>
          <div id="k_sharpe" class="val">—</div>
          <span class="tip">Доходность, скорректированная на риск (коэффициент Шарпа)</span>
        </div>
        <div class="kbox tooltip">
        <div class="lbl">Сделки</div>
          <div id="k_trades" class="val">—</div>
          <span class="tip">Количество совершённых сделок</span>
        </div>
        <!-- Additional metrics -->
        <div class="kbox tooltip">
        <div class="lbl">PNL (День)</div>
          <div id="k_pnl_day" class="val">—</div>
          <span class="tip">Прибыль/убыток за текущий день</span>
        </div>
        <div class="kbox tooltip">
        <div class="lbl">Макс. просадка</div>
          <div id="k_maxdd" class="val">—</div>
          <span class="tip">Максимальная просадка от пика капитала</span>
        </div>
        <div class="kbox tooltip">
        <div class="lbl">Win Rate</div>
          <div id="k_winrate" class="val">—</div>
          <span class="tip">Доля положительных доходностей</span>
        </div>
        <div class="kbox tooltip">
        <div class="lbl">Волатильность</div>
          <div id="k_volatility" class="val">—</div>
          <span class="tip">Стандартное отклонение доходностей</span>
        </div>
        <div class="kbox tooltip">
        <div class="lbl">VaR 95%</div>
          <div id="k_var95" class="val">—</div>
          <span class="tip">VaR при доверии 95%</span>
        </div>
      </div>
      <div style="font-size:12px;color:var(--muted);margin-top:6px">Источник: /proxy/ai/metrics (автообновление 5с)</div>
    </div>

    <div id="trading" class="card">
    <h3 style="margin:0 0 8px 0;font-size:14px;color:var(--muted)">Исполнитель</h3>
      <div class="row">
        <label>символ</label><input id="ex_symbol" class="input" style="width:120px" value="BTCUSDT"/>
        <label>сторона</label><select id="ex_side" class="input"><option>buy</option><option>sell</option></select>
        <label>кол-во</label><input id="ex_qty" class="input" style="width:80px" value="0.01"/>
        <button class="btn" id="btn_order">Ордер (бумага)</button>
        <button class="btn" id="btn_pos">Позиции</button>
        <button class="btn" id="btn_bal">Баланс</button>
        <button class="btn" id="btn_switch">Переключить режим</button>
      </div>
      <pre id="ex_out">{ }</pre>
    </div>

    <div id="risk" class="card">
    <h3 style="margin:0 0 8px 0;font-size:14px;color:var(--muted)">Риск</h3>
      <div class="row">
        <button class="btn" id="btn_risk_load">Загрузить</button>
        <button class="btn" id="btn_risk_save">Сохранить</button>
        <button class="btn" id="btn_risk_unblock">Разблокировать</button>
        <span id="risk_state" style="font-size:12px;color:var(--muted)"></span>
      </div>
      <div class="row" style="margin-top:6px">
        <label>макс ордеров/мин</label><input id="r_maxopm" class="input" style="width:90px" value="30"/>
        <label>лимит убытков/день</label><input id="r_dll" class="input" style="width:90px" value="200"/>
        <label>макс кол-во позиций</label><input id="r_mpq" class="input" style="width:90px" value="1"/>
        <label>макс номинал</label><input id="r_not" class="input" style="width:100px" value="2000"/>
      </div>
      <pre id="risk_out" style="margin-top:8px">{ }</pre>
    </div>

    <div id="trades" class="card">
    <h3 style="margin:0 0 8px 0;font-size:14px;color:var(--muted)">Сделки</h3>
      <div class="row">
        <label>источник</label><select id="tr_src" class="input"><option>executor</option><option>backtester</option></select>
        <label>лимит</label><input id="tr_lim" class="input" style="width:80px" value="50"/>
        <button class="btn" id="tr_refresh">Обновить</button>
        <button class="btn" id="tr_export">Экспорт CSV</button>
      </div>
      <div style="overflow:auto;margin-top:8px">
        <table>
          <thead><tr><th>время</th><th>тип</th><th>символ</th><th>сторона</th><th>кол-во</th><th>цена@сделки</th><th>цена@тек</th><th>Δцена</th></tr></thead>
          <tbody id="tr_tbody"></tbody>
        </table>
      </div>
    </div>

    <!-- Positions (open exposures) -->
    <div id="positions" class="card">
    <h3 style="margin:0 0 8px 0;font-size:14px;color:var(--muted)">Позиции</h3>
      <div class="row">
        <button class="btn" id="pos_refresh">Обновить</button>
      </div>
      <div style="overflow:auto;margin-top:8px">
        <table>
          <thead><tr><th>символ</th><th>кол-во</th><th>сред. цена</th><th>текущ. цена</th><th>PnL</th></tr></thead>
          <tbody id="pos_tbody"></tbody>
        </table>
      </div>
    </div>

    <!-- Live Price Chart -->
    <div id="live-price" class="card">
    <h3 style="margin:0 0 8px 0;font-size:14px;color:var(--muted)">График цены</h3>
      <canvas id="price_chart" style="width:100%;height:220px;border:1px solid var(--br);border-radius:8px;"></canvas>
      <div class="ma-legend">
        <div class="item"><span class="ma-box" style="background:var(--ma1)"></span><span>Короткая&nbsp;MA (50)</span></div>
        <div class="item"><span class="ma-box" style="background:var(--ma2)"></span><span>Длинная&nbsp;MA (200)</span></div>
      </div>
    </div>

    <!-- Market Radar Panel -->
    <div id="market-radar" class="card">
    <h3 style="margin:0 0 8px 0;font-size:14px;color:var(--muted)">Радар рынка</h3>
      <div class="row">
        <label>порог</label>
        <input id="radar_threshold" class="input" style="width:80px" value="0.005" placeholder="0.005" />
        <button class="btn" id="radar_refresh">Сканировать</button>
      </div>
      <div style="overflow:auto;margin-top:8px">
        <table>
          <thead><tr><th>символ</th><th>цена</th><th>изменение</th></tr></thead>
          <tbody id="radar_tbody"></tbody>
        </table>
      </div>
      <small style="display:block;margin-top:4px;color:var(--muted);font-size:12px">Введите порог как десятичную долю (например, <code>0.005</code> = 0,5&nbsp;%). При сканировании будут показаны монеты, изменившиеся больше этого порога.</small>
    </div>

    <div id="logs" class="card">
    <h3 style="margin:0 0 8px 0;font-size:14px;color:var(--muted)">Логи (Backtester)</h3>
      <div class="row">
        <label>хвост</label><select id="lg_tail" class="input"><option>200</option><option selected>500</option><option>1000</option></select>
        <label style="font-size:12px;color:var(--muted)">авто</label><input id="lg_auto" type="checkbox" checked style="transform:scale(1.2)"/>
        <button class="btn" id="lg_once">Обновить</button>
      </div>
      <pre id="lg_out" style="margin-top:8px">{ }</pre>
    </div>
    <!-- AI Training Panel -->
    <div id="ai-training" class="card">
      <h3 style="margin:0 0 8px 0;font-size:14px;color:var(--muted)">Обучение ИИ</h3>
      <!-- Returns entry row: multiline textarea with train and clear buttons -->
      <div class="row" style="flex-wrap:wrap">
        <label>доходности</label>
        <!-- Multiline textarea for returns; users can paste comma, whitespace or newline separated numbers -->
        <textarea id="train_returns" class="input" style="flex:1;height:80px;resize:vertical" placeholder="Введите доходности через запятую, пробел или новую строку..."></textarea>
        <button class="btn" id="btn_train">Обучить</button>
        <button class="btn" id="btn_train_clear">Очистить</button>
      </div>
      <!-- File upload row: allow loading returns from a CSV or text file -->
      <div class="row" style="flex-wrap:wrap;margin-top:6px">
        <label>файл</label>
        <input id="train_file" type="file" accept=".csv,.txt" class="input" style="flex:1" />
      </div>
      <!-- Summary: shows count, mean, min and max of the parsed returns -->
      <small id="train_summary" style="display:block;margin-top:6px;color:var(--muted);font-size:12px">0 значений</small>
      <!-- Help text explaining training results -->
      <small style="display:block;margin-top:4px;color:var(--muted);font-size:12px;line-height:1.3">
        После нажатия «Обучить» ниже появятся метрики. Вот как их интерпретировать: <br/>
        <b>Equity</b> – итоговый капитал после применения доходностей; <b>PNL (Всего)</b> – суммарная прибыль; <b>PNL (Дня)</b> – прибыль за день; <b>Sharpe</b> – риск‑скорректированная доходность (чем выше, тем лучше); <b>Win Rate</b> – доля прибыльных сделок; <b>Max Drawdown</b> – максимальная просадка капитала; <b>Profit Factor</b> – отношение суммарной прибыли к суммарному убытку; <b>Sortino</b> – Sharpe‑аналог, учитывающий только негативные отклонения.
      </small>
      <pre id="train_out">{ }</pre>
    </div>

    <!-- Backtest Runner Panel -->
    <div id="backtest" class="card">
      <h3 style="margin:0 0 8px 0;font-size:14px;color:var(--muted)">Бэктест</h3>
      <div class="row">
        <label>доходности</label>
        <input id="bt_returns" class="input" style="flex:1" placeholder="например 0.5 -0.3 0.2"/>
        <label>символ</label>
        <input id="bt_symbol" class="input" style="width:100px" value="TEST"/>
        <button class="btn" id="btn_bt_run">Запуск</button>
      </div>
      <pre id="bt_out">{ }</pre>
      <small style="display:block;margin-top:4px;color:var(--muted);font-size:12px;line-height:1.3">
        После нажатия «Запуск» здесь появятся результаты бэктеста. В поле «доходности» введите ряд доходностей (например, <code>0.5 -0.3 0.2</code>). В таблице выше отобразятся сделки, а в блоке «metrics» – метрики, аналогичные описанию в разделе «Обучение ИИ».
      </small>
    </div>

    <!-- AI Trader Chat Panel -->
    <div id="ai-chat" class="card">
    <h3 style="margin:0 0 8px 0;font-size:14px;color:var(--muted)">ИИ трейдер</h3>
      <div class="row">
        <input id="chat_input" class="input" style="flex:1" placeholder="Спросите торгового бота..."/>
        <button class="btn" id="btn_chat_send">Отправить</button>
      </div>
      <pre id="chat_out" style="max-height:240px;overflow:auto"> </pre>
    </div>

  </div>

<script>
const $ = (id)=>document.getElementById(id);
const j = (x)=>JSON.stringify(x,null,2);

async function jget(u){ const r=await fetch(u); const t=await r.text(); try{return JSON.parse(t);}catch(e){return t;} }
async function jpost(u,b){ const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})}); const t=await r.text(); try{return JSON.parse(t);}catch(e){return t;} }

// ====== AI Training Helpers ======
// Parse a string into an array of floats. Accepts comma, whitespace or newline as separators.
function parseReturns(str){
  if(!str) return [];
  return str.split(/[\s,]+/).map(x => parseFloat(x.trim())).filter(x => !isNaN(x));
}

// Update the training summary: count, mean, min and max of the parsed returns
function updateTrainSummary(){
  const summaryEl = document.getElementById('train_summary');
  const textarea  = document.getElementById('train_returns');
  if(!summaryEl || !textarea) return;
  const arr = parseReturns(textarea.value || '');
  if(arr.length === 0){
    summaryEl.textContent = '0 значений';
    return;
  }
  const count = arr.length;
  const sum   = arr.reduce((a,b) => a+b, 0);
  const mean  = (sum / count).toFixed(4);
  const min   = Math.min(...arr).toFixed(4);
  const max   = Math.max(...arr).toFixed(4);
  summaryEl.textContent = `${count} значений: среднее ${mean}, мин ${min}, макс ${max}`;
}

async function refreshHeader(){
  try{
    const s = await jget('/proxy/executor/settings');
    const mode = s?.settings?.mode || 'paper';
    const el = $('b_exec'); el.textContent = 'exec: '+mode; el.classList.remove('ok','wn','er'); el.classList.add(mode==='live'?'er':'ok');
  }catch(e){ const el=$('b_exec'); el.textContent='exec: ?'; el.classList.remove('ok'); el.classList.add('er'); }
  try{
    const a = await fetch('/proxy/alerts/health');
    const ok = a.ok; const el=$('b_alerts'); el.textContent = 'alerts: '+(ok?'OK':'ERR'); el.classList.remove('ok','wn','er'); el.classList.add(ok?'ok':'er');
  }catch(e){ const el=$('b_alerts'); el.textContent='alerts: ERR'; el.classList.remove('ok'); el.classList.add('er'); }
  await refreshRiskBadge();
}
async function refreshRiskBadge(){
  const lab = $('rb_label'), tip = $('rb_tip'), fill = $('risk_fill');
  try {
    const r = await jget('/proxy/executor/risk');
    const rk = r?.risk || {};
    const st = r?.state || {};
    const mopm = rk.max_orders_per_min;
    const dll  = rk.daily_loss_limit;
    const mpq  = rk.max_position_qty;
    const mn   = rk.max_notional;
    // display key risk parameters in Russian for quick glance
    lab.textContent = `макс_ордеров/мин=${mopm??'?'} | лимит_убытков/день=${dll??'?'} | макс_кол-во_позиций=${mpq??'?'} | макс_номинал=${mn??'?'}`;
    // build tooltip with Russian labels
    let tipText = `макс_ордеров/мин=${mopm}\nлимит_убытков/день=${dll}\nмакс_кол-во_позиций=${mpq}\nмакс_номинал=${mn}`;
    if(st?.pnl_day != null) tipText += `\n\nPnL дня=${st.pnl_day}`;
    if(st?.blocked) tipText += `\nБлокировано: ДА`;
    if(st?.block_reason) tipText += `\nПричина: ${st.block_reason}`;
    tip.textContent = tipText;
    // compute risk ratio
    let ratio = 0;
    if(dll != null && st?.pnl_day != null && Number(dll) > 0){
      ratio = Math.min(1, Math.abs(Number(st.pnl_day)) / Number(dll));
    }
    if(fill){
      const rootStyles = getComputedStyle(document.documentElement);
      let col = rootStyles.getPropertyValue('--ok').trim();
      if(st?.blocked){
        col = rootStyles.getPropertyValue('--err').trim();
        ratio = 1;
      } else if (ratio >= 0.8){
        col = rootStyles.getPropertyValue('--warn').trim();
      }
      fill.style.background = col;
      fill.style.width = ((ratio*100).toFixed(0)) + '%';
    }
  } catch(e) {
    lab.textContent = 'риск: ERR';
    tip.textContent = 'error loading risk';
    if(fill){
      const rootStyles = getComputedStyle(document.documentElement);
      fill.style.background = rootStyles.getPropertyValue('--err').trim();
      fill.style.width = '100%';
    }
  }
}

// load favourite symbols from localStorage into the datalist
function loadFavs(){
  try {
    const favs = JSON.parse(localStorage.getItem('fav_symbols') || '[]');
    const dl = $('fav_list');
    if (!dl) return;
    dl.innerHTML = '';
    favs.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      dl.appendChild(opt);
    });
  } catch (e) {}
}
let hdrTimer=null; function headerAuto(){ if(hdrTimer) clearInterval(hdrTimer); hdrTimer=setInterval(refreshHeader, 10000); }
$('h_apply').onclick = ()=>{
  const s = $('h_symbol').value.trim() || 'BTCUSDT';
  $('ex_symbol').value = s;
  // persist favourite symbols in localStorage
  try {
    let favs = JSON.parse(localStorage.getItem('fav_symbols') || '[]');
    if (s && !favs.includes(s)) {
      favs.push(s);
      localStorage.setItem('fav_symbols', JSON.stringify(favs));
      loadFavs();
    }
  } catch (e) {}
  refreshHeader();
  // reset price chart to new symbol
  resetPriceChart(s);
};

async function loadKPI(){
  const resp = await jget('/proxy/ai/metrics');
  // metrics may be nested under resp.metrics or at root
  const m = (resp && typeof resp === 'object' && resp.metrics) ? resp.metrics : resp;
  $('k_equity').textContent = (m && m.equity != null) ? m.equity : '—';
  $('k_pnl').textContent = (m && m.pnl_total != null) ? m.pnl_total : '—';
  $('k_sharpe').textContent = (m && m.sharpe != null) ? m.sharpe : '—';
  // trades_count or trades
  const tc = (m && m.trades_count != null) ? m.trades_count : (m && m.trades != null ? m.trades : '—');
  $('k_trades').textContent = tc;
  // additional metrics
  $('k_pnl_day').textContent = (m && m.pnl_day != null) ? m.pnl_day : '—';
  $('k_maxdd').textContent = (m && m.max_drawdown != null) ? m.max_drawdown : '—';
  $('k_winrate').textContent = (m && m.win_rate != null) ? m.win_rate : '—';
  $('k_volatility').textContent = (m && m.volatility != null) ? m.volatility : '—';
  $('k_var95').textContent = (m && m.var95 != null) ? m.var95 : '—';
}
setInterval(loadKPI, 5000);

$('btn_order').onclick = async()=>{ const body={symbol:$('ex_symbol').value,side:$('ex_side').value,qty:parseFloat($('ex_qty').value||'0')}; const r=await jpost('/proxy/executor/order_paper', body); $('ex_out').textContent=j(r); };
$('btn_pos').onclick = async()=>{ const r=await jget('/proxy/executor/positions'); $('ex_out').textContent=j(r); };
$('btn_bal').onclick = async()=>{ const r=await jget('/proxy/executor/balance'); $('ex_out').textContent=j(r); };
$('btn_switch').onclick = async () => {
  let mode = 'paper';
  try {
    const s = await jget('/proxy/executor/settings');
    mode = s?.settings?.mode || 'paper';
  } catch(e) {}
  const next = (mode === 'live') ? 'paper' : 'live';
  // confirm switching to live mode with Russian prompt
  if(next === 'live' && !confirm('Переключить исполнителя в LIVE?')) return;
  const r = await jpost('/proxy/executor/settings', {mode: next});
  $('ex_out').textContent = j(r);
  refreshHeader();
};

$('btn_risk_load').onclick = async () => {
  const r = await jget('/proxy/executor/risk');
  $('risk_out').textContent = j(r);
  try {
    const rk = r?.risk || {};
    $('r_maxopm').value = rk.max_orders_per_min ?? 30;
    $('r_dll').value    = rk.daily_loss_limit ?? 200;
    $('r_mpq').value    = rk.max_position_qty ?? 1;
    $('r_not').value    = rk.max_notional ?? 2000;
    const st = r?.state || {};
    $('risk_state').textContent = 'состояние: PnL дня=' + (st.pnl_day ?? '—') + ', блокировано=' + (st.blocked ?? '—');
  } catch (e) {}
  refreshRiskBadge();
};
$('btn_risk_save').onclick = async()=>{ const body={"risk":{"max_orders_per_min":parseInt($('r_maxopm').value||'30',10),"daily_loss_limit":parseFloat($('r_dll').value||'200'),"max_position_qty":parseFloat($('r_mpq').value||'1'),"max_notional":parseFloat($('r_not').value||'2000')}}; const r=await jpost('/proxy/executor/risk', body); $('risk_out').textContent=j(r); refreshRiskBadge(); };
$('btn_risk_unblock').onclick = async()=>{ const r=await jpost('/proxy/executor/risk_unblock', {}); $('risk_out').textContent=j(r); refreshRiskBadge(); };

async function loadTrades(){
  const src = $('tr_src').value;
  const lim = parseInt($('tr_lim').value || '50', 10);
  let data = (src === 'executor') ? (await jget('/proxy/executor/trades?limit='+lim)) : (await jget('/proxy/backtester/trades?limit='+lim));
  data = data || {};
  const arr = data.trades || [];
  const tb = $('tr_tbody');
  tb.innerHTML = '';
  for (const t of arr) {
    // derive kind from entry (mode or kind)
    const kind = (t.kind !== undefined) ? t.kind : (t.mode !== undefined ? t.mode : '');
    // trade price: support px@trade, price field, or nested extra
    let pxTrade;
    if (t['px@trade'] !== undefined) pxTrade = t['px@trade'];
    else if (t.price !== undefined) pxTrade = t.price;
    else if (t.extra && t.extra['px@trade'] !== undefined) pxTrade = t.extra['px@trade'];
    // current price and delta may not be available for executor history
    let pxNow;
    if (t['px@now'] !== undefined) pxNow = t['px@now'];
    else if (t.extra && t.extra['px@now'] !== undefined) pxNow = t.extra['px@now'];
    let dpx;
    if (t['dpx'] !== undefined) dpx = t['dpx'];
    else if (t.extra && t.extra['dpx'] !== undefined) dpx = t.extra['dpx'];
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${t.ts ?? ''}</td><td>${kind ?? ''}</td><td>${t.symbol ?? ''}</td><td>${t.side ?? ''}</td><td>${t.qty ?? ''}</td><td>${pxTrade ?? ''}</td><td>${pxNow ?? ''}</td><td>${dpx ?? ''}</td>`;
    tb.appendChild(tr);
  }
}
$('tr_refresh').onclick = loadTrades;

// Load market radar results and update the table
async function loadRadar(){
  const thr = parseFloat($('radar_threshold').value || '0.005');
  const resp = await jget('/proxy/ai/scan?threshold='+thr);
  const arr = (resp && resp.results) ? resp.results : [];
  const tb = $('radar_tbody');
  tb.innerHTML = '';
  for (const item of arr) {
    const tr = document.createElement('tr');
    const sym = item.symbol || '';
    const price = (item.price != null) ? item.price : '';
    let ch = '';
    if (item.change != null) {
      const pct = (item.change * 100).toFixed(2) + '%';
      ch = pct;
    }
    tr.innerHTML = `<td>${sym}</td><td>${price}</td><td style="color:${item.change>0?'var(--ok)':'var(--err)'}">${ch}</td>`;
    tb.appendChild(tr);
  }
}

// attach handler for radar refresh
if (document.getElementById('radar_refresh')){
  document.getElementById('radar_refresh').onclick = loadRadar;
}

async function logsOnce(){ const tail=$('lg_tail').value; const r=await jget('/proxy/backtester/log?tail='+tail); $('lg_out').textContent=j(r); }
document.getElementById('lg_once').onclick = logsOnce;
function logsAuto(){ if (document.getElementById('lg_auto').checked){ logsOnce(); setTimeout(logsAuto, 3000); } }
setTimeout(logsAuto, 1000);

// Initialize page: load favourites, refresh header/risk bar, start auto refresh
try {
  loadFavs();
} catch(e){}
// Refresh header immediately on load to display current executor and alerts status
refreshHeader().catch(()=>{});
// Start periodic header refresh (risk bar included)
headerAuto();

// Load initial radar scan after a short delay
setTimeout(() => {
  try { loadRadar(); } catch (e) {}
}, 1500);

// AI chat send handler: send question to /api/ai/chat and append response
const chatOut = document.getElementById('chat_out');
if (document.getElementById('btn_chat_send')){
  document.getElementById('btn_chat_send').onclick = async () => {
    const inp = document.getElementById('chat_input');
    const q = inp.value.trim();
    if(!q) return;
    // append user question
    chatOut.textContent += '> ' + q + '\n';
    try{
      const resp = await jpost('/api/ai/chat', {prompt: q});
      const ans = resp && resp.response ? resp.response : JSON.stringify(resp);
      chatOut.textContent += '< ' + ans + '\n';
    }catch(e){
      chatOut.textContent += '< error\n';
    }
    inp.value = '';
    // scroll to bottom
    chatOut.scrollTop = chatOut.scrollHeight;
  };
}

// Theme toggle: apply light/dark by overriding CSS variables on :root
function applyTheme(theme){
  const root = document.documentElement;
  if(theme === 'light'){
    root.style.setProperty('--bg','#f9fafb');
    root.style.setProperty('--panel','#f3f4f6');
    root.style.setProperty('--card','#ffffff');
    root.style.setProperty('--txt','#111827');
    root.style.setProperty('--muted','#6b7280');
    root.style.setProperty('--br','#d1d5db');
    root.style.setProperty('--btn','#e5e7eb');
    // keep accent color same for consistency
  } else {
    // dark default values
    root.style.setProperty('--bg','#111827');
    root.style.setProperty('--panel','#1f2937');
    root.style.setProperty('--card','#273447');
    root.style.setProperty('--txt','#e5e7eb');
    root.style.setProperty('--muted','#9ca3af');
    root.style.setProperty('--br','#374151');
    root.style.setProperty('--btn','#374151');
  }
  // update toggle button text in Russian: show next theme
  const toggleBtn = document.getElementById('theme_toggle');
  if(toggleBtn){
    // when currently in dark mode, suggest switching to light ("Светлая");
    // when in light mode, suggest switching to dark ("Тёмная")
    toggleBtn.textContent = (theme === 'dark') ? 'Светлая' : 'Тёмная';
  }
}
// initialize theme from localStorage or default dark
(function(){
  const saved = localStorage.getItem('theme') || 'dark';
  applyTheme(saved);
})();
// handle theme toggle click
if(document.getElementById('theme_toggle')){
  document.getElementById('theme_toggle').onclick = () => {
    const cur = localStorage.getItem('theme') || 'dark';
    const next = (cur === 'dark') ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem('theme', next);
  };
}

// Export trades as CSV
if(document.getElementById('tr_export')){
  document.getElementById('tr_export').onclick = async () => {
    // fetch current trades based on selected source/limit
    const src = document.getElementById('tr_src').value;
    const lim = parseInt(document.getElementById('tr_lim').value || '50', 10);
    let data;
    if(src === 'executor'){
      data = await jget('/proxy/executor/trades?limit='+lim);
    } else {
      data = await jget('/proxy/backtester/trades?limit='+lim);
    }
    const arr = (data && data.trades) ? data.trades : [];
    let csv = 'ts,kind,symbol,side,qty,px@trade,px@now,Δpx\n';
    for(const t of arr){
      const kind = (t.kind !== undefined) ? t.kind : (t.mode !== undefined ? t.mode : '');
      const pxTrade = t['px@trade'] ?? t.price ?? (t.extra && t.extra['px@trade']);
      const pxNow = t['px@now'] ?? (t.extra && t.extra['px@now']);
      const dpx = t['dpx'] ?? (t.extra && t.extra['dpx']);
      csv += `${t.ts ?? ''},${kind ?? ''},${t.symbol ?? ''},${t.side ?? ''},${t.qty ?? ''},${pxTrade ?? ''},${pxNow ?? ''},${dpx ?? ''}\n`;
    }
    const blob = new Blob([csv], {type:'text/csv'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'trades.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
}

// ====== Positions helper ======
async function loadPositions(){
  try{
    const r = await jget('/proxy/executor/positions');
    const arr = (r && r.positions) ? r.positions : [];
    const tb = document.getElementById('pos_tbody');
    if(tb) tb.innerHTML = '';
    for(const p of arr){
      const sym = p.symbol;
      let current = null;
      try{
        const pr = await jget(`/proxy/ingestor/last?symbol=${encodeURIComponent(sym)}`);
        if(pr && pr.last && pr.last.price !== undefined) current = Number(pr.last.price);
        else if(pr && pr.price !== undefined) current = Number(pr.price);
      }catch(e){}
      const avg = (p.avg_price !== undefined && p.avg_price !== null) ? Number(p.avg_price) : null;
      let pnl = null;
      if(current != null && avg != null && !Number.isNaN(avg)){
        pnl = (current - avg) * Number(p.qty);
      }
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${sym ?? ''}</td><td>${p.qty ?? ''}</td><td>${avg != null ? avg.toFixed(4) : ''}</td><td>${current != null ? current.toFixed(4) : ''}</td><td>${pnl != null ? pnl.toFixed(4) : ''}</td>`;
      if(tb) tb.appendChild(tr);
    }
  }catch(e){ const tb = document.getElementById('pos_tbody'); if(tb) tb.innerHTML = `<tr><td colspan="5">error loading positions</td></tr>`; }
}
// bind refresh button
if(document.getElementById('pos_refresh')){
  document.getElementById('pos_refresh').onclick = loadPositions;
}

// ====== Live price chart functions ======
let priceSeries = [];
const MAX_SERIES = 300;
let chartSymbol = 'BTCUSDT';

// Moving averages (short and long)
let maShort = [];
let maLong = [];
const MA_SHORT_PERIOD = 50;
const MA_LONG_PERIOD = 200;

function drawPriceChart(){
  const c = document.getElementById('price_chart');
  if(!c) return;
  const ctx = c.getContext('2d');
  // set canvas size to its displayed width and fixed height
  const w = c.width = c.clientWidth;
  const h = c.height = 220;
  ctx.clearRect(0,0,w,h);
  // grid color from CSS variable
  const rootStyles = getComputedStyle(document.documentElement);
  ctx.strokeStyle = rootStyles.getPropertyValue('--br').trim();
  ctx.lineWidth = 1;
  for(let x=0;x<w;x+=60){
    ctx.beginPath();
    ctx.moveTo(x,0);
    ctx.lineTo(x,h);
    ctx.stroke();
  }
  if(priceSeries.length < 2){
    ctx.fillStyle = rootStyles.getPropertyValue('--muted').trim();
    ctx.fillText('collecting...', 10, 20);
    return;
  }
  // include moving averages when computing min/max to keep consistent scaling
  let seriesMin = Math.min(...priceSeries);
  let seriesMax = Math.max(...priceSeries);
  // consider non-null MA values when adjusting min/max
  for(const v of maShort){ if(v != null){ if(v < seriesMin) seriesMin = v; if(v > seriesMax) seriesMax = v; } }
  for(const v of maLong){ if(v != null){ if(v < seriesMin) seriesMin = v; if(v > seriesMax) seriesMax = v; } }
  const pad = 10;
  const span = (seriesMax - seriesMin) || 1;
  // draw price series
  ctx.beginPath();
  ctx.strokeStyle = rootStyles.getPropertyValue('--accent').trim();
  ctx.lineWidth = 2;
  for(let i=0;i<priceSeries.length;i++){
    const x = pad + (w - 2*pad) * i / (MAX_SERIES - 1);
    const y = pad + (h - 2*pad) * (1 - (priceSeries[i] - seriesMin) / span);
    if(i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  // helper to draw MA lines
  function drawMA(arr, color){
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.2;
    let started = false;
    for(let i=0;i<arr.length;i++){
      const v = arr[i];
      if(v == null) { started = false; continue; }
      const x = pad + (w - 2*pad) * i / (MAX_SERIES - 1);
      const y = pad + (h - 2*pad) * (1 - (v - seriesMin) / span);
      if(!started){ ctx.moveTo(x,y); started = true; }
      else ctx.lineTo(x,y);
    }
    ctx.stroke();
  }
  // draw short and long MA lines
  const col1 = rootStyles.getPropertyValue('--ma1').trim();
  const col2 = rootStyles.getPropertyValue('--ma2').trim();
  drawMA(maShort, col1);
  drawMA(maLong, col2);
}

async function updatePriceChart(){
  try{
    const r = await jget(`/proxy/ingestor/last?symbol=${encodeURIComponent(chartSymbol)}`);
    // response may be {last: {price: ...}} or {price: ...}
    let px;
    if(r && r.last && r.last.price !== undefined) px = Number(r.last.price);
    else if(r && r.price !== undefined) px = Number(r.price);
    if(!Number.isNaN(px)){
      priceSeries.push(px);
      if(priceSeries.length > MAX_SERIES) priceSeries.shift();
      // update moving averages
      // short MA
      if(priceSeries.length >= MA_SHORT_PERIOD){
        let sum=0;
        for(let i=priceSeries.length - MA_SHORT_PERIOD; i<priceSeries.length; i++) sum += priceSeries[i];
        maShort.push(sum/MA_SHORT_PERIOD);
      } else {
        maShort.push(null);
      }
      if(maShort.length > MAX_SERIES) maShort.shift();
      // long MA
      if(priceSeries.length >= MA_LONG_PERIOD){
        let sum=0;
        for(let i=priceSeries.length - MA_LONG_PERIOD; i<priceSeries.length; i++) sum += priceSeries[i];
        maLong.push(sum/MA_LONG_PERIOD);
      } else {
        maLong.push(null);
      }
      if(maLong.length > MAX_SERIES) maLong.shift();
      drawPriceChart();
    }
  }catch(e){}
}
// poll price every second
setInterval(updatePriceChart, 1000);

function resetPriceChart(sym){
  chartSymbol = sym || 'BTCUSDT';
  priceSeries = [];
  // reset moving averages too
  maShort = [];
  maLong = [];
  drawPriceChart();
}

// handle AI training: parse returns using helper, send to backend and refresh metrics/summary
$('btn_train').onclick = async ()=> {
  const arr = parseReturns($('train_returns').value || '');
  // if no returns entered, show a helpful message and skip server call
  if(!arr || arr.length === 0){
    $('train_out').textContent = j({ok:false, error:'Введите хотя бы одно значение доходности'});
    updateTrainSummary();
    return;
  }
  try {
    const resp = await jpost('/proxy/ai/train', {returns: arr});
    $('train_out').textContent = j(resp);
  } catch (e) {
    $('train_out').textContent = j({ok:false, error:String(e)});
  }
  // update KPI and summary after training completes
  loadKPI();
  updateTrainSummary();
};

// Bind AI training input and file events to update summary
if(document.getElementById('train_returns')){
  document.getElementById('train_returns').addEventListener('input', updateTrainSummary);
}
if(document.getElementById('train_file')){
  document.getElementById('train_file').addEventListener('change', (e) => {
    const f = e.target.files && e.target.files[0];
    if(!f) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target.result || '';
      const ta = document.getElementById('train_returns');
      if(ta){ ta.value = String(text).trim(); updateTrainSummary(); }
    };
    reader.readAsText(f);
  });
}
if(document.getElementById('btn_train_clear')){
  document.getElementById('btn_train_clear').addEventListener('click', () => {
    const ta = document.getElementById('train_returns');
    if(ta){ ta.value = ''; updateTrainSummary(); }
  });
}

// Initialize training summary on page load
updateTrainSummary();

// Backtest Runner: handle backtest button click
if(document.getElementById('btn_bt_run')){
  document.getElementById('btn_bt_run').onclick = async () => {
    const returnsStr = document.getElementById('bt_returns')?.value || '';
    const sym        = document.getElementById('bt_symbol')?.value || 'TEST';
    const arr        = parseReturns(returnsStr);
    // if no returns provided, show message and skip
    if(!arr || arr.length === 0){
      const outEl = document.getElementById('bt_out');
      if(outEl) outEl.textContent = j({ok:false, error:'Введите хотя бы одно значение доходности'});
      return;
    }
    try {
      const resp = await jpost('/proxy/backtester/run', {returns: arr, symbol: sym});
      const outEl = document.getElementById('bt_out');
      if(outEl) outEl.textContent = j(resp);
      // refresh trades table if backtester source selected
      const trSrcSel = document.getElementById('tr_src');
      if(trSrcSel && trSrcSel.value === 'backtester'){
        loadTrades();
      }
    } catch(e) {
      const outEl = document.getElementById('bt_out');
      if(outEl) outEl.textContent = j({ok:false, error:String(e)});
    }
  };
}

loadFavs();
refreshHeader(); headerAuto = ()=>setInterval(refreshHeader, 10000); headerAuto(); loadKPI(); setTimeout(loadTrades, 200);
</script>
</body>
</html>
"""

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/dashboard_ops_full")

@app.get("/dashboard_ops", include_in_schema=False)
async def ops():
    return RedirectResponse(url="/dashboard_ops_full")

# Before serving the dashboard, attempt to load a modern HTML file from disk.
# If the file exists (modern_dashboard.html), its contents will override the
# embedded DASH_HTML string. This allows designers to modify the UI without
# touching this Python code. If the file is missing or cannot be read, the
# original DASH_HTML string will be served instead.
HTML_PATH_OVERRIDE = os.path.join(os.path.dirname(__file__), "modern_dashboard.html")
def _get_dashboard_html() -> str:
    try:
        with open(HTML_PATH_OVERRIDE, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return DASH_HTML

@app.get("/dashboard_ops_full", response_class=HTMLResponse)
async def dashboard_ops_full():
    return HTMLResponse(_get_dashboard_html())
