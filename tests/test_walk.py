# 신호 이력 추적(backtest/walk.py) 단위테스트 — 합성 데이터, 네트워크 없음.
#
# M1 교훈: 합성 데이터에서 모멘텀 '분면' 자체는 단언하지 않는다. 여기서는
# compute_rrg/trend_state와의 '마지막 시점 일치'와 결정론성·degrade만 단언한다.

import pandas as pd

from srm.backtest.walk import quadrant_history, transitions, trend_history
from srm.signals.rrg import compute_rrg
from srm.signals.trend import trend_state


def test_quadrant_history_deterministic_and_consistent_with_compute_rrg(
    price_panel: pd.DataFrame,
):
    members = ["STRONG", "WEAK", "NOPE"]
    hist1 = quadrant_history(price_panel, "BENCH", members)
    hist2 = quadrant_history(price_panel, "BENCH", members)

    # 결정론성: 같은 입력 -> 같은 출력
    pd.testing.assert_frame_equal(hist1, hist2)

    # 존재하지 않는 티커는 컬럼에서 제외
    assert set(hist1.columns) == {"STRONG", "WEAK"}

    # 마지막 시점 라벨은 compute_rrg의 분면과 일치(단일 정의 공유)
    rrg = compute_rrg(price_panel, "BENCH", ["STRONG", "WEAK"])
    for tkr in ["STRONG", "WEAK"]:
        assert hist1[tkr].dropna().iloc[-1] == rrg.loc[tkr, "quadrant"]

    # 윈도우가 차기 전 구간은 결측, 이후 구간은 4분면 라벨만 존재
    valid_labels = {"Improving", "Leading", "Weakening", "Lagging"}
    assert set(hist1["STRONG"].dropna().unique()) <= valid_labels
    assert hist1["STRONG"].isna().any()


def test_quadrant_history_degrades_to_empty(price_panel: pd.DataFrame):
    assert quadrant_history(price_panel, "NO_BENCH", ["STRONG"]).empty
    assert quadrant_history(price_panel, "BENCH", ["NOPE1", "NOPE2"]).empty


def test_trend_history_last_matches_trend_state(price_panel: pd.DataFrame):
    for tkr, expected in [
        ("TREND_UP", "Uptrend"),
        ("TREND_DOWN", "Downtrend"),
        ("TREND_PULLBACK", "Neutral"),
    ]:
        hist = trend_history(price_panel, tkr)
        assert trend_state(price_panel, tkr) == expected
        assert hist.dropna().iloc[-1] == expected

    # 티커 없음 -> 빈 Series (예외 없이 degrade)
    assert trend_history(price_panel, "NOPE").empty


def test_transitions_records_changes_and_skips_missing():
    idx = pd.date_range("2024-01-01", periods=7, freq="W")
    labels = pd.Series(
        ["Lagging", "Lagging", "Improving", "Improving", pd.NA, "Improving", "Leading"],
        index=idx,
        dtype="object",
    )
    tr = transitions(labels)
    # 결측을 사이에 둔 같은 라벨(Improving)은 전환이 아니다.
    assert list(tr["from"]) == ["Lagging", "Improving"]
    assert list(tr["to"]) == ["Improving", "Leading"]
    assert list(tr["time"]) == [idx[2], idx[6]]


def test_transitions_empty_when_no_changes():
    idx = pd.date_range("2024-01-01", periods=3, freq="W")
    flat = pd.Series(["Leading"] * 3, index=idx, dtype="object")
    tr = transitions(flat)
    assert tr.empty
    assert list(tr.columns) == ["time", "from", "to"]
    assert transitions(pd.Series(dtype="object")).empty
