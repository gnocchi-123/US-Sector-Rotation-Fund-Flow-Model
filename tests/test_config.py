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


def test_load_config_optional_lookbacks_default_and_parse(tmp_path):
    """windows.risk_slope/macro_lookback — 없으면 프로토타입 값 5, 있으면 파싱(M4)."""
    cfg = load_config(_write(tmp_path, _minimal_raw()))
    assert cfg.risk_slope == 5
    assert cfg.macro_lookback == 5

    raw = _minimal_raw()
    raw["windows"]["risk_slope"] = 3
    raw["windows"]["macro_lookback"] = 8
    cfg = load_config(_write(tmp_path, raw))
    assert cfg.risk_slope == 3
    assert cfg.macro_lookback == 8


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


def test_load_config_retention_default_and_parse(tmp_path):
    """data.cache_keep_days/snapshot_keep — 없으면 기본값(7/20), 있으면 파싱."""
    cfg = load_config(_write(tmp_path, _minimal_raw()))
    assert cfg.cache_keep_days == 7
    assert cfg.snapshot_keep == 20

    raw = _minimal_raw()
    raw["data"]["cache_keep_days"] = 3
    raw["data"]["snapshot_keep"] = 0  # 0 = 정리 끄기
    cfg = load_config(_write(tmp_path, raw))
    assert cfg.cache_keep_days == 3
    assert cfg.snapshot_keep == 0


@pytest.mark.parametrize(
    "bad_pair",
    [
        ["IWM"],  # 티커 1개
        ["IWM", "SPY", "QQQ"],  # 티커 3개
        "IWM/SPY",  # 리스트가 아님
        [None, "SPY"],  # 문자열이 아님
        ["", "SPY"],  # 빈 문자열
    ],
)
def test_load_config_rejects_malformed_risk_pairs(tmp_path, bad_pair):
    """risk_pairs 항목은 [분자, 분모] 두 티커 문자열 — 아니면 명확한 ConfigError."""
    raw = _minimal_raw()
    raw["tickers"]["risk_pairs"]["Broken"] = bad_pair
    with pytest.raises(ConfigError, match="risk_pairs"):
        load_config(_write(tmp_path, raw))


def test_load_config_rejects_non_mapping_risk_pairs(tmp_path):
    raw = _minimal_raw()
    raw["tickers"]["risk_pairs"] = [["IWM", "SPY"]]  # dict가 아니라 list
    with pytest.raises(ConfigError, match="risk_pairs"):
        load_config(_write(tmp_path, raw))


def test_load_config_backtest_section_default_and_parse(tmp_path):
    """backtest 옵션 섹션 — 없으면 기본값, 있으면 파싱(M4, 하위호환)."""
    cfg = load_config(_write(tmp_path, _minimal_raw()))
    assert cfg.backtest_horizon == 4
    assert cfg.backtest_min_history == 60
    assert cfg.backtest_window_candidates == (8, 10, 14, 20, 26)

    raw = _minimal_raw()
    raw["backtest"] = {"horizon": 6, "min_history": 40, "window_candidates": [10, 14]}
    cfg = load_config(_write(tmp_path, raw))
    assert cfg.backtest_horizon == 6
    assert cfg.backtest_min_history == 40
    assert cfg.backtest_window_candidates == (10, 14)


def test_default_config_backtest_includes_current_window():
    """레포 config.yaml의 스윕 후보에는 현행 rs_window가 포함돼야 한다."""
    cfg = load_config()
    assert cfg.rs_window in cfg.backtest_window_candidates


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


def test_load_config_report_section_default_and_parse(tmp_path):
    """report 옵션 섹션 — 없으면 기본값 'reports', 있으면 파싱(M5, 하위호환)."""
    cfg = load_config(_write(tmp_path, _minimal_raw()))
    assert cfg.report_output_dir == "reports"

    raw = _minimal_raw()
    raw["report"] = {"output_dir": "out/daily"}
    cfg = load_config(_write(tmp_path, raw))
    assert cfg.report_output_dir == "out/daily"
