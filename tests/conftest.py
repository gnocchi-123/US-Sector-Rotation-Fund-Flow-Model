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


@pytest.fixture
def short_price_panel() -> pd.DataFrame:
    """trend_state의 데이터 부족 degrade("n/a") 경로 검증용 — rolling 윈도우가 항상 NaN."""
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame({"ANY": [100.0, 101.0, 102.0, 101.5, 103.0]}, index=idx)
