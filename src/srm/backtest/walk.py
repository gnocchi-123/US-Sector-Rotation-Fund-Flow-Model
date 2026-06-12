# 신호 이력 추적 — RRG 분면/추세 판정을 '시점별'로 재구성한다 (M4).
#
# 순수함수만 둔다. 네트워크/Config 객체 의존 없음(윈도우 등은 인자로 받음).
# 수익률 백테스트가 아니다: 신호 상태의 시계열만 만들고, 평가(휩소율)는
# backtest/whipsaw.py가 맡는다. 흐름/순환 데이터는 후행적일 수 있다.

from __future__ import annotations

import pandas as pd

from srm.signals.rrg import classify_quadrant, rs_series


def quadrant_history(
    prices: pd.DataFrame,
    benchmark: str,
    members: list[str],
    rs_window: int = 14,
    mom_window: int = 14,
) -> pd.DataFrame:
    """티커별 RRG 4분면 라벨의 시계열 (인덱스=시간, 컬럼=티커).

    compute_rrg와 같은 정의(rs_series + classify_quadrant)를 시점별로 적용한다.
    윈도우가 차기 전(NaN) 구간은 결측으로 두고, 유효 시점이 하나도 없는 티커는
    컬럼에서 제외한다. 벤치마크가 없으면 빈 DataFrame(예외 없이 degrade).
    """
    cols: dict[str, pd.Series] = {}
    for tkr in members:
        series = rs_series(prices, benchmark, tkr, rs_window, mom_window)
        if series is None:
            continue
        rs_ratio, rs_mom = series
        valid = rs_ratio.notna() & rs_mom.notna()
        if not valid.any():
            continue
        labels = pd.Series(pd.NA, index=prices.index, dtype="object")
        labels[valid] = [classify_quadrant(r, m) for r, m in zip(rs_ratio[valid], rs_mom[valid])]
        cols[tkr] = labels
    return pd.DataFrame(cols) if cols else pd.DataFrame()


def trend_history(prices: pd.DataFrame, ticker: str, fast: int = 50, slow: int = 200) -> pd.Series:
    """trend_state와 같은 규칙(가격 vs fast/slow MA 정렬)의 시점별 판정 시계열.

    윈도우가 차기 전 구간은 결측. 티커가 없으면 빈 Series(예외 없이 degrade).
    시계열이 slow보다 짧으면 trend_state와 동일하게 윈도우를 축소한다.
    """
    if ticker not in prices.columns:
        return pd.Series(dtype="object")
    px = prices[ticker].dropna()
    if len(px) < slow:
        slow = max(20, len(px) // 2)
        fast = min(fast, slow // 2)
    mf = px.rolling(fast).mean()
    ms = px.rolling(slow).mean()
    valid = mf.notna() & ms.notna()
    out = pd.Series(pd.NA, index=px.index, dtype="object")
    out[valid] = "Neutral"
    out[valid & (px > mf) & (mf > ms)] = "Uptrend"
    out[valid & (px < mf) & (mf < ms)] = "Downtrend"
    return out


def transitions(labels: pd.Series) -> pd.DataFrame:
    """라벨 시계열의 상태 전환 기록 — 컬럼 (time, from, to).

    결측 시점은 건너뛴다(결측 전후 라벨이 같으면 전환이 아님). 전환이 없으면
    빈 DataFrame(컬럼은 유지).
    """
    s = labels.dropna()
    rows = []
    prev = None
    for t, lab in s.items():
        if prev is not None and lab != prev:
            rows.append({"time": t, "from": prev, "to": lab})
        prev = lab
    return pd.DataFrame(rows, columns=["time", "from", "to"])
