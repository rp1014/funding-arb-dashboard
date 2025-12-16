"""
Bybit USDT Perpetual Collector
"""
from typing import Dict, List
from datetime import datetime
from .base import BaseCollector, TickerData
import logging

logger = logging.getLogger(__name__)

class BybitCollector(BaseCollector):
    EXCHANGE_NAME = "bybit"
    BASE_URL = "https://api.bybit.com"
    RATE_LIMIT = 10

    async def fetch_tickers(self) -> List[TickerData]:
        tickers = []
        url = f"{self.BASE_URL}/v5/market/tickers"
        params = {"category": "linear"}
        data = await self._request("GET", url, params=params)

        if not data or data.get("retCode") != 0:
            logger.error(f"Bybit tickers error: {data}")
            return []

        for item in data.get("result", {}).get("list", []):
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            try:
                ticker = TickerData(
                    exchange=self.EXCHANGE_NAME,
                    symbol=symbol,
                    normalized_symbol=self.normalize_symbol(symbol, self.EXCHANGE_NAME),
                    mark_price=float(item.get("markPrice", 0)) or None,
                    index_price=float(item.get("indexPrice", 0)) or None,
                    last_price=float(item.get("lastPrice", 0)) or None,
                    bid_price=float(item.get("bid1Price", 0)) or None,
                    ask_price=float(item.get("ask1Price", 0)) or None,
                    volume_24h=float(item.get("turnover24h", 0)) or None,
                    open_interest=float(item.get("openInterestValue", 0)) or None,
                    funding_rate=float(item.get("fundingRate", 0)) * 100 if item.get("fundingRate") else None,
                )
                next_ms = item.get("nextFundingTime")
                if next_ms:
                    ticker.next_funding_time = datetime.utcfromtimestamp(int(next_ms) / 1000)
                tickers.append(ticker)
            except Exception as e:
                logger.debug(f"Bybit parse error {symbol}: {e}")
        return tickers

    async def fetch_funding_rates(self) -> Dict[str, Dict]:
        result = {}
        url = f"{self.BASE_URL}/v5/market/tickers"
        params = {"category": "linear"}
        data = await self._request("GET", url, params=params)

        if not data or data.get("retCode") != 0:
            return {}

        for item in data.get("result", {}).get("list", []):
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            try:
                rate = float(item.get("fundingRate", 0)) * 100
                next_time = None
                next_ms = item.get("nextFundingTime")
                if next_ms:
                    next_time = datetime.utcfromtimestamp(int(next_ms) / 1000)
                result[symbol] = {"rate": rate, "next_time": next_time, "interval": 8}
            except Exception as e:
                logger.debug(f"Bybit funding error {symbol}: {e}")
        return result

    async def fetch_open_interest(self) -> Dict[str, float]:
        result = {}
        url = f"{self.BASE_URL}/v5/market/tickers"
        params = {"category": "linear"}
        data = await self._request("GET", url, params=params)

        if not data or data.get("retCode") != 0:
            return {}

        for item in data.get("result", {}).get("list", []):
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            try:
                oi = float(item.get("openInterestValue", 0))
                if oi > 0:
                    result[symbol] = oi
            except:
                pass
        return result
