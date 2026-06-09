# config 로더 테스트 — 네트워크 없이 통과해야 한다.

import pytest
import yaml

from srm.config import Config, ConfigError, load_config


def test_load_config_success():
    cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.benchmark == "SPY"
    assert "XLK" in cfg.sectors
    assert cfg.trend_gate is False
    assert cfg.disclaimer.strip() != ""


def test_load_config_missing_file(tmp_path):
    missing = tmp_path / "no_such_config.yaml"
    with pytest.raises(ConfigError):
        load_config(missing)


def test_load_config_missing_required_key(tmp_path):
    raw = {
        "tickers": {
            "benchmark": "SPY",
            "sectors": {"XLK": "Technology"},
            "risk_pairs": {"SmallVsLarge": ["IWM", "SPY"]},
            "macro": {"^VIX": "VIX"},
        },
        "windows": {
            "rs_window": 14,
            "mom_window": 14,
            "risk_ma": 20,
            "trend_fast": 50,
            "trend_slow": 200,
        },
        # weights 섹션 자체를 누락시킨다.
        "thresholds": {"risk_on": 2, "risk_off": -2},
        "disclaimer": "면책 문구",
    }
    bad_path = tmp_path / "bad_config.yaml"
    bad_path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(bad_path)
