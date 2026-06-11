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


def _minimal_raw() -> dict:
    """필수 섹션만 있는 최소 config (fred/cycle 옵션 섹션 없음)."""
    return {
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
        "weights": {
            "quad_flow": {"Improving": 2, "Leading": 1, "Weakening": -1, "Lagging": -2},
            "rotation": {"up": 0.5, "down": -0.5, "flat": 0.0},
            "trend": {"Uptrend": 1, "Neutral": 0, "Downtrend": -1, "n/a": 0},
            "trend_gate": False,
        },
        "data": {"period": "2y", "interval": "1wk"},
        "thresholds": {"risk_on": 2, "risk_off": -2},
        "disclaimer": "면책 문구",
    }


def _write(tmp_path, raw) -> str:
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return p


def test_load_config_missing_required_key(tmp_path):
    raw = _minimal_raw()
    del raw["weights"]  # weights 섹션 자체를 누락시킨다.
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_load_config_without_fred_cycle_sections(tmp_path):
    """fred/cycle 옵션 섹션이 없어도(M2 이전 config) 기본값으로 로드된다(하위호환)."""
    cfg = load_config(_write(tmp_path, _minimal_raw()))
    assert cfg.fred_series == {}
    assert cfg.fred_dbnomics == {}
    assert cfg.phase_sectors == {}
    assert cfg.fred_period_years == 10
    assert cfg.cycle_min_indicators == 2


def test_load_config_parses_fred_cycle_sections(tmp_path):
    raw = _minimal_raw()
    raw["fred"] = {
        "series": {
            "T10Y2Y": {"name": "10Y-2Y Term Spread", "higher_is": "expansion"},
            "ICSA": {"name": "Initial Jobless Claims", "higher_is": "contraction"},
        },
        "period_years": 8,
        "stale_months": 3,
        "dbnomics": {
            "ISM_PMI": {"provider_code": "ISM/pmi/pm", "higher_is": "expansion"},
        },
    }
    raw["cycle"] = {
        "trend_window": 4,
        "level_window": 60,
        "min_indicators": 3,
        "phase_sectors": {"Recovery": ["XLY", "XLF"]},
    }
    cfg = load_config(_write(tmp_path, raw))
    assert cfg.fred_series["ICSA"]["higher_is"] == "contraction"
    assert cfg.fred_series["T10Y2Y"]["name"] == "10Y-2Y Term Spread"
    # name 미지정 시 시리즈 ID로 채워진다.
    assert cfg.fred_dbnomics["ISM_PMI"]["name"] == "ISM_PMI"
    assert cfg.fred_dbnomics["ISM_PMI"]["provider_code"] == "ISM/pmi/pm"
    assert cfg.fred_period_years == 8
    assert cfg.fred_stale_months == 3
    assert cfg.cycle_trend_window == 4
    assert cfg.cycle_level_window == 60
    assert cfg.cycle_min_indicators == 3
    assert cfg.phase_sectors["Recovery"] == ("XLY", "XLF")


def test_load_config_rejects_invalid_higher_is(tmp_path):
    raw = _minimal_raw()
    raw["fred"] = {"series": {"T10Y2Y": {"higher_is": "sideways"}}}
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_default_config_has_fred_cycle_sections():
    """레포의 config.yaml에는 M3 섹션이 채워져 있어야 한다."""
    cfg = load_config()
    assert "T10Y2Y" in cfg.fred_series
    assert all(m["higher_is"] in ("expansion", "contraction") for m in cfg.fred_series.values())
    assert set(cfg.phase_sectors) == {"Recovery", "Expansion", "Slowdown", "Contraction"}
