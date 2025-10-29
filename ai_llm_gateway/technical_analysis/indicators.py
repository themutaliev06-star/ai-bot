import numpy as np
import pandas as pd
from typing import List, Tuple, Dict

class TechnicalIndicators:
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """Вычисляет RSI (Relative Strength Index)"""
        if len(prices) < period:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

    @staticmethod
    def calculate_macd(prices: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict:
        """Вычисляет MACD"""
        if len(prices) < slow_period:
            return {"macd": 0, "signal": 0, "histogram": 0}
        
        exp1 = pd.Series(prices).ewm(span=fast_period, adjust=False).mean()
        exp2 = pd.Series(prices).ewm(span=slow_period, adjust=False).mean()
        
        macd = exp1 - exp2
        signal = macd.ewm(span=signal_period, adjust=False).mean()
        histogram = macd - signal
        
        return {
            "macd": round(macd.iloc[-1], 4),
            "signal": round(signal.iloc[-1], 4),
            "histogram": round(histogram.iloc[-1], 4)
        }

    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, num_std: int = 2) -> Dict:
        """Вычисляет Bollinger Bands"""
        if len(prices) < period:
            return {"upper": 0, "middle": 0, "lower": 0, "width": 0}
        
        series = pd.Series(prices[-period:])
        middle = series.mean()
        std = series.std()
        
        upper = middle + (std * num_std)
        lower = middle - (std * num_std)
        width = (upper - lower) / middle  # Относительная ширина
        
        return {
            "upper": round(upper, 2),
            "middle": round(middle, 2),
            "lower": round(lower, 2),
            "width": round(width, 4)
        }

    @staticmethod
    def calculate_support_resistance(prices: List[float], window: int = 20) -> Dict:
        """Вычисляет уровни поддержки и сопротивления"""
        if len(prices) < window:
            return {"support": 0, "resistance": 0}
        
        recent_prices = prices[-window:]
        support = min(recent_prices)
        resistance = max(recent_prices)
        
        return {
            "support": round(support, 2),
            "resistance": round(resistance, 2)
        }

    @staticmethod
    def detect_trend(prices: List[float], short_window: int = 10, long_window: int = 30) -> str:
        """Определяет тренд"""
        if len(prices) < long_window:
            return "neutral"
        
        short_ma = np.mean(prices[-short_window:])
        long_ma = np.mean(prices[-long_window:])
        
        if short_ma > long_ma * 1.02:  # 2% выше
            return "bullish"
        elif short_ma < long_ma * 0.98:  # 2% ниже
            return "bearish"
        else:
            return "neutral"