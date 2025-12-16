"""
Funding Arbitrage Engine - Net Edge, Gap Stability 계산
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
import numpy as np
import sys
sys.path.append('..')
from config import funding_arb_config, EXCHANGE_FEES

@dataclass
class ArbOpportunity:
    """아비트라지 기회 데이터"""
    symbol: str
    exchange_a: str
    price_a: float
    funding_a: float
    next_funding_min_a: Optional[float]
    exchange_b: str
    price_b: float
    funding_b: float
    next_funding_min_b: Optional[float]
    gap_pct: float
    spread_cost_bps: float
    gap_stability: float
    net_edge: float
    best_leg: str
    data_ok: bool = True
    warning: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def funding_diff(self) -> float:
        return self.funding_a - self.funding_b


class GapTracker:
    """갭 히스토리 추적"""
    def __init__(self, window_minutes: int = 60, max_points: int = 360):
        self.window_minutes = window_minutes
        self.max_points = max_points
        self._history: Dict[Tuple[str, str, str], deque] = {}

    def _key(self, symbol: str, ex_a: str, ex_b: str) -> Tuple[str, str, str]:
        if ex_a > ex_b:
            ex_a, ex_b = ex_b, ex_a
        return (symbol, ex_a, ex_b)

    def add(self, symbol: str, ex_a: str, ex_b: str, gap_pct: float):
        key = self._key(symbol, ex_a, ex_b)
        if key not in self._history:
            self._history[key] = deque(maxlen=self.max_points)
        self._history[key].append((datetime.utcnow(), gap_pct))

    def get_stability(self, symbol: str, ex_a: str, ex_b: str) -> float:
        key = self._key(symbol, ex_a, ex_b)
        if key not in self._history:
            return 999.0
        cutoff = datetime.utcnow() - timedelta(minutes=self.window_minutes)
        recent = [gap for ts, gap in self._history[key] if ts >= cutoff]
        if len(recent) < 3:
            return 999.0
        return float(np.std(recent))


class FundingArbEngine:
    """펀딩 아비트라지 계산 엔진"""
    def __init__(self):
        self.config = funding_arb_config
        self.gap_tracker = GapTracker(window_minutes=self.config.gap_stability_window_min)

    def calculate_spread_cost(self, ticker_a, ticker_b) -> float:
        cost_a = ticker_a.spread_bps if ticker_a.spread_bps else self.config.default_spread_bps
        cost_b = ticker_b.spread_bps if ticker_b.spread_bps else self.config.default_spread_bps
        return cost_a + cost_b

    def calculate_fee_cost(self, exchange_a: str, exchange_b: str) -> float:
        fee_a = EXCHANGE_FEES.get(exchange_a, {"taker": 0.05})
        fee_b = EXCHANGE_FEES.get(exchange_b, {"taker": 0.05})
        return (fee_a["taker"] + fee_b["taker"]) * 2

    def calculate_net_edge(self, funding_receive: float, funding_pay: float, 
                          fee_cost: float, spread_cost_bps: float, gap_stability: float) -> float:
        funding_diff = funding_receive - funding_pay
        spread_pct = spread_cost_bps / 100
        gap_penalty = gap_stability * self.config.gap_risk_penalty_weight if gap_stability < 100 else 0
        return funding_diff - fee_cost - spread_pct - gap_penalty

    def find_opportunities(self, tickers_by_exchange: Dict[str, Dict], 
                          min_volume: float = 0, min_edge: Optional[float] = None) -> List[ArbOpportunity]:
        if min_edge is None:
            min_edge = self.config.min_net_edge
        
        opportunities = []
        exchanges = list(tickers_by_exchange.keys())

        for i, ex_a in enumerate(exchanges):
            for ex_b in exchanges[i+1:]:
                tickers_a = tickers_by_exchange[ex_a]
                tickers_b = tickers_by_exchange[ex_b]
                common_symbols = set(tickers_a.keys()) & set(tickers_b.keys())

                for symbol in common_symbols:
                    ticker_a = tickers_a[symbol]
                    ticker_b = tickers_b[symbol]

                    if not ticker_a.data_ok or not ticker_b.data_ok:
                        continue
                    if ticker_a.funding_rate is None or ticker_b.funding_rate is None:
                        continue
                    if ticker_a.mark_price is None or ticker_b.mark_price is None:
                        continue

                    vol_a = ticker_a.volume_24h or 0
                    vol_b = ticker_b.volume_24h or 0
                    if min(vol_a, vol_b) < min_volume:
                        continue

                    if ticker_a.funding_rate >= ticker_b.funding_rate:
                        short_ticker, short_ex = ticker_a, ex_a
                        long_ticker, long_ex = ticker_b, ex_b
                    else:
                        short_ticker, short_ex = ticker_b, ex_b
                        long_ticker, long_ex = ticker_a, ex_a

                    mid_price = (short_ticker.mark_price + long_ticker.mark_price) / 2
                    gap_pct = (long_ticker.mark_price - short_ticker.mark_price) / mid_price * 100

                    self.gap_tracker.add(symbol, ex_a, ex_b, gap_pct)
                    gap_stability = self.gap_tracker.get_stability(symbol, ex_a, ex_b)

                    spread_cost = self.calculate_spread_cost(short_ticker, long_ticker)
                    fee_cost = self.calculate_fee_cost(short_ex, long_ex)

                    net_edge = self.calculate_net_edge(
                        funding_receive=abs(short_ticker.funding_rate),
                        funding_pay=abs(long_ticker.funding_rate) if long_ticker.funding_rate < 0 else 0,
                        fee_cost=fee_cost,
                        spread_cost_bps=spread_cost,
                        gap_stability=gap_stability
                    )

                    warning = None
                    if abs(gap_pct) > self.config.gap_cutoff_threshold:
                        continue
                    elif abs(gap_pct) > self.config.gap_warning_threshold:
                        warning = f"Gap warning: {gap_pct:.3f}%"

                    if net_edge < min_edge:
                        continue

                    opp = ArbOpportunity(
                        symbol=symbol,
                        exchange_a=short_ex,
                        price_a=short_ticker.mark_price,
                        funding_a=short_ticker.funding_rate,
                        next_funding_min_a=short_ticker.minutes_to_funding,
                        exchange_b=long_ex,
                        price_b=long_ticker.mark_price,
                        funding_b=long_ticker.funding_rate,
                        next_funding_min_b=long_ticker.minutes_to_funding,
                        gap_pct=gap_pct,
                        spread_cost_bps=spread_cost,
                        gap_stability=gap_stability if gap_stability < 100 else float('inf'),
                        net_edge=net_edge,
                        best_leg=f"{short_ex.capitalize()} SHORT / {long_ex.capitalize()} LONG",
                        warning=warning,
                    )
                    opportunities.append(opp)

        opportunities.sort(key=lambda x: x.net_edge, reverse=True)
        return opportunities