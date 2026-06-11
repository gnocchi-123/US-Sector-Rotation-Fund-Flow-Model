# data/fred.py 테스트 — 네트워크 없이 통과해야 한다 (_request_json monkeypatch).

import pandas as pd
import pytest

from srm.data import fred


def _fred_payload(rows):
    return {"observations": [{"date": d, "value": v} for d, v in rows]}


def _dbnomics_payload(periods, values):
    return {"series": {"docs": [{"period": periods, "value": values}]}}


def test_get_api_key_from_env(monkeypatch):
    monkeypatch.setenv(fred.API_KEY_ENV, "abc123")
    assert fred.get_api_key() == "abc123"
    monkeypatch.setenv(fred.API_KEY_ENV, "   ")
    assert fred.get_api_key() is None
    monkeypatch.delenv(fred.API_KEY_ENV, raising=False)
    assert fred.get_api_key() is None


def test_fetch_fred_series_without_key_returns_empty(monkeypatch):
    """키 미설정 시 네트워크 시도 없이 빈 DataFrame(안전 degrade)."""
    monkeypatch.delenv(fred.API_KEY_ENV, raising=False)

    def boom(url, timeout=10.0):
        raise AssertionError("키가 없으면 네트워크를 호출하면 안 된다")

    monkeypatch.setattr(fred, "_request_json", boom)
    out = fred.fetch_fred_series(["T10Y2Y"])
    assert out.empty


def test_parse_fred_observations_handles_missing_dot():
    payload = _fred_payload([("2025-01-01", "1.5"), ("2025-02-01", "."), ("2025-03-01", "2.0")])
    series = fred._parse_fred_observations(payload)
    assert list(series.values) == [1.5, 2.0]
    assert series.index[0] == pd.Timestamp("2025-01-01")


def test_fetch_fred_series_partial_failure(monkeypatch):
    """일부 시리즈 요청이 실패해도 나머지 컬럼은 정상 반환(부분 degrade)."""

    def fake_request(url, timeout=10.0):
        if "series_id=BAD" in url:
            raise OSError("simulated network error")
        return _fred_payload([("2025-01-01", "1.0"), ("2025-02-01", "2.0")])

    monkeypatch.setattr(fred, "_request_json", fake_request)
    out = fred.fetch_fred_series(["GOOD", "BAD"], api_key="k")
    assert list(out.columns) == ["GOOD"]
    assert len(out) == 2


def test_parse_dbnomics_series():
    payload = _dbnomics_payload(["2025-01", "2025-02", "2025-03"], [48.5, None, 49.0])
    series = fred._parse_dbnomics_series(payload)
    assert list(series.values) == [48.5, 49.0]
    assert fred._parse_dbnomics_series({"series": {"docs": []}}).empty


def test_fetch_dbnomics_series(monkeypatch):
    def fake_request(url, timeout=10.0):
        assert "ISM/pmi/pm" in url
        return _dbnomics_payload(["2025-01", "2025-02"], [48.0, 48.7])

    monkeypatch.setattr(fred, "_request_json", fake_request)
    meta = {"ISM_PMI": {"provider_code": "ISM/pmi/pm", "higher_is": "expansion"}}
    out = fred.fetch_dbnomics_series(meta)
    assert list(out.columns) == ["ISM_PMI"]
    assert out["ISM_PMI"].iloc[-1] == 48.7


def test_fetch_dbnomics_series_failure_degrades(monkeypatch):
    def boom(url, timeout=10.0):
        raise OSError("simulated network error")

    monkeypatch.setattr(fred, "_request_json", boom)
    meta = {"ISM_PMI": {"provider_code": "ISM/pmi/pm"}}
    assert fred.fetch_dbnomics_series(meta).empty


@pytest.mark.parametrize(
    ("last_obs", "expect_stale"),
    [("2026-05-01", False), ("2025-11-01", True)],
)
def test_drop_stale_series(last_obs, expect_stale):
    """as_of 기준 stale_months(4개월)보다 오래된 시리즈는 제외된다."""
    fresh_idx = pd.date_range("2025-06-30", "2026-05-31", freq="ME")
    df = pd.DataFrame(
        {
            "FRESH": pd.Series(range(len(fresh_idx)), index=fresh_idx, dtype=float),
            "TESTED": pd.Series(
                [1.0], index=pd.DatetimeIndex([pd.Timestamp(last_obs)]), dtype=float
            ),
        }
    )
    kept, stale = fred.drop_stale_series(df, stale_months=4, as_of=pd.Timestamp("2026-06-11"))
    if expect_stale:
        assert stale == ["TESTED"]
        assert list(kept.columns) == ["FRESH"]
    else:
        assert stale == []
        assert set(kept.columns) == {"FRESH", "TESTED"}


def test_drop_stale_series_empty():
    kept, stale = fred.drop_stale_series(pd.DataFrame())
    assert kept.empty and stale == []
