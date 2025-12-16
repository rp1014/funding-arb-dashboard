"""
MEXC USDT-M Futures Collector
"""
from typing import Dict, List
from datetime import datetime
from .base import BaseCollector, TickerData
import logging

logger = logging.getLogger(__name__)

class MEXCCollector(BaseCollector):
    EXCHANGE_NAME = "mexc"
    BASE_URL = "https://contract.mexc.com"
    RATE_LIMIT = 10

    async def fetch_tickers(self) -> List[TickerData]:
        tickers = []
        url = f"{self.BASE_URL}/api/v1/contract/ticker"
        data = await self._request("GET", url)

        if not data or not data.get("success"):
            logger.error(f"MEXC tickers error: {data}")
            return []

        for item in data.get("data", []):
            symbol = item.get("symbol", "")
            if not symbol.endswith("_USDT"):
                continue
            try:
                ticker = TickerData(
                    exchange=self.EXCHANGE_NAME,
                    symbol=symbol,
                    normalized_symbol=self.normalize_symbol(symbol, self.EXCHANGE_NAME),
                    last_price=float(item.get("lastPrice", 0)) or None,
                    bid_price=float(item.get("bid1", 0)) or None,
                    ask_price=float(item.get("ask1", 0)) or None,
                    volume_24h=float(item.get("volume24", 0)) or None,
                    open_interest=float(item.get("holdVol", 0)) or None,
                    funding_rate=float(item.get("fundingRate", 0)) * 100 if item.get("fundingRate") else None,
                )
                next_ms = item.get("nextSettleTime")
                if next_ms:
                    ticker.next_funding_time = datetime.utcfromtimestamp(int(next_ms) / 1000)
                tickers.append(ticker)
            except Exception as e:
                logger.debug(f"MEXC parse error {symbol}: {e}")
        return tickers

    async def fetch_funding_rates(self) -> Dict[str, Dict]:
        result = {}
        url = f"{self.BASE_URL}/api/v1/contract/ticker"
        data = await self._request("GET", url)

        if not data or not data.get("success"):
            return {}

        for item in data.get("data", []):
            symbol = item.get("symbol", "")
            if not symbol.endswith("_USDT"):
                continue
            try:
                rate = float(item.get("fundingRate", 0)) * 100
                next_time = None
                next_ms = item.get("nextSettleTime")
                if next_ms:
                    next_time = datetime.utcfromtimestamp(int(next_ms) / 1000)
                result[symbol] = {"rate": rate, "next_time": next_time, "interval": 8}
            except Exception as e:
                logger.debug(f"MEXC funding error {symbol}: {e}")
        return result

    async def fetch_open_interest(self) -> Dict[str, float]:
        result = {}
        url = f"{self.BASE_URL}/api/v1/contract/ticker"
        data = await self._request("GET", url)

        if not data or not data.get("success"):
            return {}

        for item in data.get("data", []):
            symbol = item.get("symbol", "")
            if not symbol.endswith("_USDT"):
                continue
            try:
                hold_vol = float(item.get("holdVol", 0))
                last_price = float(item.get("lastPrice", 0))
                if hold_vol > 0 and last_price > 0:
                    result[symbol] = hold_vol * last_price
            except:
                pass
        return result