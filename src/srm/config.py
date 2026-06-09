# config.yaml 로더 — 네트워크 접근 없음. 필수 키 누락 시 명확한 에러로 즉시 실패한다.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"

# config.yaml에 반드시 있어야 하는 최상위 키와, 그 아래 필수 하위 키.
_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "tickers": ("benchmark", "sectors", "risk_pairs", "macro"),
    "windows": ("rs_window", "mom_window", "risk_ma", "trend_fast", "trend_slow"),
    "weights": ("quad_flow", "rotation", "trend", "trend_gate"),
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

    risk_on: float
    risk_off: float

    disclaimer: str


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
    thresholds = raw["thresholds"]

    risk_pairs = {
        name: (pair[0], pair[1]) for name, pair in tickers["risk_pairs"].items()
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
        quad_flow=dict(weights["quad_flow"]),
        rotation=dict(weights["rotation"]),
        trend=dict(weights["trend"]),
        trend_gate=bool(weights["trend_gate"]),
        risk_on=float(thresholds["risk_on"]),
        risk_off=float(thresholds["risk_off"]),
        disclaimer=str(raw["disclaimer"]),
    )
