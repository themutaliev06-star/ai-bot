import asyncio
import json
from datetime import datetime
from typing import Dict, List
from market_data.binance_client import BinanceClient
from technical_analysis.indicators import TechnicalIndicators

class AIRadar:
    def __init__(self):
        self.binance = BinanceClient()
        self.indicators = TechnicalIndicators()
        self.symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "SOLUSDT", "DOTUSDT"]
        self.analysis_results = {}

    async def analyze_symbol(self, symbol: str) -> Dict:
        """Анализирует один символ"""
        try:
            # Получаем данные
            klines = await self.binance.get_klines(symbol, "1h", 100)
            prices = [float(k[4]) for k in klines]  # Цены закрытия
            
            if len(prices) < 26:  # Минимум для индикаторов
                return {"error": "Недостаточно данных"}
            
            current_price = prices[-1]
            
            # Вычисляем индикаторы
            rsi = self.indicators.calculate_rsi(prices)
            macd = self.indicators.calculate_macd(prices)
            bollinger = self.indicators.calculate_bollinger_bands(prices)
            support_resistance = self.indicators.calculate_support_resistance(prices)
            trend = self.indicators.detect_trend(prices)
            
            # Генерируем сигналы
            signals = self._generate_signals(rsi, macd, bollinger, current_price)
            
            return {
                "symbol": symbol,
                "price": current_price,
                "timestamp": datetime.now().isoformat(),
                "indicators": {
                    "rsi": rsi,
                    "macd": macd,
                    "bollinger_bands": bollinger,
                    "support_resistance": support_resistance,
                    "trend": trend
                },
                "signals": signals,
                "recommendation": self._get_recommendation(signals)
            }
            
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def _generate_signals(self, rsi: float, macd: Dict, bollinger: Dict, price: float) -> Dict:
        """Генерирует торговые сигналы на основе индикаторов"""
        signals = {}
        
        # RSI сигналы
        signals["rsi_oversold"] = rsi < 30
        signals["rsi_overbought"] = rsi > 70
        signals["rsi_neutral"] = 30 <= rsi <= 70
        
        # MACD сигналы
        signals["macd_bullish"] = macd["histogram"] > 0
        signals["macd_bearish"] = macd["histogram"] < 0
        
        # Bollinger Bands сигналы
        signals["bb_oversold"] = price < bollinger["lower"]
        signals["bb_overbought"] = price > bollinger["upper"]
        signals["bb_squeeze"] = bollinger["width"] < 0.01  # Узкие полосы
        
        return signals

    def _get_recommendation(self, signals: Dict) -> str:
        """Формирует общую рекомендацию"""
        bullish_signals = sum([
            signals["rsi_oversold"],
            signals["macd_bullish"],
            signals["bb_oversold"]
        ])
        
        bearish_signals = sum([
            signals["rsi_overbought"], 
            signals["macd_bearish"],
            signals["bb_overbought"]
        ])
        
        if bullish_signals > bearish_signals:
            return "BUY"
        elif bearish_signals > bullish_signals:
            return "SELL"
        else:
            return "HOLD"

    async def scan_market(self) -> Dict:
        """Сканирует весь рынок"""
        tasks = [self.analyze_symbol(symbol) for symbol in self.symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        self.analysis_results = {
            "timestamp": datetime.now().isoformat(),
            "symbols": {}
        }
        
        for result in results:
            if isinstance(result, dict) and "symbol" in result:
                self.analysis_results["symbols"][result["symbol"]] = result
        
        return self.analysis_results

    async def close(self):
        """Закрывает соединения"""
        await self.binance.close()

# Глобальный экземпляр радара
ai_radar = AIRadar()