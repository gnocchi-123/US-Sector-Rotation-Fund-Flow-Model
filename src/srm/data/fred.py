# 선행지표 로더 — FRED 공식 API + DBnomics. 네트워크 접근은 이 모듈에만 격리한다.
#
# - FRED: 공식 REST API(api.stlouisfed.org). API 키는 환경변수 FRED_API_KEY에서만
#   읽는다(파일/하드코딩 금지). 키가 없으면 빈 결과로 안전하게 degrade.
#   키 없는 fredgraph.csv 엔드포인트도 존재하지만 비공식이라(약관·안정성 보장 없음,
#   봇 차단 사례 확인됨) 기본으로 쓰지 않는다.
# - DBnomics: 키 불필요 공공 미러(api.db.nomics.world). ISM PMI처럼 FRED에서
#   제공이 중단된 시리즈의 보조 소스로 쓴다. 단, 미러 갱신이 정체될 수 있으므로
#   drop_stale_series()로 오래된 시리즈를 판정에서 제외해야 한다.
#   (2026-06 실측: ISM/pmi/pm은 2025-12에서 갱신이 멈췄고 2025-09 이후 값이
#   10 근처로 손상돼 있다. stale 가드가 시리즈를 통째로 제외해 안전.)
# - 선행지표라도 발표 지연(수일~1개월)과 사후 개정이 있어 최신 경제 상태와
#   다를 수 있다. 사용자 대면 출력에 이 한계를 명시할 것.

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from datetime import date as date_cls

import pandas as pd

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
DBNOMICS_API_URL = "https://api.db.nomics.world/v22/series"
API_KEY_ENV = "FRED_API_KEY"


def get_api_key() -> str | None:
    """FRED API 키는 환경변수에서만 읽는다. 없으면 None(예외 없음)."""
    key = os.environ.get(API_KEY_ENV, "").strip()
    return key or None


def _request_json(url: str, timeout: float = 10.0) -> dict:
    """HTTP GET → JSON. 테스트에서 이 함수를 monkeypatch해 네트워크를 끊는다."""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_fred_observations(payload: Mapping) -> pd.Series:
    """FRED observations payload → 시계열. 결측치 '.'은 NaN으로 처리한다."""
    obs = payload.get("observations", [])
    index, values = [], []
    for row in obs:
        index.append(pd.Timestamp(row["date"]))
        raw = row.get("value", ".")
        values.append(float(raw) if raw not in (".", "", None) else float("nan"))
    return pd.Series(values, index=pd.DatetimeIndex(index), dtype=float).dropna()


def _parse_dbnomics_series(payload: Mapping) -> pd.Series:
    """DBnomics v22 series payload → 시계열. value의 None/NA는 제거한다."""
    docs = payload.get("series", {}).get("docs", [])
    if not docs:
        return pd.Series(dtype=float)
    doc = docs[0]
    periods = doc.get("period", [])
    values = doc.get("value", [])
    index, out = [], []
    for p, v in zip(periods, values):
        if v is None or v == "NA":
            continue
        index.append(pd.Timestamp(p))
        out.append(float(v))
    return pd.Series(out, index=pd.DatetimeIndex(index), dtype=float)


def fetch_fred_series(
    series_ids: Iterable[str],
    period_years: int = 10,
    api_key: str | None = None,
) -> pd.DataFrame:
    """FRED 시리즈들을 받아 하나의 DataFrame(인덱스 union, 결측 NaN)으로 합친다.

    - 키가 없으면 빈 DataFrame 반환(안전 degrade, 예외 없음).
    - 시리즈별로 실패해도 해당 컬럼만 건너뛴다(부분 degrade).
    """
    api_key = api_key or get_api_key()
    if api_key is None:
        return pd.DataFrame()

    start = pd.Timestamp.today() - pd.DateOffset(years=period_years)
    columns: dict[str, pd.Series] = {}
    for sid in series_ids:
        params = urllib.parse.urlencode(
            {
                "series_id": sid,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start.date().isoformat(),
            }
        )
        try:
            series = _parse_fred_observations(_request_json(f"{FRED_API_URL}?{params}"))
        except Exception as exc:  # noqa: BLE001 — 어떤 실패도 전체를 죽이지 않는다
            print(f"[FRED] {sid} 로드 실패, 건너뜀: {exc}")
            continue
        if not series.empty:
            columns[sid] = series
    return pd.DataFrame(columns)


def fetch_dbnomics_series(meta: Mapping[str, Mapping[str, str]]) -> pd.DataFrame:
    """DBnomics 시리즈들(키 불필요)을 받아 DataFrame으로 합친다.

    meta: {지표ID: {"provider_code": "ISM/pmi/pm", ...}}. 실패한 시리즈는 건너뛴다.
    """
    columns: dict[str, pd.Series] = {}
    for indicator_id, m in meta.items():
        code = m.get("provider_code")
        if not code:
            continue
        url = f"{DBNOMICS_API_URL}/{code}?observations=1&format=json"
        try:
            series = _parse_dbnomics_series(_request_json(url))
        except Exception as exc:  # noqa: BLE001
            print(f"[DBnomics] {indicator_id}({code}) 로드 실패, 건너뜀: {exc}")
            continue
        if not series.empty:
            columns[indicator_id] = series
    return pd.DataFrame(columns)


def drop_stale_series(
    indicators: pd.DataFrame,
    stale_months: int = 4,
    as_of: date_cls | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """마지막 관측이 stale_months보다 오래된 컬럼을 제외한다.

    미러 갱신 정체(예: DBnomics ISM) 등으로 낡은 데이터가 사이클 판정을
    오염시키지 않게 하는 가드. 반환: (남은 DataFrame, 제외된 컬럼 이름 목록).
    """
    if indicators.empty:
        return indicators, []
    cutoff = pd.Timestamp(as_of or date_cls.today()) - pd.DateOffset(months=stale_months)
    stale: list[str] = []
    for col in indicators.columns:
        last_obs = indicators[col].dropna().index.max()
        if pd.isna(last_obs) or last_obs < cutoff:
            stale.append(col)
    return indicators.drop(columns=stale), stale
