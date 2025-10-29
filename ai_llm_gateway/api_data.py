import json
import random
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

# Создаём router ПЕРВЫМ делом!
router = APIRouter()

# Тестовые данные для демонстрации
@router.get("/api/balance")
async def get_balance():
    """Возвращает текущий баланс и PnL"""
    return {
        "total_balance": 15427.50,
        "available_balance": 8421.75,
        "pnl_total": 3247.50,
        "pnl_today": 142.30,
        "win_rate": 67.8,
        "sharpe_ratio": 1.24,
        "max_drawdown": -8.45
    }

@router.get("/api/positions")
async def get_positions():
    """Возвращает текущие позиции"""
    return [
        {
            "symbol": "BTCUSDT",
            "size": 0.15,
            "entry_price": 42500.0,
            "current_price": 43820.5,
            "unrealized_pnl": 198.08,
            "pnl_percent": 3.1
        },
        {
            "symbol": "ETHUSDT",
            "size": 2.3,
            "entry_price": 2540.0,
            "current_price": 2621.8,
            "unrealized_pnl": 188.14,
            "pnl_percent": 3.2
        }
    ]

@router.get("/api/market_data")
async def get_market_data():
    """Возвращает рыночные данные"""
    return {
        "BTCUSDT": {
            "price": 43820.5, 
            "change_24h": 2.34,
            "volume": 2850000000,
            "high_24h": 44200.0,
            "low_24h": 43250.0
        },
        "ETHUSDT": {
            "price": 2621.8, 
            "change_24h": 1.87,
            "volume": 1200000000,
            "high_24h": 2650.0,
            "low_24h": 2580.0
        },
        "ADAUSDT": {
            "price": 0.512, 
            "change_24h": -0.45,
            "volume": 350000000,
            "high_24h": 0.525,
            "low_24h": 0.508
        }
    }

@router.get("/api/radar_signals")
async def get_radar_signals(threshold: float = 0.005):
    """Возвращает сигналы радара"""
    signals = [
        {"symbol": "BTCUSDT", "price": 43820.5, "change": 0.0234, "volume_change": 15.6},
        {"symbol": "SOLUSDT", "price": 142.3, "change": 0.0156, "volume_change": 22.1},
        {"symbol": "AVAXUSDT", "price": 34.56, "change": 0.0087, "volume_change": 18.3}
    ]
    
    # Фильтруем по порогу
    filtered_signals = [s for s in signals if abs(s["change"]) >= threshold]
    return filtered_signals

@router.get("/api/trades")
async def get_trades(limit: int = 10):
    """Возвращает историю сделок"""
    return [
        {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "size": 0.1,
            "price": 42500.0,
            "timestamp": "2024-01-15T10:30:00Z",
            "pnl": 132.05
        },
        {
            "symbol": "ETHUSDT", 
            "side": "SELL",
            "size": 1.5,
            "price": 2610.0,
            "timestamp": "2024-01-15T09:15:00Z", 
            "pnl": 45.20
        }
    ]

@router.get("/api/health")
async def health_check():
    """Проверка статуса сервиса"""
    return {
        "status": "healthy",
        "service": "ai_llm_gateway",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

# ============================================
# AI RADAR ENDPOINTS - ДОБАВЛЯЕМ ПОСЛЕ ОСНОВНЫХ
# ============================================

# Импортируем AI Radar только когда он нужен, чтобы избежать циклических импортов
try:
    from services.ai_radar import ai_radar
    
    @router.get("/api/ai_radar/scan")
    async def ai_radar_scan():
        """Запускает полное сканирование рынка AI радаром"""
        try:
            results = await ai_radar.scan_market()
            return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI Radar error: {str(e)}")

    @router.get("/api/ai_radar/symbol/{symbol}")
    async def ai_radar_symbol(symbol: str):
        """Анализирует конкретный символ"""
        try:
            result = await ai_radar.analyze_symbol(symbol.upper())
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI Radar error: {str(e)}")

    @router.get("/api/ai_radar/signals")
    async def ai_radar_signals():
        """Возвращает только сигналы"""
        try:
            results = await ai_radar.scan_market()
            signals = {}
            
            for symbol, data in results["symbols"].items():
                if "signals" in data:
                    signals[symbol] = {
                        "price": data.get("price"),
                        "recommendation": data.get("recommendation"),
                        "signals": data.get("signals", {}),
                        "trend": data.get("indicators", {}).get("trend", "neutral")
                    }
            
            return {
                "timestamp": results["timestamp"],
                "signals": signals
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI Radar error: {str(e)}")

except ImportError as e:
    print(f"⚠️ AI Radar module not available: {e}")
    
    # Заглушки для AI Radar endpoints если модуль не доступен
    @router.get("/api/ai_radar/scan")
    async def ai_radar_scan_stub():
        return {"error": "AI Radar module not installed", "timestamp": datetime.now().isoformat()}
    
    @router.get("/api/ai_radar/symbol/{symbol}")
    async def ai_radar_symbol_stub(symbol: str):
        return {"error": "AI Radar module not installed", "symbol": symbol, "timestamp": datetime.now().isoformat()}
    
    @router.get("/api/ai_radar/signals")
    async def ai_radar_signals_stub():
        return {"error": "AI Radar module not installed", "timestamp": datetime.now().isoformat()}