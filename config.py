"""
Funding Arbitrage Dashboard Configuration
"""
from dataclasses import dataclass, field
from typing import Dict, List

# 거래소 목록
CEX_EXCHANGES = ["binance", "bybit", "okx", "gate", "bitget", "mexc"]
DEX_EXCHANGES = ["hyperliquid", "lighter", "variational"]
ALL_EXCHANGES = CEX_EXCHANGES + DEX_EXCHANGES

# 거래소별 수수료 (maker/taker, 단위: %)
EXCHANGE_FEES: Dict[str, Dict[str, float]] = {
    "binance": {"maker": 0.02, "taker": 0.05},
    "bybit": {"maker": 0.02, "taker": 0.055},
    "okx": {"maker": 0.02, "taker": 0.05},
    "gate": {"maker": 0.02, "taker": 0.05},
    "bitget": {"maker": 0.02, "taker": 0.06},
    "mexc": {"maker": 0.02, "taker": 0.06},
    "hyperliquid": {"maker": 0.02, "taker": 0.05},
    "lighter": {"maker": 0.02, "taker": 0.05},
    "variational": {"maker": 0.02, "taker": 0.05},
}

# 펀딩 주기 (시간)
FUNDING_INTERVALS: Dict[str, int] = {
    "binance": 8, "bybit": 8, "okx": 8, "gate": 8,
    "bitget": 8, "mexc": 8, "hyperliquid": 1,
    "lighter": 1, "variational": 8,
}

# Rate Limit (초당 요청 수)
RATE_LIMITS: Dict[str, int] = {
    "binance": 10, "bybit": 10, "okx": 10, "gate": 10,
    "bitget": 10, "mexc": 10, "hyperliquid": 5,
    "lighter": 5, "variational": 5,
}

@dataclass
class FundingArbConfig:
    gap_warning_threshold: float = 0.05
    gap_cutoff_threshold: float = 0.10
    gap_stability_window_min: int = 60
    gap_risk_penalty_weight: float = 0.5
    default_spread_bps: float = 5.0
    min_net_edge: float = 0.0
    data_stale_threshold_sec: int = 30

@dataclass
class SqueezeConfig:
    weight_oi_shock: float = 0.30
    weight_price_move: float = 0.20
    weight_crowding: float = 0.20
    weight_funding_accel: float = 0.15
    weight_liquidity_stress: float = 0.15
    oi_shock_max: float = 10.0
    price_move_max: float = 5.0
    crowding_max: float = 0.1
    funding_accel_max: float = 0.05
    liquidity_stress_max: float = 50
    funding_extreme_threshold: float = 0.05
    lookback_window_min: int = 60

@dataclass
class UIConfig:
    refresh_interval_sec: int = 10
    max_rows_display: int = 100
    default_min_volume_24h: float = 1_000_000
    time_windows: List[str] = field(default_factory=lambda: ["1h", "4h", "8h", "24h"])

funding_arb_config = FundingArbConfig()
squeeze_config = SqueezeConfig()
ui_config = UIConfig()