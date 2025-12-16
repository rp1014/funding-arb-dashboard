"""
Collectors Package
"""
from .base import BaseCollector, TickerData
from .binance import BinanceCollector
from .bybit import BybitCollector
from .okx import OKXCollector
from .gate import GateCollector
from .bitget import BitgetCollector
from .mexc import MEXCCollector
from .hyperliquid import HyperliquidCollector
from .lighter import LighterCollector
from .variational import VariationalCollector

COLLECTOR_MAP = {
    "binance": BinanceCollector,
    "bybit": BybitCollector,
    "okx": OKXCollector,
    "gate": GateCollector,
    "bitget": BitgetCollector,
    "mexc": MEXCCollector,
    "hyperliquid": HyperliquidCollector,
    "lighter": LighterCollector,
    "variational": VariationalCollector,
}

__all__ = [
    "BaseCollector", "TickerData", "COLLECTOR_MAP",
]
