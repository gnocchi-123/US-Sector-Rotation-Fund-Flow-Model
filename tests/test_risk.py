# Layer 2 (위험선호) 단위테스트 — 합성 데이터, 네트워크 없음.

import numpy as np
import pandas as pd

from srm.signals.risk import compute_risk_appetite, ratio_score


def test_ratio_score_up_down_mixed():
    idx_15 = pd.date_range("2024-01-01", periods=15, freq="D")
    idx_10 = pd.date_range("2024-01-01", periods=10, freq="D")

    up = pd.DataFrame({"A": np.linspace(1.0, 1.5, 15), "B": np.ones(15)}, index=idx_15)
    down = pd.DataFrame({"A": np.linspace(1.5, 1.0, 15), "B": np.ones(15)}, index=idx_15)
    mixed = pd.DataFrame(
        {"A": [1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 1.0], "B": np.ones(10)},
        index=idx_10,
    )

    assert ratio_score(up, "A", "B", ma=5) == 1
    assert ratio_score(down, "A", "B", ma=5) == -1
    assert ratio_score(mixed, "A", "B", ma=5) == 0


def test_ratio_score_missing_or_insufficient_data():
    idx_15 = pd.date_range("2024-01-01", periods=15, freq="D")
    idx_9 = pd.date_range("2024-01-01", periods=9, freq="D")

    missing = pd.DataFrame({"A": np.ones(15)}, index=idx_15)
    short = pd.DataFrame({"A": np.ones(9), "B": np.ones(9)}, index=idx_9)

    assert ratio_score(missing, "A", "B", ma=5) is None
    assert ratio_score(short, "A", "B", ma=5) is None


def test_compute_risk_appetite_thresholds(price_panel: pd.DataFrame):
    risk_on_pairs = {"a": ("UP1", "BENCH"), "b": ("UP2", "BENCH")}
    risk_off_pairs = {"a": ("DOWN1", "BENCH"), "b": ("DOWN2", "BENCH")}
    mixed_pairs = {"a": ("UP1", "BENCH"), "b": ("DOWN1", "BENCH")}
    unknown_pairs = {"a": ("FOO", "BAR")}

    on = compute_risk_appetite(price_panel, risk_on_pairs, risk_on=2, risk_off=-2)
    assert on["score"] == 2
    assert "RISK-ON" in on["regime"]

    off = compute_risk_appetite(price_panel, risk_off_pairs, risk_on=2, risk_off=-2)
    assert off["score"] == -2
    assert "RISK-OFF" in off["regime"]

    mixed = compute_risk_appetite(price_panel, mixed_pairs, risk_on=2, risk_off=-2)
    assert mixed["score"] == 0
    assert "MIXED" in mixed["regime"]

    unknown = compute_risk_appetite(price_panel, unknown_pairs, risk_on=2, risk_off=-2)
    assert unknown["max"] == 0
    assert "Unknown" in unknown["regime"]


def test_compute_risk_appetite_threshold_is_parameterized(price_panel: pd.DataFrame):
    # UP1만 있을 때 합산 점수는 +1 -> 기본 임계값(risk_on=2)으로는 RISK-ON이 아니지만
    # risk_on=1로 낮추면 동일 데이터에서 RISK-ON으로 바뀐다(임계값이 인자로 동작함을 확인).
    pairs = {"a": ("UP1", "BENCH")}

    default = compute_risk_appetite(price_panel, pairs, risk_on=2, risk_off=-2)
    assert default["score"] == 1
    assert "RISK-ON" not in default["regime"]

    lowered = compute_risk_appetite(price_panel, pairs, risk_on=1, risk_off=-2)
    assert "RISK-ON" in lowered["regime"]
