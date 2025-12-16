"""
Variational DEX Collector (Placeholder)
TODO: 실제 API 엔드포인트 확인 후 구현
"""
from typing import Dict, List
from .base import BaseCollector, TickerData
import logging

logger = logging.getLogger(__name__)

class VariationalCollector(BaseCollector):
    EXCHANGE_NAME = "variational"
    BASE_URL = "https://api.variational.io"
    RATE_LIMIT = 5

    async def fetch_tickers(self) -> List[TickerData]:
        # TODO: API 스펙 확인 후 구현
        logger.warning("Variational collector not implemented yet")
        return []

    async def fetch_funding_rates(self) -> Dict[str, Dict]:
        return {}

    async def fetch_open_interest(self) -> Dict[str, float]:
        return {}