# 합성 가격 데이터 fixture — 외부 네트워크 없이 signals/* 단위테스트에 직접 주입한다.

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _walk(
    rng: np.random.Generator, n: int, drift: float, vol: float = 1.0, start: float = 100.0
) -> np.ndarray:
    """drift가 있는 랜덤워크 가격 시계열을 만든다."""
    steps = rng.normal(drift, vol, n)
    return start + np.cumsum(steps)


@pytest.fixture
def price_panel() -> pd.DataFrame:
    """RRG/위험선호/추세 신호 함수를 테스트하기 위한 합성 가격 패널.

    n=260(주봉, 추세 슬로우 윈도우 200을 만족하는 길이)이며 시드를 고정해 매 실행
    동일한 결과를 보장한다.
    """
    rng = np.random.default_rng(42)
    n = 260
    idx = pd.date_range("2020-01-06", periods=n, freq="W-MON")

    data = {
        # RRG: BENCH 대비 STRONG은 꾸준히 강세, WEAK는 꾸준히 약세
        "BENCH": _walk(rng, n, drift=0.30, vol=1.0, start=400.0),
        "STRONG": _walk(rng, n, drift=0.90, vol=1.0, start=150.0),
        "WEAK": _walk(rng, n, drift=-0.30, vol=1.0, start=60.0),
        # 위험선호: BENCH 대비 UP*는 꾸준히 강세(ratio_score=+1), DOWN*는 꾸준히 약세(-1)
        "UP1": _walk(rng, n, drift=0.80, vol=1.0, start=180.0),
        "UP2": _walk(rng, n, drift=0.90, vol=1.0, start=150.0),
        "DOWN1": _walk(rng, n, drift=-0.20, vol=1.0, start=170.0),
        "DOWN2": _walk(rng, n, drift=-0.40, vol=1.0, start=70.0),
    }

    # 추세: 장기/최근 모두 같은 방향(노이즈 작게)
    data["TREND_UP"] = _walk(rng, n, drift=0.50, vol=0.3, start=100.0)
    data["TREND_DOWN"] = _walk(rng, n, drift=-0.50, vol=0.3, start=100.0)

    # 추세: 장기 상승 후 최근 단기 조정 (last < fast-MA, fast-MA > slow-MA -> Neutral)
    up_phase = _walk(rng, 220, drift=0.60, vol=0.2, start=100.0)
    down_phase = _walk(rng, 40, drift=-1.50, vol=0.2, start=up_phase[-1])
    data["TREND_PULLBACK"] = np.concatenate([up_phase, down_phase])

    return pd.DataFrame(data, index=idx)


def _indicator_panel(level_drift: float, recent_drift: float) -> pd.DataFrame:
    """사이클 테스트용 합성 선행지표 패널 (시드 고정, 혼합 주기).

    M1 RRG 교훈: 칼날 경계(z~0, 변화~0) 단언은 피하고 drift를 크게 줘
    수준/방향 부호가 확실한 케이스만 만든다.
    - 전반(level_drift)으로 역사 대비 수준을, 후반 12개월(recent_drift)로
      최근 방향을 명확하게 설계한다.
    - MONTHLY_*는 월간, DAILY는 일간 — 혼합 주기 리샘플 경로를 함께 검증.
    """
    rng = np.random.default_rng(7)
    n_m = 120  # 월간 120개월 (10년)

    def hist_then_recent(start: float) -> np.ndarray:
        hist = _walk(rng, n_m - 12, drift=level_drift, vol=0.2, start=start)
        recent = _walk(rng, 12, drift=recent_drift, vol=0.2, start=hist[-1])
        return np.concatenate([hist, recent])

    m_idx = pd.date_range("2016-01-31", periods=n_m, freq="ME")
    panel = pd.DataFrame(
        {
            "MONTHLY_A": hist_then_recent(50.0),
            "MONTHLY_B": hist_then_recent(100.0),
        },
        index=m_idx,
    )

    # 일간 시리즈 — 같은 구조를 일간 해상도로 (월간 패널과 인덱스 union으로 합쳐짐)
    d_idx = pd.date_range(m_idx[0], m_idx[-1], freq="D")
    n_d = len(d_idx)
    n_recent = 365
    hist = _walk(rng, n_d - n_recent, drift=level_drift / 30, vol=0.05, start=1.0)
    recent = _walk(rng, n_recent, drift=recent_drift / 30, vol=0.05, start=hist[-1])
    daily = pd.Series(np.concatenate([hist, recent]), index=d_idx, name="DAILY")

    return panel.join(daily, how="outer")


@pytest.fixture
def expansion_panel() -> pd.DataFrame:
    """수준 높음(꾸준한 상승 이력의 끝) + 최근 방향 상승 -> Expansion형."""
    return _indicator_panel(level_drift=0.3, recent_drift=1.0)


@pytest.fixture
def contraction_panel() -> pd.DataFrame:
    """수준 낮음(꾸준한 하락 이력의 끝) + 최근 방향 하락 -> Contraction형."""
    return _indicator_panel(level_drift=-0.3, recent_drift=-1.0)


@pytest.fixture
def short_price_panel() -> pd.DataFrame:
    """trend_state의 데이터 부족 degrade("n/a") 경로 검증용 — rolling 윈도우가 항상 NaN."""
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame({"ANY": [100.0, 101.0, 102.0, 101.5, 103.0]}, index=idx)
