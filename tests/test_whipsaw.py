# 휩소 측정/게이트 후보 규칙(backtest/whipsaw.py) 단위테스트 — 합성 라벨, 네트워크 없음.

import pandas as pd
import pytest

from srm.backtest.whipsaw import apply_gate, score_sign_stability, whipsaw_rate


def _label_frame(**columns: list) -> pd.DataFrame:
    n = len(next(iter(columns.values())))
    idx = pd.date_range("2024-01-01", periods=n, freq="W")
    return pd.DataFrame({k: pd.array(v, dtype="object") for k, v in columns.items()}, index=idx)


def test_whipsaw_rate_counts_reversals():
    # A->B 전환은 1봉 만에 A로 복귀(휩소), B->A 전환은 복귀 없음.
    hist = _label_frame(X=["A", "A", "B", "A", "A", "A"])
    out = whipsaw_rate(hist, horizon=4)
    assert out["per_ticker"]["X"] == {"transitions": 2, "whipsaws": 1, "rate": 0.5}
    assert out["total"] == {"transitions": 2, "whipsaws": 1, "rate": 0.5}


def test_whipsaw_rate_horizon_limits_lookahead():
    # A->B 후 5봉 뒤에야 A 복귀: horizon=4면 휩소가 아니고, horizon=5면 휩소다.
    hist = _label_frame(X=["A", "B", "B", "B", "B", "B", "A"])
    assert whipsaw_rate(hist, horizon=4)["per_ticker"]["X"]["whipsaws"] == 0
    assert whipsaw_rate(hist, horizon=5)["per_ticker"]["X"]["whipsaws"] == 1


def test_whipsaw_rate_no_transitions_gives_none():
    hist = _label_frame(X=["A", "A", "A"])
    out = whipsaw_rate(hist, horizon=4)
    assert out["per_ticker"]["X"]["rate"] is None
    assert out["total"]["rate"] is None
    # 빈 이력도 예외 없이 degrade
    assert whipsaw_rate(pd.DataFrame(), horizon=4)["total"]["rate"] is None


def test_whipsaw_rate_skips_missing_labels():
    # 결측을 사이에 둔 같은 라벨은 전환이 아니다 (walk.transitions와 동일 규칙).
    hist = _label_frame(X=["A", pd.NA, "A", "B", pd.NA, "A"])
    out = whipsaw_rate(hist, horizon=4)
    assert out["per_ticker"]["X"]["transitions"] == 2  # A->B, B->A
    assert out["per_ticker"]["X"]["whipsaws"] == 1  # A->B가 2(유효)봉 내 복귀


def test_apply_gate_none_returns_score_unchanged():
    assert apply_gate("Leading", "Downtrend", 1.5, rule="none") == 1.5
    assert apply_gate("Lagging", "Uptrend", -1.5, rule="none") == -1.5


def test_apply_gate_contradiction_only_demotes_contradictions_to_zero():
    assert apply_gate("Leading", "Downtrend", 1.5, rule="contradiction_only") == 0.0
    assert apply_gate("Weakening", "Uptrend", -0.5, rule="contradiction_only") == 0.0
    assert apply_gate("Lagging", "Uptrend", -1.5, rule="contradiction_only") == 0.0
    # 모순이 아닌 조합은 그대로
    assert apply_gate("Leading", "Uptrend", 2.0, rule="contradiction_only") == 2.0
    assert apply_gate("Lagging", "Downtrend", -3.0, rule="contradiction_only") == -3.0


def test_apply_gate_never_demotes_improving():
    # 결정 3 제약: Improving은 추세가 Downtrend여도(이른 신호라 정상) 강등하지 않는다.
    assert apply_gate("Improving", "Downtrend", 1.5, rule="contradiction_only") == 1.5
    assert apply_gate("Improving", "Uptrend", 2.5, rule="contradiction_only") == 2.5


def test_apply_gate_rejects_unknown_rule():
    with pytest.raises(ValueError):
        apply_gate("Leading", "Uptrend", 1.0, rule="typo")


def test_score_sign_stability_differs_by_rule():
    # Leading 고정 + 추세가 Uptrend/Downtrend로 교대.
    #   none               -> 점수 1.5 / 0.5: 항상 양수(부호 전환 0건).
    #   contradiction_only -> Leading+Downtrend가 0으로 강등돼 pos/zero가 교대(전환 발생).
    n = 8
    idx = pd.date_range("2024-01-01", periods=n, freq="W")
    quad = pd.DataFrame({"X": pd.array(["Leading"] * n, dtype="object")}, index=idx)
    trend = {
        "X": pd.Series(pd.array(["Uptrend", "Downtrend"] * (n // 2), dtype="object"), index=idx)
    }
    weights = {"quad_flow": {"Leading": 1.0}, "trend": {"Uptrend": 0.5, "Downtrend": -0.5}}

    plain = score_sign_stability(quad, trend, weights, horizon=4, rule="none")
    gated = score_sign_stability(quad, trend, weights, horizon=4, rule="contradiction_only")

    assert plain["total"]["transitions"] == 0
    assert plain["total"]["rate"] is None
    assert gated["total"]["transitions"] > 0
    assert gated["total"]["rate"] is not None


def test_score_sign_stability_skips_ticker_without_trend():
    idx = pd.date_range("2024-01-01", periods=4, freq="W")
    quad = pd.DataFrame({"X": pd.array(["Leading"] * 4, dtype="object")}, index=idx)
    out = score_sign_stability(
        quad, {}, {"quad_flow": {"Leading": 1.0}, "trend": {}}, horizon=4, rule="none"
    )
    assert out["per_ticker"] == {}
    assert out["total"]["rate"] is None
