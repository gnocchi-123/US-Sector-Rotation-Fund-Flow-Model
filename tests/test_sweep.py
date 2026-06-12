# 윈도우 스윕(backtest/sweep.py) 단위테스트 — 합성 데이터, 네트워크 없음.

import pandas as pd

from srm.backtest.sweep import sweep_windows


def test_sweep_windows_deterministic_one_row_per_candidate(price_panel: pd.DataFrame):
    candidates = [8, 10, 14]
    out1 = sweep_windows(price_panel, "BENCH", ["STRONG", "WEAK"], candidates, horizon=4)
    out2 = sweep_windows(price_panel, "BENCH", ["STRONG", "WEAK"], candidates, horizon=4)

    pd.testing.assert_frame_equal(out1, out2)
    assert list(out1.columns) == ["window", "transitions", "whipsaws", "rate"]
    assert list(out1["window"]) == candidates  # 현행(14) 포함, 후보 수만큼 행
    # 합성 랜덤워크에서는 분면 전환이 발생한다(전환 0이면 스윕 비교가 무의미).
    assert (out1["transitions"] > 0).all()


def test_sweep_windows_degrades_when_benchmark_missing(price_panel: pd.DataFrame):
    out = sweep_windows(price_panel, "NO_BENCH", ["STRONG"], [8, 14], horizon=4)
    assert len(out) == 2
    assert (out["transitions"] == 0).all()
    assert out["rate"].isna().all()
