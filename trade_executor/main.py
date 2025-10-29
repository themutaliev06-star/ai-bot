from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "trade_executor is running", "status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "trade_executor"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
