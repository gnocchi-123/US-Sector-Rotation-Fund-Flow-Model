# 가격 캐시(data/cache.py) 단위테스트 — 네트워크 없음, 파일 I/O는 tmp_path에서.

import pandas as pd

from srm.data.cache import cache_path, load_cached_prices, save_prices


def test_cache_path_stable_for_same_inputs(tmp_path):
    a = cache_path(["SPY", "XLK"], "2y", "1wk", tmp_path, as_of="2026-06-10")
    b = cache_path(["XLK", "SPY"], "2y", "1wk", tmp_path, as_of="2026-06-10")
    assert a == b  # 티커 순서는 결과에 영향 없음(정렬 후 키 생성)


def test_cache_path_changes_with_inputs(tmp_path):
    base = cache_path(["SPY", "XLK"], "2y", "1wk", tmp_path, as_of="2026-06-10")
    diff_tickers = cache_path(["SPY", "XLF"], "2y", "1wk", tmp_path, as_of="2026-06-10")
    diff_period = cache_path(["SPY", "XLK"], "1y", "1wk", tmp_path, as_of="2026-06-10")
    diff_interval = cache_path(["SPY", "XLK"], "2y", "1d", tmp_path, as_of="2026-06-10")
    diff_date = cache_path(["SPY", "XLK"], "2y", "1wk", tmp_path, as_of="2026-06-11")

    assert len({base, diff_tickers, diff_period, diff_interval, diff_date}) == 5


def test_save_and_load_roundtrip(tmp_path, price_panel: pd.DataFrame):
    tickers = ["BENCH", "STRONG", "WEAK"]
    saved_path = save_prices(price_panel, tickers, "2y", "1wk", tmp_path)
    assert saved_path.exists()

    loaded = load_cached_prices(tickers, "2y", "1wk", tmp_path)
    assert loaded is not None
    # parquet 라운드트립에서 DatetimeIndex의 freq 메타데이터는 보존되지 않는다(값은 동일).
    pd.testing.assert_frame_equal(loaded, price_panel, check_freq=False)


def test_load_cached_prices_missing_returns_none(tmp_path):
    assert load_cached_prices(["SPY"], "2y", "1wk", tmp_path) is None
