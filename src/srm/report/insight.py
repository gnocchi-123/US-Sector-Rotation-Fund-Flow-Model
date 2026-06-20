# 사용자 친화 표현 헬퍼 (M6) — 순수함수, 네트워크 접근 없음.
#
# .md 보고서(markdown_report)와 노션 보고서(notion_report)가 공유하는 '의미/표현' 계층.
# 두 렌더러가 같은 결론·풀이·시각 막대를 쓰도록 콘텐츠 분기를 여기 한 곳에 모은다.
#
# 스펙 원칙 유지: 모든 신호는 '현재 상태 확인'이며 미래를 단정하지 않는다(상태 서술만).
# 흐름 데이터는 후행적일 수 있다. FlowScore 이론 범위 = quad_flow(±2) + rotation(±0.5)
# + trend(±1) = −3.5 ~ +3.5.

from __future__ import annotations

from typing import Mapping

import pandas as pd

from srm.config import Config

# 위험선호 국면을 일반어로 — 단정이 아니라 '상태' 서술.
REGIME_KO: dict[str, str] = {
    "RISK-ON": "위험선호 우위 (위험자산으로 자금 유입 우세)",
    "RISK-OFF": "안전선호 우위 (방어적 자산 선호 우세)",
    "MIXED": "혼조 (국면 전환이 가능한 구간)",
}

# 4분면을 한 단어 한글 꼬리표로 — 표/결론에서 영어 분면 옆에 곁들인다.
QUADRANT_KO: dict[str, str] = {
    "Improving": "유입 시작",
    "Leading": "주도 중",
    "Weakening": "유출 경고",
    "Lagging": "소외/유출",
}

# FlowScore 이론 최대 절대값 (막대 스케일 기준). −HI ~ +HI.
FLOW_SCORE_HI = 3.5

# 발산형(diverging) 막대 문자 — GitHub Markdown·노션 양쪽에서 렌더되는 이모지.
_BAR_POS = "🟩"
_BAR_NEG = "🟥"
_BAR_EMPTY = "▫️"


def flow_bar(score: float, hi: float = FLOW_SCORE_HI, half: int = 4) -> str:
    """FlowScore를 중앙(0) 기준 좌우 발산 막대로 시각화한다.

    음수면 왼쪽으로 빨강, 양수면 오른쪽으로 초록이 중앙에서 바깥으로 찬다.
    0은 양쪽 모두 비어 중립을 나타낸다. 색은 '유입 합의 우세(초록)/유출 합의 우세(빨강)'
    상태를 보일 뿐 미래를 단정하지 않는다.
    """
    units = min(half, round(abs(score) / hi * half)) if hi else 0
    if score > 0:
        left = _BAR_EMPTY * half
        right = _BAR_POS * units + _BAR_EMPTY * (half - units)
    elif score < 0:
        left = _BAR_EMPTY * (half - units) + _BAR_NEG * units
        right = _BAR_EMPTY * half
    else:
        left = right = _BAR_EMPTY * half
    return f"{left}│{right}"


def sector_short(ticker: str, cfg: Config) -> str:
    """섹터의 짧은 한글명. config.sector_desc('한글명 — 설명')의 머리말, 없으면 영문명."""
    desc = getattr(cfg, "sector_desc", {}).get(ticker)
    if desc:
        return desc.split("—", 1)[0].strip()
    return cfg.sectors.get(ticker, ticker)


def sector_desc_full(ticker: str, cfg: Config) -> str:
    """섹터 한 줄 풀이 전체('한글명 — 설명'). 없으면 영문명으로 degrade."""
    desc = getattr(cfg, "sector_desc", {}).get(ticker)
    return desc if desc else cfg.sectors.get(ticker, ticker)


def sector_label(ticker: str, cfg: Config) -> str:
    """'경기소비재(XLY)' 식 라벨 — 표·결론에서 티커 옆에 한글명을 붙여 친화적으로."""
    return f"{sector_short(ticker, cfg)}({ticker})"


def weekly_conclusion(flow_table: pd.DataFrame, risk: Mapping, cfg: Config) -> dict:
    """'이번 주 결론'에 쓸 요약 묶음을 만든다(상태 서술, 단정 금지).

    반환: regime / regime_ko / score / max / inflow / outflow / one_liner / caveat.
    inflow·outflow는 [(라벨, FlowScore)] 리스트. 빈 flow_table은 호출 전에 걸러진다고
    가정하되, 양/음 점수가 없으면 빈 리스트로 안전 degrade한다.
    """
    regime = risk["regime"]
    regime_ko = REGIME_KO.get(regime, regime)

    inflow: list[tuple[str, float]] = []
    outflow: list[tuple[str, float]] = []
    if not flow_table.empty:
        pos = flow_table[flow_table["FlowScore"] > 0].sort_values("FlowScore", ascending=False)
        neg = flow_table[flow_table["FlowScore"] < 0].sort_values("FlowScore", ascending=True)
        inflow = [
            (sector_label(r.Ticker, cfg), float(r.FlowScore)) for r in pos.head(3).itertuples()
        ]
        outflow = [
            (sector_label(r.Ticker, cfg), float(r.FlowScore)) for r in neg.head(3).itertuples()
        ]

    inflow_txt = (
        ", ".join(name for name, _ in inflow) if inflow else "뚜렷한 상대 유입 우위 섹터 없음"
    )
    outflow_txt = (
        ", ".join(name for name, _ in outflow) if outflow else "뚜렷한 상대 유출 우위 섹터 없음"
    )
    one_liner = (
        f"시장 국면은 **{regime_ko}**. "
        f"벤치마크(SPY) 대비 **상대적 자금 유입 우위**: {inflow_txt} · "
        f"**상대적 유출 우위**: {outflow_txt}."
    )
    caveat = (
        "FlowScore는 SPY 대비 '상대 순위'입니다. 점수가 음수라도 절대 하락이 아니라 "
        "벤치마크보다 상대적으로 뒤처짐을 뜻하며, 모든 신호는 미래 예측이 아닌 현재 상태 확인입니다."
    )
    return {
        "regime": regime,
        "regime_ko": regime_ko,
        "score": risk["score"],
        "max": risk["max"],
        "inflow": inflow,
        "outflow": outflow,
        "one_liner": one_liner,
        "caveat": caveat,
    }


def read_guide() -> list[str]:
    """'읽는 법' — FlowScore의 뜻과 한계를 비전문가용 3~4줄로(상태 서술)."""
    return [
        "**FlowScore**는 RRG 4분면 + 모멘텀 회전 + 1차 추세 세 신호를 합산한 종합 점수입니다 "
        "(이론 범위 −3.5 ~ +3.5).",
        "점수가 **높을수록** 여러 신호가 '벤치마크(SPY) 대비 상대적 자금 유입' 쪽으로 합의함을, "
        "**낮을수록(음수)** 상대적 유출/소외 쪽 합의를 뜻합니다.",
        "막대(🟩 유입 / 🟥 유출)는 그 합의의 방향·세기를 한눈에 보이기 위한 것입니다.",
        "절대 수익률 예측이 아니라 SPY 대비 **상대 순위**이며, 모든 신호는 현재 상태 '확인'입니다.",
    ]
