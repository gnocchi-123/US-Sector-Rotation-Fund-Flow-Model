# 데이터 로더 — yfinance 다운로드. 네트워크 접근은 이 모듈에만 격리한다.
# signals/* 등 신호 계산 모듈은 fetch_prices()가 반환하는 DataFrame만 받아 순수하게 동작한다.

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def fetch_prices(tickers: Iterable[str], period: str = "2y", interval: str = "1wk") -> pd.DataFrame:
    """티커별 수정종가(Close, auto-adjusted) 시계열을 받아온다.

    일부 티커 다운로드가 실패해도 예외로 죽지 않고, 받아온 컬럼만으로
    DataFrame을 구성한다(안전한 degrade). 흐름/가격 데이터는 후행적일 수 있다.
    """
    import yfinance as yf

    tickers = sorted(set(tickers))
    raw = yf.download(
        tickers,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        group_by="column",
    )

    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:
        close = raw[["Close"]].copy()
        close.columns = tickers

    close = close.dropna(axis=1, how="all")
    return close.dropna(how="all").ffill()
