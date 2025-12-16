"""
Squeeze Radar Engine - Squeeze Score 계산 및 방향성 판정
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
import numpy as np
import sys
sys.path.append('..')
from config import squeeze_config

@dataclass
class SqueezeSignal:
    """스퀴즈 신호 데이터"""
    symbol: str
    exchange: str
    squeeze_score: float
    direction_bias: str
    oi_delta_pct: Optional[float] = None
    price_delta_pct: Optional[float] = None
    funding_level: Optional[float] = None
    funding_delta: Optional[float] = None
    volume_spike: Optional[float] = None
    spread_stress: Optional[float] = None
    oi_score: float = 0
    price_score: float = 0
    crowding_score: float = 0
    funding_accel_score: float = 0
    liquidity_score: float = 0
    notes: str = ""
    data_ok: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)


class HistoryTracker:
    """과거 데이터 추적 (변화율 계산용)"""
    def __init__(self, window_minutes: int = 60, max_points: int = 360):
        self.window_minutes = window_minutes
        self.max_points = max_points
        self._history: Dict[Tuple[str, str], deque] = {}

    def add(self, exchange: str, symbol: str, data: Dict):
        key = (exchange.lower(), symbol)
        if key not in self._history:
            self._history[key] = deque(maxlen=self.max_points)
        self._history[key].append((datetime.utcnow(), data))

    def get_delta(self, exchange: str, symbol: str, field: str, minutes: int = 60) -> Optional[float]:
        key = (exchange.lower(), symbol)
        if key not in self._history or len(self._history[key]) < 2:
            return None
        
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        history = list(self._history[key])
        
        current = history[-1][1].get(field)
        old_val = None
        for ts, data in history:
            if ts <= cutoff and field in data:
                old_val = data[field]
                break
        
        if old_val is None:
            for ts, data in history[:5]:
                if field in data:
                    old_val = data[field]
                    break
        
        if current is None or old_val is None or old_val == 0:
            return None
        return (current - old_val) / abs(old_val) * 100


class SqueezeEngine:
    """스퀴즈 점수 계산 엔진"""
    def __init__(self):
        self.config = squeeze_config
        self.history = HistoryTracker(window_minutes=self.config.lookback_window_min)

    def _normalize_score(self, value: float, max_val: float) -> float:
        if value is None:
            return 0
        return min(100, abs(value) / max_val * 100)

    def _determine_direction(self, funding: Optional[float], oi_delta: Optional[float]) -> str:
        if funding is None:
            return "Neutral"
        
        is_funding_extreme = abs(funding) > self.config.funding_extreme_threshold
        oi_increasing = oi_delta is not None and oi_delta > 0
        
        if is_funding_extreme and oi_increasing:
            if funding > 0:
                return "Long squeeze risk ↑"
            else:
                return "Short squeeze risk ↑"
        return "Neutral"

    def calculate_score(self, ticker, prev_funding: Optional[float] = None) -> SqueezeSignal:
        self.history.add(ticker.exchange, ticker.symbol, {
            "oi": ticker.open_interest,
            "price": ticker.mark_price or ticker.last_price,
            "funding": ticker.funding_rate,
        })

        oi_delta = self.history.get_delta(ticker.exchange, ticker.symbol, "oi", 60)
        price_delta = self.history.get_delta(ticker.exchange, ticker.symbol, "price", 60)
        funding_delta = None
        if ticker.funding_rate is not None and prev_funding is not None:
            funding_delta = ticker.funding_rate - prev_funding

        oi_score = self._normalize_score(oi_delta, self.config.oi_shock_max)
        price_score = self._normalize_score(price_delta, self.config.price_move_max)
        crowding_score = self._normalize_score(ticker.funding_rate, self.config.crowding_max)
        funding_accel_score = self._normalize_score(funding_delta, self.config.funding_accel_max)
        
        spread_stress = ticker.spread_bps if ticker.spread_bps else 0
        liquidity_score = self._normalize_score(spread_stress, self.config.liquidity_stress_max)

        squeeze_score = (
            self.config.weight_oi_shock * oi_score +
            self.config.weight_price_move * price_score +
            self.config.weight_crowding * crowding_score +
            self.config.weight_funding_accel * funding_accel_score +
            self.config.weight_liquidity_stress * liquidity_score
        )

        direction = self._determine_direction(ticker.funding_rate, oi_delta)

        notes_parts = []
        if oi_score > 50:
            notes_parts.append(f"OI shock {oi_delta:.1f}%")
        if crowding_score > 50:
            notes_parts.append(f"Crowded {'long' if ticker.funding_rate and ticker.funding_rate > 0 else 'short'}")
        if funding_accel_score > 50:
            notes_parts.append("Funding accelerating")
        notes = ", ".join(notes_parts) if notes_parts else "Normal"

        return SqueezeSignal(
            symbol=ticker.normalized_symbol,
            exchange=ticker.exchange,
            squeeze_score=round(squeeze_score, 1),
            direction_bias=direction,
            oi_delta_pct=round(oi_delta, 2) if oi_delta else None,
            price_delta_pct=round(price_delta, 2) if price_delta else None,
            funding_level=ticker.funding_rate,
            funding_delta=round(funding_delta, 4) if funding_delta else None,
            spread_stress=round(spread_stress, 1) if spread_stress else None,
            oi_score=round(oi_score, 1),
            price_score=round(price_score, 1),
            crowding_score=round(crowding_score, 1),
            funding_accel_score=round(funding_accel_score, 1),
            liquidity_score=round(liquidity_score, 1),
            notes=notes,
            data_ok=ticker.data_ok,
        )

    def analyze_all(self, tickers: List, prev_fundings: Dict[str, float] = None) -> List[SqueezeSignal]:
        if prev_fundings is None:
            prev_fundings = {}
        
        signals = []
        for ticker in tickers:
            if not ticker.data_ok:
                continue
            key = f"{ticker.exchange}:{ticker.symbol}"
            prev_funding = prev_fundings.get(key)
            signal = self.calculate_score(ticker, prev_funding)
            signals.append(signal)
        
        signals.sort(key=lambda x: x.squeeze_score, reverse=True)
        return signals