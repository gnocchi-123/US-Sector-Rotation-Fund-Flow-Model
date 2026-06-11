# 가격 스냅샷(data/snapshot.py) 단위테스트 — 네트워크 없음, 파일 I/O는 tmp_path에서.
#
# 재현성 검증: 같은 스냅샷을 두 번 로드해 각각 리포트를 만들면 완전히 동일해야 한다
# (ROADMAP.md M2 완료 기준 "같은 스냅샷 -> 같은 보고서").

import pandas as pd

from srm.config import Config
from srm.data.snapshot import load_snapshot, load_snapshot_frame, save_snapshot
from srm.report.synthesize import compute_flow_table, render_report
from srm.signals.risk import compute_risk_appetite


def test_save_and_load_roundtrip(tmp_path, price_panel: pd.DataFrame):
    meta = {"period": "2y", "interval": "1wk", "tickers": ["BENCH", "STRONG", "WEAK"]}
    snap_dir = save_snapshot(price_panel, meta, tmp_path)

    assert (snap_dir / "prices.parquet").exists()
    assert (snap_dir / "meta.json").exists()

    loaded_prices, loaded_meta = load_snapshot(snap_dir)
    # parquet 라운드트립에서 DatetimeIndex의 freq 메타데이터는 보존되지 않는다(값은 동일).
    pd.testing.assert_frame_equal(loaded_prices, price_panel, check_freq=False)
    assert loaded_meta["period"] == "2y"
    assert loaded_meta["interval"] == "1wk"
    assert "timestamp" in loaded_meta


def test_snapshot_extra_frames_roundtrip(tmp_path, price_panel, expansion_panel):
    """선행지표 패널을 extra_frames로 저장하면 같은 스냅샷에서 복원된다."""
    snap_dir = save_snapshot(
        price_panel,
        {"period": "2y", "interval": "1wk"},
        tmp_path,
        extra_frames={"indicators": expansion_panel},
    )
    loaded = load_snapshot_frame(snap_dir, "indicators")
    pd.testing.assert_frame_equal(loaded, expansion_panel, check_freq=False)
    # extra_frames 없이 저장된 과거 스냅샷은 None(하위호환, 예외 없음).
    old_dir = save_snapshot(price_panel, {}, tmp_path)
    assert load_snapshot_frame(old_dir, "indicators") is None


def _sample_config() -> Config:
    """price_panel fixture의 컬럼에 맞춘 작은 합성 Config."""
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


def test_snapshot_reproducibility(tmp_path, price_panel: pd.DataFrame):
    snap_dir = save_snapshot(price_panel, {"period": "2y", "interval": "1wk"}, tmp_path)
    cfg = _sample_config()

    reports = []
    for _ in range(2):
        prices, _ = load_snapshot(snap_dir)
        flow_table = compute_flow_table(prices, cfg)
        risk = compute_risk_appetite(prices, cfg.risk_pairs, cfg.risk_ma, cfg.risk_on, cfg.risk_off)
        reports.append(render_report(flow_table, risk, prices, cfg, cfg.data_interval))

    assert reports[0] == reports[1]
