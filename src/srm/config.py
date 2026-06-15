# config.yaml 로더 — 네트워크 접근 없음. 필수 키 누락 시 명확한 에러로 즉시 실패한다.

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"

# config.yaml에 반드시 있어야 하는 최상위 키와, 그 아래 필수 하위 키.
_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "tickers": ("benchmark", "sectors", "risk_pairs", "macro"),
    "windows": ("rs_window", "mom_window", "risk_ma", "trend_fast", "trend_slow"),
    "weights": ("quad_flow", "rotation", "trend", "trend_gate"),
    "data": ("period", "interval"),
    "thresholds": ("risk_on", "risk_off"),
    "disclaimer": (),
}


class ConfigError(ValueError):
    """config.yaml의 필수 키가 없거나 형식이 잘못된 경우."""


@dataclass(frozen=True)
class Config:
    benchmark: str
    sectors: Mapping[str, str]
    risk_pairs: Mapping[str, tuple[str, str]]
    macro: Mapping[str, str]

    rs_window: int
    mom_window: int
    risk_ma: int
    trend_fast: int
    trend_slow: int

    quad_flow: Mapping[str, float]
    rotation: Mapping[str, float]
    trend: Mapping[str, float]
    trend_gate: bool

    data_period: str
    data_interval: str

    risk_on: float
    risk_off: float

    disclaimer: str

    # --- M4 옵션 윈도우 (config.yaml에 없으면 프로토타입 값 5 — 하위호환) ---
    risk_slope: int = 5
    macro_lookback: int = 5

    # --- 캐시/스냅샷 보관 정책 (data 섹션 옵션 키, 0 = 정리 끄기) ---
    cache_keep_days: int = 7
    snapshot_keep: int = 20

    # --- M5 보고서 옵션 섹션 (config.yaml에 없으면 기본값 — --report-md용) ---
    report_output_dir: str = "reports"

    # --- M4 백테스트 옵션 섹션 (config.yaml에 없으면 기본값 — --backtest용) ---
    backtest_horizon: int = 4
    backtest_min_history: int = 60
    backtest_window_candidates: tuple[int, ...] = (8, 10, 14, 20, 26)

    # --- M3 옵션 섹션 (config.yaml에 없으면 빈 값/기본값 — 사이클 분석을 건너뛴다) ---
    fred_series: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    fred_dbnomics: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    fred_period_years: int = 10
    fred_stale_months: int = 4
    cycle_trend_window: int = 6
    cycle_level_window: int = 120
    cycle_min_indicators: int = 2
    phase_sectors: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


def _require(raw: Mapping[str, Any], top: str, sub_keys: tuple[str, ...]) -> Mapping[str, Any]:
    if top not in raw:
        raise ConfigError(f"config.yaml에 최상위 키 '{top}'이(가) 없습니다.")
    section = raw[top]
    if sub_keys:
        if not isinstance(section, Mapping):
            raise ConfigError(f"config.yaml의 '{top}'은(는) 매핑(dict)이어야 합니다.")
        for key in sub_keys:
            if key not in section:
                raise ConfigError(f"config.yaml의 '{top}.{key}' 키가 없습니다.")
    return section


def _parse_risk_pairs(section: Any) -> dict[str, tuple[str, str]]:
    """tickers.risk_pairs 파싱 — 각 항목은 [분자, 분모] 두 티커 문자열이어야 한다.

    형식이 틀리면 IndexError 같은 불친절한 예외 대신 명확한 ConfigError로 실패한다.
    """
    if not isinstance(section, Mapping):
        raise ConfigError("config.yaml의 'tickers.risk_pairs'은(는) 매핑(dict)이어야 합니다.")
    out: dict[str, tuple[str, str]] = {}
    for name, pair in section.items():
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or not all(isinstance(t, str) and t.strip() for t in pair)
        ):
            raise ConfigError(
                f"config.yaml의 'tickers.risk_pairs.{name}'은(는) [분자, 분모] 형식의 "
                f"티커 문자열 2개여야 합니다 (현재: {pair!r})."
            )
        out[str(name)] = (pair[0], pair[1])
    return out


_VALID_HIGHER_IS = ("expansion", "contraction")


