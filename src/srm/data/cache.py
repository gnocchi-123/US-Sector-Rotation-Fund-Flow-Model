# 가격 데이터 parquet 로컬 캐시 — 네트워크 접근 없음.
#
# fetch_prices()의 결과를 저장/재사용해 반복 다운로드를 줄인다. 캐시 키는
# (티커 집합, period, interval, 날짜)이므로 날짜가 바뀌면 자동으로 새 키가 되어
# 하루 단위로 갱신된다(=daily refresh).

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterable
from datetime import date as date_cls
from pathlib import Path

import pandas as pd

DEFAULT_CACHE_DIR = Path(".cache/prices")


def cache_path(
    tickers: Iterable[str],
    period: str,
    interval: str,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    as_of: str | None = None,
) -> Path:
    """캐시 파일 경로. 키 = 정렬된 티커 집합 + period + interval + as_of(기본 오늘)."""
    as_of = as_of or date_cls.today().isoformat()
    key = "|".join([",".join(sorted(set(tickers))), period, interval, as_of])
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return Path(cache_dir) / f"{digest}.parquet"


def load_cached_prices(
    tickers: Iterable[str],
    period: str,
    interval: str,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
) -> pd.DataFrame | None:
    """캐시 파일이 있으면 읽어서 반환, 없으면 None(예외 없이 캐시 미스로 처리)."""
    path = cache_path(tickers, period, interval, cache_dir)
    if not path.exists():
        return None
    return pd.read_parquet(path)


def save_prices(
    prices: pd.DataFrame,
    tickers: Iterable[str],
    period: str,
    interval: str,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
) -> Path:
    """가격 데이터를 캐시에 저장하고 경로를 반환한다."""
    path = cache_path(tickers, period, interval, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(path)
    return path


def prune_cache(cache_dir: Path | str = DEFAULT_CACHE_DIR, keep_days: int = 7) -> list[Path]:
    """마지막 수정이 keep_days보다 오래된 캐시 파일을 삭제하고 그 목록을 반환한다.

    캐시 키에 날짜가 들어가 하루마다 새 파일이 쌓이므로, 새로 저장할 때 호출해
    오래된 파일을 정리한다(보관 정책: config.yaml data.cache_keep_days).
    keep_days <= 0이면 정리하지 않는다. 캐시는 언제든 재생성 가능하므로
    개별 삭제 실패는 무시한다(예외 없이 degrade).
    """
    if keep_days <= 0:
        return []
    root = Path(cache_dir)
    if not root.exists():
        return []
    cutoff = time.time() - keep_days * 86400
    removed: list[Path] = []
    for f in root.glob("*.parquet"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed.append(f)
        except OSError:
            continue
    return removed
