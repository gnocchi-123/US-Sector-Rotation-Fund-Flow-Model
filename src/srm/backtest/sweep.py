# RRG 윈도우 스윕 — 후보 윈도우별 신호 안정성(전환 수/휩소율) 비교 (M4).
#
# 순수함수만 둔다. rs_window=mom_window 동일값으로 스윕한다(현행 config도 동일값).
# 휩소율이 낮다 = 신호가 덜 번복된다(안정적)이며, 예측 성과를 뜻하지 않는다.

from __future__ import annotations

import pandas as pd

from srm.backtest.walk import quadrant_history
from srm.backtest.whipsaw import whipsaw_rate


def sweep_windows(
    prices: pd.DataFrame,
    benchmark: str,
    members: list[str],
    candidates: tuple[int, ...] | list[int],
    horizon: int,
) -> pd.DataFrame:
    """후보 윈도우별 분면 전환 수/휩소율 표 — 컬럼 window/transitions/whipsaws/rate.

    각 후보로 quadrant_history를 다시 계산해 whipsaw_rate의 total을 한 행으로
    기록한다. 이력이 비면(데이터 부족) 해당 행은 전환 0/rate None(degrade).
    """
    rows = []
    for window in candidates:
        hist = quadrant_history(prices, benchmark, members, rs_window=window, mom_window=window)
        total = whipsaw_rate(hist, horizon)["total"]
        rows.append({"window": int(window), **total})
    return pd.DataFrame(rows, columns=["window", "transitions", "whipsaws", "rate"])
