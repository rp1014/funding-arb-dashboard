"""
Binance USDT-M Futures Collector
"""
from typing import Dict, List
from datetime import datetime
from .base import BaseCollector, TickerData
import logging

logger = logging.getLogger(__name__)

class BinanceCollector(BaseCollector):
    EXCHANGE_NAME = "binance"
    BASE_URL = "https://fapi.binance.com"
    RATE_LIMIT = 10

    async def fetch_tickers(self) -> List[TickerData]:
        tickers = []
        url = f"{self.BASE_URL}/fapi/v1/ticker/24hr"
        data = await self._request("GET", url)
        if not data:
            return []

        mark_url = f"{self.BASE_URL}/fapi/v1/premiumIndex"
        mark_data = await self._request("GET", mark_url)
        mark_map = {}
        if mark_data:
            for item in mark_data:
                mark_map[item["symbol"]] = {
                    "mark": float(item.get("markPrice", 0)),
                    "index": float(item.get("indexPrice", 0)),
                }

        for item in data:
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT") or "_" in symbol:
                continue
            try:
                mark_info = mark_map.get(symbol, {})
                ticker = TickerData(
                    exchange=self.EXCHANGE_NAME,
                    symbol=symbol,
                    normalized_symbol=self.normalize_symbol(symbol, self.EXCHANGE_NAME),
                    mark_price=mark_info.get("mark"),
                    index_price=mark_info.get("index"),
                    last_price=float(item.get("lastPrice", 0)),
                    bid_price=float(item.get("bidPrice", 0)) or None,
                    ask_price=float(item.get("askPrice", 0)) or None,
                    volume_24h=float(item.get("quoteVolume", 0)),
                )
                tickers.append(ticker)
            except Exception as e:
                logger.debug(f"Binance parse error {symbol}: {e}")
        return tickers

    async def fetch_funding_rates(self) -> Dict[str, Dict]:
        result = {}
        url = f"{self.BASE_URL}/fapi/v1/premiumIndex"
        data = await self._request("GET", url)
        if not data:
            return {}

        for item in data:
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT") or "_" in symbol:
                continue
            try:
                rate = float(item.get("lastFundingRate", 0)) * 100
                next_ms = int(item.get("nextFundingTime", 0))
                next_time = datetime.utcfromtimestamp(next_ms / 1000) if next_ms else None
                result[symbol] = {"rate": rate, "next_time": next_time, "interval": 8}
            except Exception as e:
                logger.debug(f"Binance funding error {symbol}: {e}")
        return result

    async def fetch_open_interest(self) -> Dict[str, float]:
        return {}