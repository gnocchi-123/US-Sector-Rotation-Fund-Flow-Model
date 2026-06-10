# report/export.py 단위테스트 — 합성 데이터, 네트워크/파일은 tmp_path에서.

import json

import pandas as pd

from srm.config import Config
from srm.report.export import build_export_payload, export_csv, export_json


def _sample_config() -> Config:
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


def _sample_flow_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Sector": "Strong Sector",
                "Ticker": "STRONG",
                "Quadrant": "Leading",
                "RS-Ratio": 102.5,
                "RS-Mom": 100.3,
                "Rot": "U",
                "Trend": "Uptrend",
                "FlowScore": 2.5,
            },
            {
                "Sector": "Weak Sector",
                "Ticker": "WEAK",
                "Quadrant": "Lagging",
                "RS-Ratio": 97.1,
                "RS-Mom": 99.8,
                "Rot": "D",
                "Trend": "Downtrend",
                "FlowScore": -3.5,
            },
        ]
    )


def _sample_risk() -> dict:
    return {
        "score": 1,
        "max": 1,
        "regime": "MIXED (혼조 / 전환 가능 구간)",
        "details": {"UpVsDown": "risk-ON"},
    }


def test_build_export_payload_schema():
    cfg = _sample_config()
    flow_table = _sample_flow_table()
    risk = _sample_risk()

    payload = build_export_payload(flow_table, risk, cfg, "1wk", "2026-06-10T00:00:00+00:00")

    assert payload["generated_at"] == "2026-06-10T00:00:00+00:00"
    assert payload["interval"] == "1wk"
    assert payload["benchmark"] == cfg.benchmark
    assert payload["regime"] == risk["regime"]
    assert payload["score"] == risk["score"]
    assert payload["max_score"] == risk["max"]
    assert payload["details"] == risk["details"]
    assert len(payload["ranking"]) == len(flow_table)
    assert payload["ranking"][0]["Ticker"] == "STRONG"
    assert payload["disclaimer"].strip() != ""


def test_export_json_roundtrip(tmp_path):
    cfg = _sample_config()
    flow_table = _sample_flow_table()
    risk = _sample_risk()
    payload = build_export_payload(flow_table, risk, cfg, "1wk", "2026-06-10T00:00:00+00:00")

    path = export_json(payload, tmp_path / "flow_table.json")
    assert path.exists()

    with path.open(encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == payload


def test_export_csv_roundtrip(tmp_path):
    flow_table = _sample_flow_table()

    path = export_csv(flow_table, tmp_path / "flow_table.csv")
    assert path.exists()

    loaded = pd.read_csv(path)
    pd.testing.assert_frame_equal(loaded, flow_table)
