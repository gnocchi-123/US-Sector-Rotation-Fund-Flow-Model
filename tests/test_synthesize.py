# report/synthesize — 종합 점수(결정 2)와 랭킹표의 단위테스트 (네트워크 없음).
#
# 가중치 수치를 테스트에 하드코딩하지 않고 config.yaml(단일 기준)에서 읽어
# 기대값을 재계산한다. 단, "Improving > Leading"(이른 신호 우대)은 결정 2의
# 의도된 편향이므로 부등식으로 직접 단언해 가중치 변경 시 깨지도록 한다.
#
# M1 RRG 교훈에 따라 합성 데이터에서 모멘텀 '분면'은 단언하지 않는다 —
# 랭킹표는 RS-Ratio 좌우 반면과 점수 합산의 자기일관성만 검증한다.

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from srm.config import load_config
from srm.report.synthesize import compute_flow_score, compute_flow_table

# Rot 컬럼 표기 -> rotation 가중치 키
_ROT_KEY = {"U": "up", "D": "down", "-": "flat"}


@pytest.fixture(scope="module")
def cfg():
    """레포 기본 config.yaml — 가중치의 단일 기준."""
    return load_config()


@pytest.fixture
def panel_cfg(cfg):
    """합성 price_panel의 티커에 맞춘 Config (가중치/윈도우는 기본값 유지)."""
    return dataclasses.replace(
        cfg,
        benchmark="BENCH",
        sectors={"STRONG": "Strong Sector", "WEAK": "Weak Sector"},
    )


@pytest.mark.parametrize("quadrant", ["Improving", "Leading", "Weakening", "Lagging"])
@pytest.mark.parametrize(("mom_delta", "rot_key"), [(1.0, "up"), (-1.0, "down"), (0.0, "flat")])
@pytest.mark.parametrize("trend", ["Uptrend", "Neutral", "Downtrend", "n/a"])
def test_flow_score_is_weighted_sum(cfg, quadrant, mom_delta, rot_key, trend):
    """결정 2: 점수 = quad_flow + rotation 부호 + trend 의 단순 합산."""
    expected = cfg.quad_flow[quadrant] + cfg.rotation[rot_key] + cfg.trend.get(trend, 0.0)
    assert compute_flow_score(quadrant, mom_delta, trend, cfg) == expected


def test_flow_score_improving_bias_over_leading(cfg):
    """결정 2의 의도된 편향: 같은 조건이면 Improving(유입 시작) > Leading(주도 중)."""
    for trend in ["Uptrend", "Neutral", "Downtrend"]:
        improving = compute_flow_score("Improving", 0.0, trend, cfg)
        leading = compute_flow_score("Leading", 0.0, trend, cfg)
        assert improving > leading


def test_flow_score_rotation_ordering(cfg):
    """회전(RS-Mom 변화) 방향: up > flat > down."""
    up = compute_flow_score("Leading", 1.0, "Neutral", cfg)
    flat = compute_flow_score("Leading", 0.0, "Neutral", cfg)
    down = compute_flow_score("Leading", -1.0, "Neutral", cfg)
    assert up > flat > down


def test_flow_score_trend_gate_toggle_is_identical_in_m1(cfg):
    """결정 3: trend_gate는 토글만 존재하고 M1~M3에서는 ON/OFF 점수가 동일하다.

    M4에서 강등 규칙이 들어가면 이 테스트를 의도적으로 갱신해야 한다
    (그때도 Improving 분면은 강등하지 않아야 함).
    """
    gated = dataclasses.replace(cfg, trend_gate=True)
    for quadrant in ["Improving", "Leading", "Weakening", "Lagging"]:
        for mom_delta in (1.0, -1.0, 0.0):
            for trend in ["Uptrend", "Neutral", "Downtrend", "n/a"]:
                assert compute_flow_score(quadrant, mom_delta, trend, cfg) == (
                    compute_flow_score(quadrant, mom_delta, trend, gated)
                )


def test_flow_table_ranking_and_consistency(price_panel, panel_cfg):
    """랭킹표: 스키마/정렬/RS-Ratio 반면 + FlowScore가 표의 자체 컬럼과 자기일관."""
    table = compute_flow_table(price_panel, panel_cfg)

    assert list(table["Ticker"]) != []
    assert set(table["Ticker"]) == {"STRONG", "WEAK"}
    assert list(table.columns) == [
        "Sector",
        "Ticker",
        "Quadrant",
        "RS-Ratio",
        "RS-Mom",
        "Rot",
        "Trend",
        "FlowScore",
    ]

    # FlowScore 내림차순 정렬
    scores = list(table["FlowScore"])
    assert scores == sorted(scores, reverse=True)

    # RS-Ratio 좌우 반면(부호)만 단언 — 모멘텀 분면은 단언하지 않는다(M1 교훈).
    by_ticker = table.set_index("Ticker")
    assert by_ticker.loc["STRONG", "RS-Ratio"] >= 100
    assert by_ticker.loc["WEAK", "RS-Ratio"] < 100

    # 표의 Quadrant/Rot/Trend 컬럼으로 점수를 재계산하면 FlowScore와 일치해야 한다.
    for row in table.itertuples():
        expected = round(
            panel_cfg.quad_flow[row.Quadrant]
            + panel_cfg.rotation[_ROT_KEY[row.Rot]]
            + panel_cfg.trend.get(row.Trend, 0.0),
            2,
        )
        assert row.FlowScore == expected


def test_flow_table_degrades_to_empty_when_benchmark_missing(short_price_panel, panel_cfg):
    """벤치마크 티커 자체가 없어도 예외 없이 빈 DataFrame으로 degrade한다."""
    assert "BENCH" not in short_price_panel.columns
    table = compute_flow_table(short_price_panel, panel_cfg)
    assert table.empty


def test_flow_table_degrades_to_empty_on_short_data(panel_cfg):
    """벤치마크는 있지만 윈도우보다 짧은 데이터면 빈 DataFrame으로 degrade한다."""
    idx = pd.date_range("2024-01-01", periods=5, freq="W-MON")
    short = pd.DataFrame(
        {"BENCH": range(100, 105), "STRONG": range(50, 55), "WEAK": range(80, 85)},
        index=idx,
        dtype=float,
    )
    table = compute_flow_table(short, panel_cfg)
    assert table.empty
