import aiohttp
import asyncio
import json
import time
from typing import Dict, List, Optional
import hmac
import hashlib
import urllib.parse

class BinanceClient:
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.base_url = "https://api.binance.com"
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = None

    async def get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session:
            await self.session.close()

    async def get_exchange_info(self):
        """Получает информацию о торговых парах"""
        session = await self.get_session()
        url = f"{self.base_url}/api/v3/exchangeInfo"
        async with session.get(url) as response:
            return await response.json()

    async def get_symbol_price(self, symbol: str):
        """Получает текущую цену для символа"""
        session = await self.get_session()
        url = f"{self.base_url}/api/v3/ticker/price"
        params = {"symbol": symbol}
        async with session.get(url, params=params) as response:
            return await response.json()

    async def get_klines(self, symbol: str, interval: str = "1h", limit: int = 500):
        """Получает свечные данные"""
        session = await self.get_session()
        url = f"{self.base_url}/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        async with session.get(url, params=params) as response:
            return await response.json()

    async def get_24hr_ticker(self, symbol: str):
        """Получает статистику за 24 часа"""
        session = await self.get_session()
        url = f"{self.base_url}/api/v3/ticker/24hr"
        params = {"symbol": symbol}
        async with session.get(url, params=params) as response:
            return await response.json()

    async def get_orderbook(self, symbol: str, limit: int = 100):
        """Получает стакан ордеров"""
        session = await self.get_session()
        url = f"{self.base_url}/api/v3/depth"
        params = {"symbol": symbol, "limit": limit}
        async with session.get(url, params=params) as response:
            return await response.json()