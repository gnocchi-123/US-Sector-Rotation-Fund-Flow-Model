# report/notion_report — Notion-flavored 보고서 렌더 테스트 (합성 데이터, 네트워크 없음).
#
# 노션 블록 문법(<table>/<callout>/<details>)으로 모든 섹션과 면책을 담고, 차트는 raw URL로
# 임베드하며, 단정 표현이 없고, 데이터 결측 시 예외 없이 안내문으로 degrade하는지 검증한다.

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from srm.backtest.sweep import sweep_windows
from srm.backtest.walk import quadrant_history, trend_history
from srm.backtest.whipsaw import score_sign_stability, whipsaw_rate
from srm.config import load_config
from srm.report.notion_report import render_notion_report
from srm.report.synthesize import compute_flow_table
from srm.signals.risk import compute_risk_appetite

FORBIDDEN_PHRASES = ("오를 것", "상승할 것", "하락할 것", "보장된", "확실")


@pytest.fixture
def cfg():
    base = load_config()
    return dataclasses.replace(
        base,
        benchmark="BENCH",
        sectors={"STRONG": "Strong Sector", "WEAK": "Weak Sector"},
        sector_desc={"STRONG": "강세섹터 — 합성 테스트용"},
        risk_pairs={"UpVsDown": ("UP1", "DOWN1")},
        macro={"DOWN2": "Macro Proxy"},
        report_chart_raw_base="https://raw.example.com/repo/main/reports",
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
    return {
        "phase": "Expansion",
        "description": "선행지표가 역사 대비 높은 수준에서 개선 중인 상태",
        "counted": 3,
        "level_score": 0.80,
        "direction_score": 2,
        "details": {"Indicator A": "up / 수준 z=+0.80"},
    }


def test_notion_report_has_sections_callout_table_and_disclaimer(
    flow_table, risk, price_panel, cfg, cycle, backtest
):
    md = render_notion_report(
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
    assert '<table header-row="true">' in md  # 노션 표 문법
    assert "<callout" in md  # 콜아웃
    assert "<details>" in md  # 용어 토글
    assert cfg.disclaimer.strip() in md


def test_notion_report_embeds_chart_via_raw_url(flow_table, risk, price_panel, cfg):
    md = render_notion_report(flow_table, risk, price_panel, cfg, "1wk", chart_name="rrg.png")
    assert "![Relative Rotation Graph](https://raw.example.com/repo/main/reports/rrg.png)" in md


def test_notion_report_degrades_chart_without_base(flow_table, risk, price_panel, cfg):
    bare = dataclasses.replace(cfg, report_chart_raw_base="")
    md = render_notion_report(flow_table, risk, price_panel, bare, "1wk", chart_name="rrg.png")
    assert "임베드할 수 없어" in md
    assert "raw.example.com" not in md


def test_notion_report_no_predictive_language(flow_table, risk, price_panel, cfg, cycle, backtest):
    md = render_notion_report(
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


def test_notion_report_degrades_missing_cycle_backtest_chart(flow_table, risk, price_panel, cfg):
    md = render_notion_report(
        flow_table, risk, price_panel, cfg, "1wk", cycle=None, backtest=None, chart_name=None
    )
    assert "사이클 분석을 생략합니다" in md
    assert "신호 안정성 측정을 생략합니다" in md
    assert "이미지를 임베드할 수 없어" in md
    assert cfg.disclaimer.strip() in md


def test_notion_report_empty_flow_table_safe_degrade(risk, price_panel, cfg):
    md = render_notion_report(pd.DataFrame(), risk, price_panel, cfg, "1wk")
    assert "데이터가 부족" in md
    assert cfg.disclaimer.strip() in md


def test_notion_report_empty_prices_safe_degrade(risk, cfg):
    md = render_notion_report(pd.DataFrame(), risk, pd.DataFrame(), cfg, "1wk")
    assert "가격 데이터를 불러오지 못해" in md
    assert cfg.disclaimer.strip() in md
