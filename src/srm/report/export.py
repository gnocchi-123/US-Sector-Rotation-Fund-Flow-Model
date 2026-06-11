# 섹터 자금흐름 랭킹표를 JSON/CSV로 내보낸다.
#
# JSON에는 국면(regime)/점수/면책문구 등 메타데이터를 함께 담아, 표만으로는
# 알 수 없는 맥락(이 신호가 후행적일 수 있다는 점, 투자 자문이 아니라는 점)을
# 외부 소비자도 함께 받도록 한다.

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from srm.config import Config
from srm.report.synthesize import CYCLE_LIMITATION


def build_export_payload(
    flow_table: pd.DataFrame,
    risk: dict,
    cfg: Config,
    interval: str,
    generated_at: str,
    cycle: dict | None = None,
) -> dict:
    """랭킹표 + 국면/점수/면책 메타를 하나의 dict로 묶는다(JSON 내보내기용).

    cycle(경기 사이클 위치)은 없으면 null로 내보낸다. 있으면 선행지표의
    발표지연/개정 한계 문구(note)를 함께 담는다.
    """
    return {
        "generated_at": generated_at,
        "interval": interval,
        "benchmark": cfg.benchmark,
        "regime": risk["regime"],
        "score": risk["score"],
        "max_score": risk["max"],
        "details": risk["details"],
        "cycle": None if cycle is None else {**cycle, "note": CYCLE_LIMITATION},
        "ranking": flow_table.to_dict("records"),
        "disclaimer": cfg.disclaimer.strip(),
    }


def export_json(payload: dict, outfile: str | Path) -> Path:
    """payload를 보기 좋은 JSON 파일로 저장하고 경로를 반환한다."""
    path = Path(outfile)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def export_csv(flow_table: pd.DataFrame, outfile: str | Path) -> Path:
    """랭킹표를 CSV 파일로 저장하고 경로를 반환한다."""
    path = Path(outfile)
    flow_table.to_csv(path, index=False)
    return path
