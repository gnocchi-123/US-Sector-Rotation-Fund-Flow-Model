# Layer 3 (추세) 단위테스트 — 합성 데이터, 네트워크 없음.

import pandas as pd

from srm.signals.trend import trend_state


def test_trend_state_uptrend_and_downtrend(price_panel: pd.DataFrame):
    assert trend_state(price_panel, "TREND_UP") == "Uptrend"
    assert trend_state(price_panel, "TREND_DOWN") == "Downtrend"


def test_trend_state_pullback_is_neutral(price_panel: pd.DataFrame):
    # 장기 상승 후 최근 단기 조정: last < fast-MA, fast-MA > slow-MA -> Neutral
    assert trend_state(price_panel, "TREND_PULLBACK") == "Neutral"


def test_trend_state_missing_ticker_is_na(price_panel: pd.DataFrame):
    assert trend_state(price_panel, "NOPE") == "n/a"


def test_trend_state_insufficient_data_is_na(short_price_panel: pd.DataFrame):
    assert trend_state(short_price_panel, "ANY") == "n/a"
