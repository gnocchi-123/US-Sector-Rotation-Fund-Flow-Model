# report/markdown_report — Markdown 종합 보고서 렌더 테스트 (합성 데이터, 네트워크 없음).
#
# 보고서가 모든 섹션과 면책을 담고, 단정적 미래 표현이 없으며, 데이터가 빠진
# 경우(사이클/백테스트/차트/빈 랭킹표)에 예외 없이 안내문으로 degrade하는지 검증한다.

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from srm.backtest.sweep import sweep_windows
from srm.backtest.walk import quadrant_history, trend_history
from srm.backtest.whipsaw import score_sign_stability, whipsaw_rate
from srm.config import load_config
from srm.report.markdown_report import render_markdown_report
from srm.report.synthesize import compute_flow_table
from srm.signals.risk import compute_risk_appetite

# 단정적 미래 표현 금지 (test_backtest_report.py와 동일 기준).
FORBIDDEN_PHRASES = ("오를 것", "상승할 것", "하락할 것", "보장된", "확실")


@pytest.fixture
def cfg():
    """합성 price_panel 티커에 맞춘 Config (가중치/윈도우는 레포 기본값)."""
    base = load_config()
    return dataclasses.replace(
        base,
        benchmark="BENCH",
        sectors={"STRONG": "Strong Sector", "WEAK": "Weak Sector"},
        risk_pairs={"UpVsDown": ("UP1", "DOWN1")},
        macro={"DOWN2": "Macro Proxy"},
    )


@pytest.fixture
def flow_table(price_panel, cfg):
    return compute_flow_table(price_panel, cfg)


@pytest.fixture
def risk(price_panel, cfg):
    return compute_risk_appetite(
        price_panel, cfg.risk_pairs, cfg.risk_ma, cfg.risk_on, cfg.risk_off, slope=cfg.risk_slope
    )


@pytest.fixture
def backtest(price_panel, cfg):
    """실제 백테스트 헬퍼로 만든 유효한 backtest dict (렌더러 입력 스키마)."""
    members = list(cfg.sectors)
    quad_hist = quadrant_history(price_panel, cfg.benchmark, members, cfg.rs_window, cfg.mom_window)
    trend_hists = {
        t: trend_history(price_panel, t, cfg.trend_fast, cfg.trend_slow) for t in members
    }
    weights = {"quad_flow": cfg.quad_flow, "trend": cfg.trend}
    return {
        "whipsaw": whipsaw_rate(quad_hist, cfg.backtest_horizon),
        "gate_cmp": {
            rule: score_sign_stability(quad_hist, trend_hists, weights, cfg.backtest_horizon, rule)
            for rule in ("none", "contradiction_only")
        },
        "sweep": sweep_windows(
            price_panel,
            cfg.benchmark,
            members,
            cfg.backtest_window_candidates,
            cfg.backtest_horizon,
        ),
    }


@pytest.fixture
def cycle():
    """유효한 사이클 dict (compute_cycle_position 스키마)."""
    return {
        "phase": "Expansion",
        "description": "선행지표가 역사 대비 높은 수준에서 개선 중인 상태",
        "counted": 3,
        "level_score": 0.80,
        "direction_score": 2,
        "details": {"Indicator A": "up / 수준 z=+0.80", "Indicator B": "up / 수준 z=+0.50"},
    }


def test_report_has_all_sections_and_disclaimer(
    flow_table, risk, price_panel, cfg, cycle, backtest
):
    md = render_markdown_report(
        flow_table,
        risk,
        price_panel,
        cfg,
        "1wk",
        cycle=cycle,
        backtest=backtest,
        chart_name="rrg.png",
    )
    for heading in [
        "## 0. 이번 주 결론",
        "### 읽는 법",
        "## 1. 시장 국면",
        "## 2. 섹터 자금흐름 랭킹",
        "## 3. 핵심 요약",
        "## 4. RRG 4분면 차트",
        "## 5. 거시 참고",
        "## 6. 경기 사이클",
        "## 7. 신호 안정성",
    ]:
        assert heading in md, heading
    assert "![Relative Rotation Graph](rrg.png)" in md  # 차트 임베드(상대경로)
    assert "Strong Sector" in md  # 섹터 표시 이름
    assert "FlowScore" in md  # 친화 랭킹표에도 종합 점수 칼럼 유지
    assert "부록: 용어 설명" in md
    assert cfg.disclaimer.strip() in md
    assert "수익률 백테스트가 아닙니다" in md


def test_report_no_predictive_language(flow_table, risk, price_panel, cfg, cycle, backtest):
    md = render_markdown_report(
        flow_table,
        risk,
        price_panel,
        cfg,
        "1wk",
        cycle=cycle,
        backtest=backtest,
        chart_name="rrg.png",
    )
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in md, phrase


def test_ranking_table_is_valid_gfm(flow_table, risk, price_panel, cfg):
    md = render_markdown_report(flow_table, risk, price_panel, cfg, "1wk")
    # GFM 표 구분선 존재 + 헤더 컬럼 모두 포함
    assert "| --- |" in md
    for col in flow_table.columns:
        assert col in md
    # 랭킹 표의 데이터 행 수 = 섹터 수 (각 티커가 한 줄)
    for tkr in cfg.sectors:
        assert tkr in md


def test_degrade_when_cycle_backtest_chart_missing(flow_table, risk, price_panel, cfg):
    md = render_markdown_report(
        flow_table,
        risk,
        price_panel,
        cfg,
        "1wk",
        cycle=None,
        backtest=None,
        chart_name=None,
    )
    # 예외 없이 각 섹션이 안내문으로 대체되고, 면책은 유지된다.
    assert "사이클 분석을 생략합니다" in md
    assert "신호 안정성 측정을 생략합니다" in md
    assert "차트를 생성하지 못해" in md
    assert cfg.disclaimer.strip() in md


def test_empty_flow_table_safe_degrade(risk, price_panel, cfg):
    md = render_markdown_report(pd.DataFrame(), risk, price_panel, cfg, "1wk")
    assert "데이터가 부족" in md
    assert cfg.disclaimer.strip() in md


def test_empty_prices_safe_degrade(risk, cfg):
    """가격 데이터가 비면 prices.index[-1] 접근으로 죽지 않고 안내문 degrade."""
    md = render_markdown_report(pd.DataFrame(), risk, pd.DataFrame(), cfg, "1wk")
    assert "가격 데이터를 불러오지 못해" in md
    assert cfg.disclaimer.strip() in md
