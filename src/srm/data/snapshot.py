# 가격 데이터 스냅샷 — 재현성(00_PROJECT_SPEC.md 4)을 위해 실행 시점에 사용한
# 가격 데이터와 분석 메타데이터를 snapshots/<timestamp>/에 저장한다. 네트워크 접근 없음.
#
# 같은 스냅샷 디렉터리를 다시 로드하면 동일한 가격 데이터를 복원하므로,
# 그 데이터로 계산한 리포트도 항상 동일하다(=재현 가능).

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DEFAULT_SNAPSHOT_DIR = Path("snapshots")


def save_snapshot(
    prices: pd.DataFrame,
    meta: dict,
    snapshot_dir: Path | str = DEFAULT_SNAPSHOT_DIR,
    extra_frames: dict[str, pd.DataFrame] | None = None,
) -> Path:
    """가격 데이터(prices.parquet)와 메타데이터(meta.json)를 새 타임스탬프
    디렉터리에 저장하고 그 경로를 반환한다. meta에는 timestamp가 자동으로 추가된다.

    extra_frames로 추가 데이터(예: 선행지표 패널)를 <이름>.parquet으로 함께
    저장할 수 있다 — 같은 스냅샷에서 사이클 섹션까지 재현하기 위함."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out_dir = Path(snapshot_dir) / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    prices.to_parquet(out_dir / "prices.parquet")
    for name, frame in (extra_frames or {}).items():
        frame.to_parquet(out_dir / f"{name}.parquet")
    payload = {"timestamp": timestamp, **meta}
    with (out_dir / "meta.json").open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return out_dir


def load_snapshot(path: Path | str) -> tuple[pd.DataFrame, dict]:
    """save_snapshot으로 저장한 디렉터리에서 가격 데이터와 메타데이터를 복원한다."""
    snap_dir = Path(path)
    prices = pd.read_parquet(snap_dir / "prices.parquet")
    with (snap_dir / "meta.json").open(encoding="utf-8") as f:
        meta = json.load(f)
    return prices, meta


def load_snapshot_frame(path: Path | str, name: str) -> pd.DataFrame | None:
    """스냅샷의 추가 프레임(<name>.parquet)을 읽는다. 없으면 None(예외 없음) —
    extra_frames 없이 저장된 과거 스냅샷도 그대로 동작한다(하위호환)."""
    frame_path = Path(path) / f"{name}.parquet"
    if not frame_path.exists():
        return None
    return pd.read_parquet(frame_path)
