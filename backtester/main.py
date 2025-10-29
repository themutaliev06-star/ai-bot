﻿from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "backtester is running", "status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "backtester"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
