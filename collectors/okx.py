"""
OKX USDT Perpetual Swap Collector
"""
from typing import Dict, List
from datetime import datetime
from .base import BaseCollector, TickerData
import logging

logger = logging.getLogger(__name__)

class OKXCollector(BaseCollector):
    EXCHANGE_NAME = "okx"
    BASE_URL = "https://www.okx.com"
    RATE_LIMIT = 10

    async def fetch_tickers(self) -> List[TickerData]:
        tickers = []
        url = f"{self.BASE_URL}/api/v5/market/tickers"
        params = {"instType": "SWAP"}
        data = await self._request("GET", url, params=params)

        if not data or data.get("code") != "0":
            logger.error(f"OKX tickers error: {data}")
            return []

        for item in data.get("data", []):
            inst_id = item.get("instId", "")
            if not inst_id.endswith("-USDT-SWAP"):
                continue
            try:
                ticker = TickerData(
                    exchange=self.EXCHANGE_NAME,
                    symbol=inst_id,
                    normalized_symbol=self.normalize_symbol(inst_id, self.EXCHANGE_NAME),
                    last_price=float(item.get("last", 0)) or None,
                    bid_price=float(item.get("bidPx", 0)) or None,
                    ask_price=float(item.get("askPx", 0)) or None,
                    volume_24h=float(item.get("volCcy24h", 0)) or None,
                )
                tickers.append(ticker)
            except Exception as e:
                logger.debug(f"OKX parse error {inst_id}: {e}")
        return tickers

    async def fetch_funding_rates(self) -> Dict[str, Dict]:
        result = {}
        
        # 먼저 티커에서 심볼 목록 가져오기
        url = f"{self.BASE_URL}/api/v5/market/tickers"
        params = {"instType": "SWAP"}
        data = await self._request("GET", url, params=params)
        
        if not data or data.get("code") != "0":
            return {}

        symbols = [item.get("instId") for item in data.get("data", []) if item.get("instId", "").endswith("-USDT-SWAP")]
        
        # 상위 30개만 펀딩 조회 (rate limit)
        for symbol in symbols[:30]:
            fr_url = f"{self.BASE_URL}/api/v5/public/funding-rate"
            fr_params = {"instId": symbol}
            fr_data = await self._request("GET", fr_url, params=fr_params)
            
            if fr_data and fr_data.get("code") == "0" and fr_data.get("data"):
                item = fr_data["data"][0]
                try:
                    rate = float(item.get("fundingRate", 0)) * 100
                    next_ts = item.get("nextFundingTime")
                    next_time = datetime.utcfromtimestamp(int(next_ts) / 1000) if next_ts else None
                    result[symbol] = {"rate": rate, "next_time": next_time, "interval": 8}
                except Exception as e:
                    logger.debug(f"OKX funding error {symbol}: {e}")
        return result

    async def fetch_open_interest(self) -> Dict[str, float]:
        result = {}
        url = f"{self.BASE_URL}/api/v5/public/open-interest"
        params = {"instType": "SWAP"}
        data = await self._request("GET", url, params=params)

        if not data or data.get("code") != "0":
            return {}

        for item in data.get("data", []):
            inst_id = item.get("instId", "")
            if not inst_id.endswith("-USDT-SWAP"):
                continue
            try:
                oi = float(item.get("oiCcy", 0))
                if oi > 0:
                    result[inst_id] = oi
            except:
                pass
        return result