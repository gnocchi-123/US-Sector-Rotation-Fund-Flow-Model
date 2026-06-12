# Layer 1: RRG 엔진 — RS-Ratio / RS-Momentum -> 4분면 ("어디로").
# 순수함수만 둔다. 네트워크/설정 파일 접근은 하지 않는다(윈도우 등은 인자로 받음).
#
# 정의 (00_PROJECT_SPEC.md §3, CLAUDE.md 결정 1):
#   RS          = 100 * (섹터 가격 / 벤치마크 가격)
#   RS-Ratio    = 100 + 롤링 z-score(RS)
#   RS-Momentum = 100 + 롤링 z-score(RS-Ratio의 변화량(diff))
#     -> 스펙 초기 문구는 "변화율"이었으나, RS-Ratio가 이미 100 근처로 정규화돼 있고
#        z-score가 상수배를 제거하므로 변화율(pct_change)과 결과가 사실상 동일하다.
#        분모가 없어 NaN/극단값이 없는 diff를 채택한다.

from __future__ import annotations

import numpy as np
import pandas as pd


def _zscore_normalize(series: pd.Series, window: int) -> pd.Series:
    m = series.rolling(window, min_periods=window // 2).mean()
    s = series.rolling(window, min_periods=window // 2).std()
    return 100.0 + (series - m) / s.replace(0, np.nan)


def classify_quadrant(rs_ratio: float, rs_momentum: float) -> str:
    """RS-Ratio/RS-Momentum의 100 기준 4분면을 분류한다.

    | 분면 | 조건 | 자금 흐름 의미 |
    |---|---|---|
    | Improving | Ratio<100, Mom>=100 | 유입 시작 (이른 신호) |
    | Leading   | Ratio>=100, Mom>=100 | 이미 주도 중 |
    | Weakening | Ratio>=100, Mom<100 | 유출 시작 (이른 경고) |
    | Lagging   | Ratio<100, Mom<100 | 소외 / 빠져나간 상태 |
    """
    if rs_ratio >= 100 and rs_momentum >= 100:
        return "Leading"
    if rs_ratio >= 100 and rs_momentum < 100:
        return "Weakening"
    if rs_ratio < 100 and rs_momentum < 100:
        return "Lagging"
    return "Improving"


def rs_series(
    prices: pd.DataFrame,
    benchmark: str,
    ticker: str,
    rs_window: int = 14,
    mom_window: int = 14,
) -> tuple[pd.Series, pd.Series] | None:
    """한 티커의 RS-Ratio/RS-Momentum 전체 시계열을 계산한다.

    벤치마크나 티커가 `prices`에 없으면 None(예외 대신 안전하게 degrade).
    compute_rrg(최신 스냅샷)와 백테스트의 분면 이력 추적이 공유하는 단일 정의다.
    """
    if benchmark not in prices.columns or ticker not in prices.columns:
        return None
    rs = 100.0 * prices[ticker] / prices[benchmark]
    rs_ratio = _zscore_normalize(rs, rs_window)
    rs_mom = _zscore_normalize(rs_ratio.diff(), mom_window)
    return rs_ratio, rs_mom


def compute_rrg(
    prices: pd.DataFrame,
    benchmark: str,
    members: list[str],
    rs_window: int = 14,
    mom_window: int = 14,
) -> pd.DataFrame:
    """종목별 최신 RS-Ratio/RS-Momentum/4분면을 계산한다.

    `prices`에 없는 티커나, 윈도우가 부족해 NaN인 티커는 결과에서 제외하고,
    벤치마크 자체가 없으면 빈 DataFrame을 반환한다(예외 대신 안전하게 degrade).
    반환 DataFrame은 ticker를 인덱스로 하며 `_ratio_series`/`_mom_series`에
    전체 시계열을 담아 차트 렌더에 재사용한다.
    """
    rows = []
    for tkr in members:
        series = rs_series(prices, benchmark, tkr, rs_window, mom_window)
        if series is None:
            continue
        rs_ratio, rs_mom = series
        lr, lm = rs_ratio.iloc[-1], rs_mom.iloc[-1]
        if np.isnan(lr) or np.isnan(lm):
            continue
        rows.append(
            {
                "ticker": tkr,
                "rs_ratio": round(lr, 2),
                "rs_momentum": round(lm, 2),
                "quadrant": classify_quadrant(lr, lm),
                "mom_delta": (
                    round(rs_mom.iloc[-1] - rs_mom.iloc[-2], 2) if len(rs_mom.dropna()) > 1 else 0.0
                ),
                "_ratio_series": rs_ratio,
                "_mom_series": rs_mom,
            }
        )
    return pd.DataFrame(rows).set_index("ticker") if rows else pd.DataFrame()
