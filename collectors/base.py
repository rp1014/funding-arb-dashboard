"""
Base Collector - 모든 거래소 수집기의 추상 베이스 클래스
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)

@dataclass
class TickerData:
    """정규화된 티커 데이터"""
    exchange: str
    symbol: str
    normalized_symbol: str
    mark_price: Optional[float] = None
    index_price: Optional[float] = None
    last_price: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    funding_rate: Optional[float] = None
    predicted_funding_rate: Optional[float] = None
    next_funding_time: Optional[datetime] = None
    funding_interval_hours: int = 8
    open_interest: Optional[float] = None
    open_interest_change_1h: Optional[float] = None
    volume_24h: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data_ok: bool = True
    error_msg: Optional[str] = None

    @property
    def spread_bps(self) -> Optional[float]:
        if self.bid_price and self.ask_price and self.bid_price > 0:
            mid = (self.bid_price + self.ask_price) / 2
            return (self.ask_price - self.bid_price) / mid * 10000
        return None

    @property
    def minutes_to_funding(self) -> Optional[float]:
        if self.next_funding_time:
            delta = self.next_funding_time - datetime.utcnow()
            return max(0, delta.total_seconds() / 60)
        return None

class BaseCollector(ABC):
    EXCHANGE_NAME: str = "base"
    BASE_URL: str = ""
    RATE_LIMIT: int = 10

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self._own_session = False
        self._last_request_time = 0
        self._request_interval = 1.0 / self.RATE_LIMIT

    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self._session:
            await self._session.close()

    async def _rate_limit(self):
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self._request_interval:
            await asyncio.sleep(self._request_interval - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _request(self, method: str, url: str, params: Dict = None, timeout: int = 10) -> Optional[Dict]:
        await self._rate_limit()
        for attempt in range(3):
            try:
                async with self._session.request(method, url, params=params, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        logger.error(f"{self.EXCHANGE_NAME} HTTP {resp.status}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"{self.EXCHANGE_NAME} timeout (attempt {attempt+1})")
            except Exception as e:
                logger.error(f"{self.EXCHANGE_NAME} error: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        return None

    @abstractmethod
    async def fetch_tickers(self) -> List[TickerData]:
        pass

    @abstractmethod
    async def fetch_funding_rates(self) -> Dict[str, Dict]:
        pass

    @abstractmethod
    async def fetch_open_interest(self) -> Dict[str, float]:
        pass

    async def fetch_all(self) -> List[TickerData]:
        try:
            tickers, funding_map, oi_map = await asyncio.gather(
                self.fetch_tickers(), self.fetch_funding_rates(), self.fetch_open_interest(),
                return_exceptions=True
            )
            if isinstance(tickers, Exception): tickers = []
            if isinstance(funding_map, Exception): funding_map = {}
            if isinstance(oi_map, Exception): oi_map = {}

            for ticker in tickers:
                if ticker.symbol in funding_map:
                    f = funding_map[ticker.symbol]
                    ticker.funding_rate = f.get("rate")
                    ticker.next_funding_time = f.get("next_time")
                if ticker.symbol in oi_map:
                    ticker.open_interest = oi_map[ticker.symbol]
            return tickers
        except Exception as e:
            logger.error(f"{self.EXCHANGE_NAME} fetch_all error: {e}")
            return []

    @staticmethod
    def normalize_symbol(symbol: str, exchange: str) -> str:
        s = symbol.upper()
        for suffix in ["-SWAP", "-PERP", "_PERP", ":USDT", "_UMCBL"]:
            s = s.replace(suffix, "")
        s = s.replace("-", "").replace("_", "").replace("/", "")
        if s.endswith("USDT"):
            return f"{s[:-4]}/USDT"
        return symbol