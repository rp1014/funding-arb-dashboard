"""
Gate.io USDT Perpetual Futures Collector
"""
from typing import Dict, List
from datetime import datetime
from .base import BaseCollector, TickerData
import logging

logger = logging.getLogger(__name__)

class GateCollector(BaseCollector):
    EXCHANGE_NAME = "gate"
    BASE_URL = "https://api.gateio.ws/api/v4"
    RATE_LIMIT = 10

    async def fetch_tickers(self) -> List[TickerData]:
        tickers = []
        url = f"{self.BASE_URL}/futures/usdt/tickers"
        data = await self._request("GET", url)

        if not data:
            return []

        for item in data:
            contract = item.get("contract", "")
            if not contract.endswith("_USDT"):
                continue
            try:
                ticker = TickerData(
                    exchange=self.EXCHANGE_NAME,
                    symbol=contract,
                    normalized_symbol=self.normalize_symbol(contract, self.EXCHANGE_NAME),
                    mark_price=float(item.get("mark_price", 0)) or None,
                    index_price=float(item.get("index_price", 0)) or None,
                    last_price=float(item.get("last", 0)) or None,
                    bid_price=float(item.get("highest_bid", 0)) or None,
                    ask_price=float(item.get("lowest_ask", 0)) or None,
                    volume_24h=float(item.get("volume_24h_quote", 0)) or None,
                    funding_rate=float(item.get("funding_rate", 0)) * 100 if item.get("funding_rate") else None,
                )
                next_funding = item.get("funding_next_apply")
                if next_funding:
                    ticker.next_funding_time = datetime.utcfromtimestamp(float(next_funding))
                tickers.append(ticker)
            except Exception as e:
                logger.debug(f"Gate parse error {contract}: {e}")
        return tickers

    async def fetch_funding_rates(self) -> Dict[str, Dict]:
        result = {}
        url = f"{self.BASE_URL}/futures/usdt/tickers"
        data = await self._request("GET", url)

        if not data:
            return {}

        for item in data:
            contract = item.get("contract", "")
            if not contract.endswith("_USDT"):
                continue
            try:
                rate = float(item.get("funding_rate", 0)) * 100
                next_time = None
                next_funding = item.get("funding_next_apply")
                if next_funding:
                    next_time = datetime.utcfromtimestamp(float(next_funding))
                result[contract] = {"rate": rate, "next_time": next_time, "interval": 8}
            except Exception as e:
                logger.debug(f"Gate funding error {contract}: {e}")
        return result

    async def fetch_open_interest(self) -> Dict[str, float]:
        result = {}
        url = f"{self.BASE_URL}/futures/usdt/tickers"
        data = await self._request("GET", url)

        if not data:
            return {}

        for item in data:
            contract = item.get("contract", "")
            if not contract.endswith("_USDT"):
                continue
            try:
                oi = float(item.get("total_size", 0))
                mark = float(item.get("mark_price", 0))
                if oi > 0 and mark > 0:
                    result[contract] = oi * mark
            except:
                pass
        return result