# report/insight — 사용자 친화 표현 헬퍼 테스트 (순수함수, 네트워크 없음).
#
# FlowScore 발산 막대의 방향/세기, 주간 결론의 유입/유출 분류와 degrade,
# 섹터 한글 라벨 풀이를 단언한다. 모든 출력은 상태 서술이어야 한다(미래 단정 금지).

from __future__ import annotations

import pandas as pd
import pytest

from srm.config import load_config
from srm.report.insight import (
    flow_bar,
    read_guide,
    sector_desc_full,
    sector_label,
    sector_short,
    weekly_conclusion,
)

FORBIDDEN_PHRASES = ("오를 것", "상승할 것", "하락할 것", "보장된", "확실")


@pytest.fixture
def cfg():
    return load_config()


def test_flow_bar_positive_is_green_only():
    bar = flow_bar(3.5)
    assert "🟩" in bar and "🟥" not in bar
    assert bar.count("🟩") == 4  # half=4, 최대치면 가득 찬다


def test_flow_bar_negative_is_red_only():
    bar = flow_bar(-3.5)
    assert "🟥" in bar and "🟩" not in bar
    assert bar.count("🟥") == 4


def test_flow_bar_zero_is_neutral():
    bar = flow_bar(0.0)
    assert "🟩" not in bar and "🟥" not in bar
    assert "│" in bar  # 중앙 구분자


def test_flow_bar_magnitude_scales():
    # 작은 양수는 큰 양수보다 초록 칸이 적거나 같다.
    assert flow_bar(0.5).count("🟩") <= flow_bar(3.0).count("🟩")


def test_sector_label_uses_korean(cfg):
    # config.yaml의 sector_desc('한글명 — 설명') 머리말을 라벨로 쓴다.
    assert sector_label("XLY", cfg) == "경기소비재(XLY)"
    assert sector_short("XLK", cfg) == "기술"
    assert "—" in sector_desc_full("XLF", cfg)


def test_sector_label_degrades_without_desc(cfg):
    import dataclasses

    bare = dataclasses.replace(cfg, sector_desc={}, sectors={"ZZZ": "Mystery"})
    assert sector_label("ZZZ", bare) == "Mystery(ZZZ)"


def _flow_table(rows):
    return pd.DataFrame(rows, columns=["Ticker", "Quadrant", "FlowScore"])


def test_weekly_conclusion_classifies_inflow_outflow(cfg):
    ft = _flow_table(
        [
            ("XLY", "Improving", 2.5),
            ("XLB", "Leading", 1.5),
            ("XLK", "Weakening", -2.5),
        ]
    )
    risk = {"regime": "MIXED", "score": 1, "max": 5, "details": {}}
    c = weekly_conclusion(ft, risk, cfg)
    assert c["regime_ko"].startswith("혼조")
    inflow_labels = [name for name, _ in c["inflow"]]
    outflow_labels = [name for name, _ in c["outflow"]]
    assert "경기소비재(XLY)" in inflow_labels
    assert "기술(XLK)" in outflow_labels
    assert "상대" in c["caveat"]
    # one_liner는 상태 서술이어야 한다(단정 표현 금지).
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in c["one_liner"]


def test_weekly_conclusion_all_negative_degrades(cfg):
    ft = _flow_table([("XLK", "Lagging", -1.0), ("XLF", "Lagging", -2.0)])
    risk = {"regime": "RISK-OFF", "score": -3, "max": 5, "details": {}}
    c = weekly_conclusion(ft, risk, cfg)
    assert c["inflow"] == []
    assert "유입 우위 섹터 없음" in c["one_liner"]


def test_read_guide_is_non_predictive():
    text = " ".join(read_guide())
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text
    assert "상대" in text  # SPY 대비 상대 순위임을 명시
