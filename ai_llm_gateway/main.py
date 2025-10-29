from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

from api_data import router as data_router

# Загружаем переменные окружения
load_dotenv()

app = FastAPI(
    title="AI LLM Gateway",
    description="Шлюз для AI торгового бота",
    version="1.0.0"
)

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(data_router)

# Функция для чтения HTML файлов из папки templates
def read_html_file(filename):
    try:
        with open(f"templates/{filename}", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Если файл не найден, возвращаем простую страницу
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>AI Trading Bot</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body>
            <div class="container">
                <h1>Файл {filename} не найден</h1>
                <p>Но статические файлы работают!</p>
            </div>
        </body>
        </html>
        """

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    content = read_html_file("dashboard_ops.html")
    return HTMLResponse(content=content)

@app.get("/dashboard_ops", response_class=HTMLResponse)
async def dashboard_ops(request: Request):
    content = read_html_file("dashboard_ops.html")
    return HTMLResponse(content=content)

@app.get("/radar", response_class=HTMLResponse)
async def radar(request: Request):
    content = read_html_file("radar.html")
    return HTMLResponse(content=content)

@app.get("/trades", response_class=HTMLResponse)
async def trades(request: Request):
    content = read_html_file("trades.html")
    return HTMLResponse(content=content)

@app.get("/positions", response_class=HTMLResponse)
async def positions(request: Request):
    content = read_html_file("positions.html")
    return HTMLResponse(content=content)

@app.get("/backtest", response_class=HTMLResponse)
async def backtest(request: Request):
    content = read_html_file("backtest.html")
    return HTMLResponse(content=content)

@app.get("/training", response_class=HTMLResponse)
async def training(request: Request):
    content = read_html_file("training.html")
    return HTMLResponse(content=content)

@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    content = read_html_file("settings.html")
    return HTMLResponse(content=content)

@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    content = read_html_file("help.html")
    return HTMLResponse(content=content)

@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    content = read_html_file("test.html")
    return HTMLResponse(content=content)

@app.get("/api/status")
async def api_status():
    return {"status": "ok", "service": "ai_llm_gateway"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT_GATEWAY", 8800))
    uvicorn.run(app, host="0.0.0.0", port=port)