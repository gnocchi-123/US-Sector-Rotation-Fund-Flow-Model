# 가격 데이터 스냅샷 — 재현성(00_PROJECT_SPEC.md 4)을 위해 실행 시점에 사용한
# 가격 데이터와 분석 메타데이터를 snapshots/<timestamp>/에 저장한다. 네트워크 접근 없음.
#
# 같은 스냅샷 디렉터리를 다시 로드하면 동일한 가격 데이터를 복원하므로,
# 그 데이터로 계산한 리포트도 항상 동일하다(=재현 가능).

from __future__ import annotations

import json
import shutil
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


def prune_snapshots(snapshot_dir: Path | str = DEFAULT_SNAPSHOT_DIR, keep: int = 20) -> list[Path]:
    """타임스탬프 이름순 최신 keep개만 남기고 오래된 스냅샷을 삭제, 목록을 반환한다.

    실행마다 스냅샷이 쌓이므로 새로 저장할 때 호출해 초과분을 정리한다
    (보관 정책: config.yaml data.snapshot_keep). keep <= 0이면 정리하지 않는다.
    meta.json이 있는 디렉터리만 스냅샷으로 간주해 다른 파일의 오삭제를 막고,
    개별 삭제 실패는 무시한다(예외 없이 degrade).
    """
    if keep <= 0:
        return []
    root = Path(snapshot_dir)
    if not root.exists():
        return []
    snaps = sorted(
        (d for d in root.iterdir() if d.is_dir() and (d / "meta.json").exists()),
        key=lambda d: d.name,
    )
    removed: list[Path] = []
    for d in snaps[: max(len(snaps) - keep, 0)]:
        try:
            shutil.rmtree(d)
            removed.append(d)
        except OSError:
            continue
    return removed


def load_snapshot_frame(path: Path | str, name: str) -> pd.DataFrame | None:
    """스냅샷의 추가 프레임(<name>.parquet)을 읽는다. 없으면 None(예외 없음) —
    extra_frames 없이 저장된 과거 스냅샷도 그대로 동작한다(하위호환)."""
    frame_path = Path(path) / f"{name}.parquet"
    if not frame_path.exists():
        return None
    return pd.read_parquet(frame_path)
