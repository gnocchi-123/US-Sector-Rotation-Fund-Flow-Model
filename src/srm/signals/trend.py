# Layer 3: 추세 필터 층 — 가격 vs 50/200MA 1차 추세 (안전장치).
# 순수함수만 둔다. fast/slow 윈도우는 config.yaml의 windows에서 인자로 받는다.

from __future__ import annotations

import numpy as np
import pandas as pd


def trend_state(prices: pd.DataFrame, ticker: str, fast: int = 50, slow: int = 200) -> str:
    """가격이 fast/slow 이동평균 위/아래로 정렬됐는지로 1차 추세를 판정한다.

    last > fast-MA > slow-MA -> "Uptrend"
    last < fast-MA < slow-MA -> "Downtrend"
    그 외 -> "Neutral"
    티커가 없거나 데이터가 부족하면 "n/a" (예외로 죽지 않고 안전하게 degrade).
    시계열이 slow보다 짧으면 fast/slow를 시계열 길이에 맞춰 축소한다.
    """
    if ticker not in prices.columns:
        return "n/a"
    px = prices[ticker].dropna()
    if len(px) < slow:
        slow = max(20, len(px) // 2)
        fast = min(fast, slow // 2)
    mf = px.rolling(fast).mean().iloc[-1]
    ms = px.rolling(slow).mean().iloc[-1]
    last = px.iloc[-1]
    if np.isnan(mf) or np.isnan(ms):
        return "n/a"
    if last > mf > ms:
        return "Uptrend"
    if last < mf < ms:
        return "Downtrend"
    return "Neutral"
