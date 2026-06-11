# signals/cycle.py 테스트 — 합성 데이터, 네트워크 없음.
# M1 RRG 교훈: 칼날 경계(z~0, 변화~0) 단언 금지 — drift가 큰 명확한 케이스만 단언한다.

import pandas as pd
import pytest

from srm.signals.cycle import (
    UNKNOWN_PHASE,
    classify_cycle_phase,
    compute_cycle_position,
    indicator_state,
)

META = {
    "MONTHLY_A": {"name": "Indicator A", "higher_is": "expansion"},
    "MONTHLY_B": {"name": "Indicator B", "higher_is": "expansion"},
    "DAILY": {"name": "Daily Indicator", "higher_is": "expansion"},
}


@pytest.mark.parametrize(
    ("level_sign", "direction_sign", "expected"),
    [
        (-1, 1, "Recovery"),
        (1, 1, "Expansion"),
        (1, -1, "Slowdown"),
        (-1, -1, "Contraction"),
    ],
)
def test_classify_cycle_phase_all_quadrants(level_sign, direction_sign, expected):
    assert classify_cycle_phase(level_sign, direction_sign) == expected


def test_indicator_state_direction_up(expansion_panel):
    state = indicator_state(expansion_panel["MONTHLY_A"], trend_window=6, level_window=120)
    assert state is not None
    assert state["direction"] == "up"
    assert state["level_z"] > 0


def test_indicator_state_higher_is_contraction_inverts(contraction_panel):
    """하락 중인 시리즈도 higher_is=contraction이면 '확장 방향(up)'으로 읽힌다."""
    plain = indicator_state(contraction_panel["MONTHLY_A"], higher_is="expansion")
    inverted = indicator_state(contraction_panel["MONTHLY_A"], higher_is="contraction")
    assert plain["direction"] == "down" and plain["level_z"] < 0
    assert inverted["direction"] == "up" and inverted["level_z"] > 0


def test_indicator_state_insufficient_data():
    short = pd.Series(
        [1.0, 2.0, 3.0],
        index=pd.date_range("2026-01-31", periods=3, freq="ME"),
    )
    assert indicator_state(short, trend_window=6) is None


def test_compute_cycle_position_expansion(expansion_panel):
    out = compute_cycle_position(expansion_panel, META, level_window=120)
    assert out["phase"] == "Expansion"
    assert out["counted"] == 3
    assert out["direction_score"] > 0
    assert out["level_score"] > 0
    # 일간 시리즈도 월말 리샘플을 거쳐 정상 판정에 포함된다(혼합 주기).
    assert "Daily Indicator" in out["details"]
    assert "데이터 부족" not in out["details"]["Daily Indicator"]


def test_compute_cycle_position_contraction(contraction_panel):
    out = compute_cycle_position(contraction_panel, META, level_window=120)
    assert out["phase"] == "Contraction"
    assert out["direction_score"] < 0
    assert out["level_score"] < 0


def test_compute_cycle_position_empty_degrades():
    out = compute_cycle_position(pd.DataFrame(), META)
    assert out["phase"] == UNKNOWN_PHASE
    assert out["counted"] == 0


def test_compute_cycle_position_below_min_indicators(expansion_panel):
    """유효 지표 1개 < min_indicators=2 -> Unknown degrade."""
    one_col = expansion_panel[["MONTHLY_A"]]
    out = compute_cycle_position(one_col, META, min_indicators=2)
    assert out["phase"] == UNKNOWN_PHASE
    assert out["counted"] == 1


def test_cycle_outputs_state_descriptions_only(expansion_panel, contraction_panel):
    """출력 문자열에 단정적 미래 표현이 없어야 한다(상태 서술만)."""
    forbidden = ["오를 것", "내릴 것", "상승할 것", "하락할 것", "전망", "예상"]
    for panel in (expansion_panel, contraction_panel):
        out = compute_cycle_position(panel, META)
        text = out["description"] + " ".join(out["details"].values())
        for word in forbidden:
            assert word not in text
