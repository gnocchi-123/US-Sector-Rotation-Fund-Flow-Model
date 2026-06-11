# 경기 사이클 위치 추정 — 선행지표 묶음의 (수준 x 방향) 2x2 -> 4국면 ("어느 국면").
# 순수함수만 둔다. 네트워크/설정 파일 접근은 하지 않는다(윈도우 등은 인자로 받음).
#
# 정의 (ROADMAP.md M3):
#   수준(level)     = 최신 월간값의 롤링 z-score (기본 120개월). 역사 대비 높은/낮은 상태.
#   방향(direction) = 최근 trend_window개월 변화의 부호. 한 점이 아니라 추세로 판단해
#                     발표지연·사후개정 노이즈를 완화한다.
#   higher_is=contraction 인 지표(실업수당 청구 등)는 부호를 반전해 합산한다.
#
#   | 국면 | 조건 | 상태 서술 |
#   |---|---|---|
#   | Recovery    | 수준 낮음, 방향 상승 | 낮은 수준에서 개선 중 |
#   | Expansion   | 수준 높음, 방향 상승 | 높은 수준에서 개선 유지 |
#   | Slowdown    | 수준 높음, 방향 하락 | 높은 수준에서 둔화 중 |
#   | Contraction | 수준 낮음, 방향 하락 | 낮은 수준에서 악화 중 |
#
# 주의: 선행지표라도 발표 지연과 사후 개정이 있어 '현재 상태 확인'일 뿐이며,
# 미래 방향을 단정하지 않는다. 국면 분류는 참고용 맥락 정보다.

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

UNKNOWN_PHASE = "Unknown (데이터 부족)"

# 국면별 상태 서술 — 단정적 미래 표현 금지, 현재 상태만 기술한다.
PHASE_DESCRIPTIONS: dict[str, str] = {
    "Recovery": "선행지표가 역사 대비 낮은 수준에서 개선 중인 상태",
    "Expansion": "선행지표가 역사 대비 높은 수준에서 개선을 유지 중인 상태",
    "Slowdown": "선행지표가 역사 대비 높은 수준에서 둔화 중인 상태",
    "Contraction": "선행지표가 역사 대비 낮은 수준에서 악화 중인 상태",
}


def classify_cycle_phase(level_sign: int, direction_sign: int) -> str:
    """합성 수준/방향 부호의 2x2 국면 분류 (rrg.classify_quadrant와 같은 구조)."""
    if direction_sign >= 0:
        return "Expansion" if level_sign >= 0 else "Recovery"
    return "Slowdown" if level_sign >= 0 else "Contraction"


def indicator_state(
    series: pd.Series,
    higher_is: str = "expansion",
    trend_window: int = 6,
    level_window: int = 120,
) -> dict | None:
    """지표 하나의 수준 z-score와 방향을 판정한다. 데이터 부족 시 None(degrade).

    혼합 주기(일/주/월간) 입력을 월말 리샘플로 통일한 뒤,
    수준 = 최신값의 롤링 z-score, 방향 = 최근 trend_window개월 변화의 부호.
    higher_is="contraction"이면 두 값의 부호를 반전해 '확장 방향 양수'로 맞춘다.
    """
    monthly = series.dropna().resample("ME").last().dropna()
    if len(monthly) < trend_window + 1:
        return None

    m = monthly.rolling(level_window, min_periods=level_window // 2).mean()
    s = monthly.rolling(level_window, min_periods=level_window // 2).std()
    z = (monthly - m) / s.replace(0, np.nan)
    level_z = z.iloc[-1]
    if np.isnan(level_z):
        return None

    change = monthly.iloc[-1] - monthly.iloc[-1 - trend_window]
    sign = -1.0 if higher_is == "contraction" else 1.0
    level_z *= sign
    change *= sign

    direction = "up" if change > 0 else ("down" if change < 0 else "flat")
    return {
        "level_z": round(float(level_z), 2),
        "direction": direction,
        "last_obs": monthly.index[-1].date(),
    }


def compute_cycle_position(
    indicators: pd.DataFrame,
    series_meta: Mapping[str, Mapping[str, str]],
    trend_window: int = 6,
    level_window: int = 120,
    min_indicators: int = 2,
) -> dict:
    """선행지표 패널의 합의로 경기 사이클 위치를 추정한다.

    방향 = 지표별 up/down 투표 합(breadth), 수준 = 지표별 signed z-score 평균.
    유효 지표가 min_indicators 미만이면 Unknown으로 degrade한다
    (risk.compute_risk_appetite의 counted==0 패턴과 동일한 철학).
    """
    details: dict[str, str] = {}
    states: list[dict] = []
    for col in indicators.columns:
        meta = series_meta.get(col, {})
        state = indicator_state(
            indicators[col],
            higher_is=meta.get("higher_is", "expansion"),
            trend_window=trend_window,
            level_window=level_window,
        )
        name = meta.get("name", col)
        if state is None:
            details[name] = "데이터 부족 (제외)"
            continue
        states.append(state)
        details[name] = (
            f"{state['direction']} / 수준 z={state['level_z']:+.2f}"
            f" (마지막 관측 {state['last_obs']})"
        )

    if len(states) < min_indicators:
        return {
            "phase": UNKNOWN_PHASE,
            "description": "유효한 선행지표가 부족해 국면을 판정하지 않음",
            "counted": len(states),
            "level_score": 0.0,
            "direction_score": 0,
            "details": details,
        }

    direction_score = sum(
        1 if st["direction"] == "up" else (-1 if st["direction"] == "down" else 0) for st in states
    )
    level_score = float(np.mean([st["level_z"] for st in states]))
    phase = classify_cycle_phase(
        level_sign=1 if level_score >= 0 else -1,
        direction_sign=1 if direction_score >= 0 else -1,
    )
    return {
        "phase": phase,
        "description": PHASE_DESCRIPTIONS[phase],
        "counted": len(states),
        "level_score": round(level_score, 2),
        "direction_score": direction_score,
        "details": details,
    }
