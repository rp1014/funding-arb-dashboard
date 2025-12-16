"""
Funding Arbitrage & Squeeze Radar Dashboard
"""
import streamlit as st
import pandas as pd
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, List

from config import ALL_EXCHANGES, CEX_EXCHANGES, DEX_EXCHANGES, ui_config
from collectors import COLLECTOR_MAP
from collectors.base import TickerData
from engine.funding_arb import FundingArbEngine
from engine.squeeze import SqueezeEngine

st.set_page_config(page_title="Funding Arb & Squeeze Radar", layout="wide")

# 엔진 초기화 (세션 유지)
if "arb_engine" not in st.session_state:
    st.session_state.arb_engine = FundingArbEngine()
if "squeeze_engine" not in st.session_state:
    st.session_state.squeeze_engine = SqueezeEngine()
if "prev_fundings" not in st.session_state:
    st.session_state.prev_fundings = {}


async def fetch_all_exchanges(exchanges: List[str]) -> Dict[str, List[TickerData]]:
    """모든 거래소 데이터 수집"""
    results = {}
    async with aiohttp.ClientSession() as session:
        tasks = []
        for ex in exchanges:
            if ex in COLLECTOR_MAP:
                collector = COLLECTOR_MAP[ex](session=session)
                tasks.append((ex, collector.fetch_all()))
        
        for ex, task in tasks:
            try:
                tickers = await task
                results[ex] = tickers
            except Exception as e:
                st.warning(f"{ex} 수집 실패: {e}")
                results[ex] = []
    return results


def run_async(coro):
    """비동기 함수 실행"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def build_ticker_map(all_data: Dict[str, List[TickerData]]) -> Dict[str, Dict[str, TickerData]]:
    """거래소별 → 정규화심볼별 티커 맵"""
    result = {}
    for exchange, tickers in all_data.items():
        result[exchange] = {}
        for t in tickers:
            result[exchange][t.normalized_symbol] = t
    return result


# ===== UI =====
st.title("📊 Funding Arbitrage & Squeeze Radar")

# 사이드바 필터
st.sidebar.header("⚙️ 설정")
selected_exchanges = st.sidebar.multiselect(
    "거래소 선택",
    options=ALL_EXCHANGES,
    default=CEX_EXCHANGES[:4]
)
min_volume = st.sidebar.number_input(
    "최소 24h 거래량 (USD)",
    min_value=0,
    value=1_000_000,
    step=100_000
)
auto_refresh = st.sidebar.checkbox("자동 새로고침 (10초)", value=False)

if st.sidebar.button("🔄 데이터 새로고침") or auto_refresh:
    st.session_state.refresh_trigger = datetime.now()

# 탭 구성
tab1, tab2 = st.tabs(["💰 Funding Arbitrage", "🎯 Squeeze Radar"])

# 데이터 수집
with st.spinner("데이터 수집 중..."):
    all_data = run_async(fetch_all_exchanges(selected_exchanges))
    ticker_map = build_ticker_map(all_data)

# ===== 탭1: Funding Arbitrage =====
with tab1:
    st.subheader("Funding Arbitrage 리더보드")
    st.caption("펀딩차 - 비용 = Net Edge 기준 정렬 | 높은 쪽 SHORT, 낮은 쪽 LONG")
    
    if len(selected_exchanges) < 2:
        st.warning("2개 이상 거래소를 선택하세요.")
    else:
        opportunities = st.session_state.arb_engine.find_opportunities(
            ticker_map, min_volume=min_volume
        )
        
        if opportunities:
            rows = []
            for opp in opportunities[:50]:
                rows.append({
                    "Symbol": opp.symbol,
                    "Ex A (SHORT)": opp.exchange_a.upper(),
                    "Price A": f"${opp.price_a:,.2f}",
                    "Funding A": f"{opp.funding_a:.4f}%",
                    "Ex B (LONG)": opp.exchange_b.upper(),
                    "Price B": f"${opp.price_b:,.2f}",
                    "Funding B": f"{opp.funding_b:.4f}%",
                    "Gap %": f"{opp.gap_pct:.4f}%",
                    "Net Edge": f"{opp.net_edge:.4f}%",
                    "Best Leg": opp.best_leg,
                    "Warning": opp.warning or "✅",
                })
            
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.metric("총 기회", len(opportunities))
        else:
            st.info("현재 조건에 맞는 아비트라지 기회가 없습니다.")

# ===== 탭2: Squeeze Radar =====
with tab2:
    st.subheader("Squeeze Radar")
    st.caption("점수 0~100 | 높을수록 스퀴즈 가능성 ↑")
    
    squeeze_exchange = st.selectbox("거래소 선택", selected_exchanges)
    
    if squeeze_exchange and squeeze_exchange in all_data:
        tickers = all_data[squeeze_exchange]
        
        signals = st.session_state.squeeze_engine.analyze_all(
            tickers, st.session_state.prev_fundings
        )
        
        # 펀딩 히스토리 업데이트
        for t in tickers:
            key = f"{t.exchange}:{t.symbol}"
            if t.funding_rate is not None:
                st.session_state.prev_fundings[key] = t.funding_rate
        
        if signals:
            rows = []
            for sig in signals[:50]:
                rows.append({
                    "Symbol": sig.symbol,
                    "Score": f"{sig.squeeze_score:.0f}",
                    "Direction": sig.direction_bias,
                    "OI Δ%": f"{sig.oi_delta_pct:.2f}%" if sig.oi_delta_pct else "-",
                    "Price Δ%": f"{sig.price_delta_pct:.2f}%" if sig.price_delta_pct else "-",
                    "Funding": f"{sig.funding_level:.4f}%" if sig.funding_level else "-",
                    "Funding Δ": f"{sig.funding_delta:.4f}%" if sig.funding_delta else "-",
                    "Spread": f"{sig.spread_stress:.1f}bps" if sig.spread_stress else "-",
                    "Notes": sig.notes,
                })
            
            df = pd.DataFrame(rows)
            
            def highlight_score(val):
                try:
                    score = float(val)
                    if score >= 70:
                        return "background-color: #ff4444; color: white"
                    elif score >= 50:
                        return "background-color: #ffaa00"
                    elif score >= 30:
                        return "background-color: #ffff44"
                    return ""
                except:
                    return ""
            
            styled_df = df.style.applymap(highlight_score, subset=["Score"])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.info("데이터 수집 중...")
    else:
        st.warning("거래소를 선택하세요.")

# 푸터
st.sidebar.markdown("---")
st.sidebar.caption(f"마지막 업데이트: {datetime.now().strftime('%H:%M:%S')}")

if auto_refresh:
    import time
    time.sleep(10)
    st.rerun()