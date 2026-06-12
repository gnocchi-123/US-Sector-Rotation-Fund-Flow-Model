# 신호 안정성 리포트(report/backtest_report.py) 렌더 테스트 — 합성 데이터, 네트워크 없음.

import pandas as pd

from srm.backtest.sweep import sweep_windows
from srm.backtest.walk import quadrant_history, trend_history
from srm.backtest.whipsaw import score_sign_stability, whipsaw_rate
from srm.config import Config
from srm.report.backtest_report import render_backtest_report

# 단정적 미래 표현 금지 — 사용자 대면 출력에 있어선 안 되는 표현들.
# ("수익"은 부정 맥락("수익률 백테스트가 아닙니다")으로만 허용 — 별도 검사)
FORBIDDEN_PHRASES = ("오를 것", "상승할 것", "하락할 것", "보장된", "확실")


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
    )


def _render(price_panel: pd.DataFrame, cfg: Config) -> str:
    members = list(cfg.sectors)
    quad_hist = quadrant_history(price_panel, cfg.benchmark, members, cfg.rs_window, cfg.mom_window)
    trend_hists = {
        t: trend_history(price_panel, t, cfg.trend_fast, cfg.trend_slow) for t in members
    }
    weights = {"quad_flow": cfg.quad_flow, "trend": cfg.trend}
    whipsaw = whipsaw_rate(quad_hist, cfg.backtest_horizon)
    gate_cmp = {
        rule: score_sign_stability(quad_hist, trend_hists, weights, cfg.backtest_horizon, rule)
        for rule in ("none", "contradiction_only")
    }
    sweep = sweep_windows(
        price_panel, cfg.benchmark, members, cfg.backtest_window_candidates, cfg.backtest_horizon
    )
    return render_backtest_report(whipsaw, gate_cmp, sweep, cfg)


def test_backtest_report_has_sections_and_disclaimer(price_panel: pd.DataFrame):
    cfg = _config()
    report = _render(price_panel, cfg)

    assert "수익률 백테스트가 아닙니다" in report
    assert "[1] 섹터별 RRG 분면 휩소율" in report
    assert "[2] 추세 게이트 후보 비교" in report
    assert "[3] RRG 윈도우 후보별 안정성" in report
    # 섹터 표시 이름 + 현행 윈도우 표식 + Improving 비강등 안내
    assert "Strong Sector" in report
    assert "<- 현행" in report
    assert "Improving 분면은 어떤 규칙에서도 강등하지 않습니다" in report
    assert cfg.disclaimer.strip() in report


def test_backtest_report_no_predictive_language(price_panel: pd.DataFrame):
    report = _render(price_panel, _config())
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in report, phrase
    # '수익'은 "수익률 백테스트가 아닙니다"라는 부정 맥락으로만 등장해야 한다.
    assert "수익" not in report.replace("수익률 백테스트가 아닙니다", "")
    assert "후행적" in report


def test_backtest_report_degrades_on_empty_inputs():
    cfg = _config()
    empty_whipsaw = {"per_ticker": {}, "total": {"transitions": 0, "whipsaws": 0, "rate": None}}
    report = render_backtest_report(empty_whipsaw, {}, pd.DataFrame(), cfg)

    assert report.count("데이터 부족으로 측정을 생략합니다.") == 3
    assert cfg.disclaimer.strip() in report


def test_backtest_report_formats_none_rate_as_na():
    cfg = _config()
    whipsaw = {
        "per_ticker": {"STRONG": {"transitions": 0, "whipsaws": 0, "rate": None}},
        "total": {"transitions": 0, "whipsaws": 0, "rate": None},
    }
    report = render_backtest_report(whipsaw, {}, pd.DataFrame(), cfg)
    assert "n/a (전환 없음)" in report
