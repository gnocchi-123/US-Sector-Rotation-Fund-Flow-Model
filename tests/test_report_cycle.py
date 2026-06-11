# render_report의 경기 사이클 섹션 테스트 — 합성 데이터, 네트워크 없음.

import pandas as pd

from srm.config import Config
from srm.report.synthesize import CYCLE_LIMITATION, compute_flow_table, render_report
from srm.signals.cycle import compute_cycle_position
from srm.signals.risk import compute_risk_appetite

CYCLE_META = {
    "MONTHLY_A": {"name": "Indicator A", "higher_is": "expansion"},
    "MONTHLY_B": {"name": "Indicator B", "higher_is": "expansion"},
    "DAILY": {"name": "Daily Indicator", "higher_is": "expansion"},
}


def _config() -> Config:
    return Config(
        benchmark="BENCH",
        sectors={"STRONG": "Strong Sector", "WEAK": "Weak Sector"},
        risk_pairs={"UpVsDown": ("UP1", "DOWN1")},
        macro={},
        rs_window=14,
        mom_window=14,
        risk_ma=20,
        trend_fast=50,
        trend_slow=200,
        quad_flow={"Improving": 2, "Leading": 1, "Weakening": -1, "Lagging": -2},
        rotation={"up": 0.5, "down": -0.5, "flat": 0.0},
        trend={"Uptrend": 1, "Neutral": 0, "Downtrend": -1, "n/a": 0},
        trend_gate=False,
        data_period="2y",
        data_interval="1wk",
        risk_on=2,
        risk_off=-2,
        disclaimer="주의: 신호 확인 도구이며 예측이 아님.",
        phase_sectors={"Expansion": ("STRONG",)},
    )


def _render(price_panel, cfg, cycle):
    flow_table = compute_flow_table(price_panel, cfg)
    risk = compute_risk_appetite(
        price_panel, cfg.risk_pairs, cfg.risk_ma, cfg.risk_on, cfg.risk_off
    )
    return render_report(flow_table, risk, price_panel, cfg, "1wk", cycle=cycle)


def test_report_includes_cycle_section(price_panel, expansion_panel):
    cfg = _config()
    cycle = compute_cycle_position(expansion_panel, CYCLE_META)
    report = _render(price_panel, cfg, cycle)

    assert "[5] 경기 사이클 위치" in report
    assert "Expansion (확장)" in report
    assert "Indicator A" in report
    # phase_sectors의 정합 섹터군이 표시 이름(티커)으로 출력된다.
    assert "Strong Sector(STRONG)" in report
    # 발표지연/개정 한계 문구와 면책문구가 함께 있다.
    assert CYCLE_LIMITATION in report
    assert cfg.disclaimer.strip() in report
    # 용어 설명 섹션은 [6]으로 밀린다.
    assert "[6] 용어 설명" in report


def test_report_cycle_none_degrades_to_notice(price_panel):
    cfg = _config()
    report = _render(price_panel, cfg, cycle=None)

    assert "[5] 경기 사이클 위치" in report
    assert "사이클 분석을 생략" in report
    # 기존 섹션들은 그대로 출력된다.
    for section in ("[1] 시장 국면", "[2] 섹터 자금흐름 랭킹", "[6] 용어 설명"):
        assert section in report
    assert cfg.disclaimer.strip() in report


def test_report_cycle_unknown_phase(price_panel):
    """유효 지표 부족 -> Unknown 국면도 예외 없이 렌더되고 정합 섹터군은 생략된다."""
    cfg = _config()
    cycle = compute_cycle_position(pd.DataFrame(), CYCLE_META)
    report = _render(price_panel, cfg, cycle)

    assert "Unknown (데이터 부족)" in report
    assert "정합적이라 알려진 섹터군" not in report