def _parse_indicator_meta(
    section: Mapping[str, Any] | None, where: str
) -> dict[str, dict[str, str]]:
    """fred.series / fred.dbnomics 항목 파싱. higher_is 값이 잘못되면 ConfigError."""
    if not section:
        return {}
    if not isinstance(section, Mapping):
        raise ConfigError(f"config.yaml의 '{where}'은(는) 매핑(dict)이어야 합니다.")
    out: dict[str, dict[str, str]] = {}
    for series_id, meta in section.items():
        meta = dict(meta or {})
        higher_is = meta.get("higher_is", "expansion")
        if higher_is not in _VALID_HIGHER_IS:
            raise ConfigError(
                f"config.yaml의 '{where}.{series_id}.higher_is'는 "
                f"{_VALID_HIGHER_IS} 중 하나여야 합니다 (현재: {higher_is!r})."
            )
        meta["higher_is"] = higher_is
        meta.setdefault("name", str(series_id))
        out[str(series_id)] = meta
    return out


def load_config(path: str | Path | None = None) -> Config:
    """config.yaml을 읽어 불변 Config를 만든다. 누락된 필수 키는 ConfigError로 즉시 실패."""
    cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise ConfigError(f"config 파일을 찾을 수 없습니다: {cfg_path}")

    with cfg_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, Mapping):
        raise ConfigError(f"config.yaml의 최상위는 매핑(dict)이어야 합니다: {cfg_path}")

    for top, sub_keys in _REQUIRED_KEYS.items():
        _require(raw, top, sub_keys)

    tickers = raw["tickers"]
    windows = raw["windows"]
    weights = raw["weights"]
    data = raw["data"]
    thresholds = raw["thresholds"]

    risk_pairs = _parse_risk_pairs(tickers["risk_pairs"])

    # M4 백테스트 옵션 섹션 — 없으면 기본값으로 동작한다.
    backtest = raw.get("backtest") or {}

    # M5 보고서 옵션 섹션 — 없으면 기본값으로 동작한다.
    report = raw.get("report") or {}

    # M3 옵션 섹션 — 없으면 빈 dict/기본값으로 두고 사이클 분석은 건너뛴다.
    fred = raw.get("fred") or {}
    cycle = raw.get("cycle") or {}
    phase_sectors = {
        str(phase): tuple(str(t) for t in tickers_)
        for phase, tickers_ in (cycle.get("phase_sectors") or {}).items()
    }

    return Config(
        benchmark=tickers["benchmark"],
        sectors=dict(tickers["sectors"]),
        risk_pairs=risk_pairs,
        macro=dict(tickers["macro"]),
        rs_window=int(windows["rs_window"]),
        mom_window=int(windows["mom_window"]),
        risk_ma=int(windows["risk_ma"]),
        trend_fast=int(windows["trend_fast"]),
        trend_slow=int(windows["trend_slow"]),
        risk_slope=int(windows.get("risk_slope", 5)),
        macro_lookback=int(windows.get("macro_lookback", 5)),
        quad_flow=dict(weights["quad_flow"]),
        rotation=dict(weights["rotation"]),
        trend=dict(weights["trend"]),
        trend_gate=bool(weights["trend_gate"]),
        data_period=str(data["period"]),
        data_interval=str(data["interval"]),
        cache_keep_days=int(data.get("cache_keep_days", 7)),
        snapshot_keep=int(data.get("snapshot_keep", 20)),
        report_output_dir=str(report.get("output_dir", "reports")),
        risk_on=float(thresholds["risk_on"]),
        risk_off=float(thresholds["risk_off"]),
        disclaimer=str(raw["disclaimer"]),
        backtest_horizon=int(backtest.get("horizon", 4)),
        backtest_min_history=int(backtest.get("min_history", 60)),
        backtest_window_candidates=tuple(
            int(w) for w in backtest.get("window_candidates", (8, 10, 14, 20, 26))
        ),
        fred_series=_parse_indicator_meta(fred.get("series"), "fred.series"),
        fred_dbnomics=_parse_indicator_meta(fred.get("dbnomics"), "fred.dbnomics"),
        fred_period_years=int(fred.get("period_years", 10)),
        fred_stale_months=int(fred.get("stale_months", 4)),
        cycle_trend_window=int(cycle.get("trend_window", 6)),
        cycle_level_window=int(cycle.get("level_window", 120)),
        cycle_min_indicators=int(cycle.get("min_indicators", 2)),
        phase_sectors=phase_sectors,
    )
