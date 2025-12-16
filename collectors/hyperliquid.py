"""
Hyperliquid Perpetual DEX Collector
"""
from typing import Dict, List, Optional
from datetime import datetime
from .base import BaseCollector, TickerData
import asyncio
import logging

logger = logging.getLogger(__name__)

class HyperliquidCollector(BaseCollector):
    EXCHANGE_NAME = "hyperliquid"
    BASE_URL = "https://api.hyperliquid.xyz"
    RATE_LIMIT = 5

    async def _post_request(self, url: str, payload: Dict) -> Optional[Dict]:
        await self._rate_limit()
        for attempt in range(3):
            try:
                async with self._session.post(
                    url, json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        logger.error(f"Hyperliquid HTTP {resp.status}")
                        return None
            except Exception as e:
                logger.error(f"Hyperliquid error: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        return None

    async def fetch_tickers(self) -> List[TickerData]:
        tickers = []
        url = f"{self.BASE_URL}/info"

        # 메타 + 가격 정보
        meta_payload = {"type": "metaAndAssetCtxs"}
        data = await self._post_request(url, meta_payload)

        if not data or not isinstance(data, list) or len(data) < 2:
            return []

        meta = data[0]
        asset_ctxs = data[1]
        universe = meta.get("universe", [])

        for i, ctx in enumerate(asset_ctxs):
            if i >= len(universe):
                break
            symbol = universe[i].get("name", "")
            try:
                mark_price = float(ctx.get("markPx", 0)) or None
                ticker = TickerData(
                    exchange=self.EXCHANGE_NAME,
                    symbol=symbol,
                    normalized_symbol=f"{symbol}/USDT",
                    mark_price=mark_price,
                    last_price=mark_price,
                    funding_rate=float(ctx.get("funding", 0)) * 100 if ctx.get("funding") else None,
                    funding_interval_hours=1,
                )
                tickers.append(ticker)
            except Exception as e:
                logger.debug(f"Hyperliquid parse error {symbol}: {e}")
        return tickers

    async def fetch_funding_rates(self) -> Dict[str, Dict]:
        result = {}
        url = f"{self.BASE_URL}/info"
        meta_payload = {"type": "metaAndAssetCtxs"}
        data = await self._post_request(url, meta_payload)

        if not data or not isinstance(data, list) or len(data) < 2:
            return {}

        meta = data[0]
        asset_ctxs = data[1]
        universe = meta.get("universe", [])

        for i, ctx in enumerate(asset_ctxs):
            if i >= len(universe):
                break
            symbol = universe[i].get("name", "")
            try:
                rate = float(ctx.get("funding", 0)) * 100
                result[symbol] = {"rate": rate, "next_time": None, "interval": 1}
            except Exception as e:
                logger.debug(f"Hyperliquid funding error {symbol}: {e}")
        return result

    async def fetch_open_interest(self) -> Dict[str, float]:
        result = {}
        url = f"{self.BASE_URL}/info"
        meta_payload = {"type": "metaAndAssetCtxs"}
        data = await self._post_request(url, meta_payload)

        if not data or not isinstance(data, list) or len(data) < 2:
            return {}

        meta = data[0]
        asset_ctxs = data[1]
        universe = meta.get("universe", [])

        for i, ctx in enumerate(asset_ctxs):
            if i >= len(universe):
                break
            symbol = universe[i].get("name", "")
            try:
                oi = float(ctx.get("openInterest", 0))
                mark = float(ctx.get("markPx", 0))
                if oi > 0 and mark > 0:
                    result[symbol] = oi * mark
            except:
                pass
        return result