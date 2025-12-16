"""
Symbol Mapper - 거래소별 심볼을 공통 형식으로 정규화
"""
from typing import Dict, List, Optional, Tuple

def normalize_symbol(symbol: str, exchange: str = "") -> str:
    """
    거래소별 심볼을 공통 형식 (BASE/QUOTE)으로 변환
    예: BTCUSDT → BTC/USDT, BTC-USDT-SWAP → BTC/USDT
    """
    s = symbol.upper().strip()
    
    suffixes = ["-SWAP", "-PERP", "_PERP", ":USDT", "_UMCBL", "-FUTURES", "_FUTURES"]
    for suffix in suffixes:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 2:
            return f"{parts[0]}/{parts[1]}"
    
    for sep in ["-", "_"]:
        if sep in s:
            parts = s.split(sep)
            if len(parts) >= 2 and parts[1] in ["USDT", "USD", "USDC", "BUSD"]:
                return f"{parts[0]}/{parts[1]}"
    
    quotes = ["USDT", "USDC", "BUSD", "USD"]
    for quote in quotes:
        if s.endswith(quote):
            base = s[:-len(quote)]
            if base:
                return f"{base}/{quote}"
    
    return symbol


class SymbolMapper:
    """거래소 간 심볼 매핑 관리"""
    
    SPECIAL_MAPPINGS: Dict[str, Dict[str, str]] = {
        "BTC/USDT": {
            "binance": "BTCUSDT", "bybit": "BTCUSDT", "okx": "BTC-USDT-SWAP",
            "gate": "BTC_USDT", "bitget": "BTCUSDT", "mexc": "BTC_USDT", "hyperliquid": "BTC",
        },
        "ETH/USDT": {
            "binance": "ETHUSDT", "bybit": "ETHUSDT", "okx": "ETH-USDT-SWAP",
            "gate": "ETH_USDT", "bitget": "ETHUSDT", "mexc": "ETH_USDT", "hyperliquid": "ETH",
        },
    }

    def __init__(self):
        self._reverse_map: Dict[Tuple[str, str], str] = {}
        self._build_reverse_map()

    def _build_reverse_map(self):
        for normalized, exchange_map in self.SPECIAL_MAPPINGS.items():
            for exchange, raw_symbol in exchange_map.items():
                self._reverse_map[(exchange.lower(), raw_symbol.upper())] = normalized

    def to_normalized(self, symbol: str, exchange: str) -> str:
        key = (exchange.lower(), symbol.upper())
        if key in self._reverse_map:
            return self._reverse_map[key]
        return normalize_symbol(symbol, exchange)

    def to_exchange(self, normalized_symbol: str, exchange: str) -> Optional[str]:
        exchange = exchange.lower()
        if normalized_symbol in self.SPECIAL_MAPPINGS:
            return self.SPECIAL_MAPPINGS[normalized_symbol].get(exchange)
        
        parts = normalized_symbol.split("/")
        if len(parts) != 2:
            return None
        base, quote = parts
        
        formats = {
            "binance": f"{base}{quote}", "bybit": f"{base}{quote}",
            "okx": f"{base}-{quote}-SWAP", "gate": f"{base}_{quote}",
            "bitget": f"{base}{quote}", "mexc": f"{base}_{quote}", "hyperliquid": base,
        }
        return formats.get(exchange, f"{base}{quote}")

    def find_common_symbols(self, exchange_symbols: Dict[str, List[str]]) -> Dict[str, Dict[str, str]]:
        normalized_map: Dict[str, Dict[str, str]] = {}
        for exchange, symbols in exchange_symbols.items():
            for raw_symbol in symbols:
                normalized = self.to_normalized(raw_symbol, exchange)
                if normalized not in normalized_map:
                    normalized_map[normalized] = {}
                normalized_map[normalized][exchange] = raw_symbol
        return {n: e for n, e in normalized_map.items() if len(e) >= 2}


def get_mapper() -> SymbolMapper:
    return SymbolMapper()