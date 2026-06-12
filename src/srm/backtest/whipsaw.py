# 휩소(빠른 신호 번복) 측정 + 추세 게이트 후보 규칙 비교 (M4).
#
# 순수함수만 둔다. 수익률/예측 성과가 아니라 '신호 일관성(안정성)'만 측정한다.
# 여기서 비교하는 게이트 규칙은 후보이며, 기본값 채택은 실측 후 결정한다(결정 3).

from __future__ import annotations

from typing import Mapping

import pandas as pd

# 추세 게이트 후보 규칙.
#   none               — 현행: 게이트 없음(단순 가중합).
#   contradiction_only — 분면과 추세가 정반대를 가리키는 '모순 조합'만 점수 0으로
#                        강등(합의 실패 → 신뢰도 0). Improving은 항상 제외 —
#                        이른 신호라 추세가 아직 Downtrend인 게 정상이다(결정 3).
GATE_RULES = ("none", "contradiction_only")

# 모순 조합: 분면 점수의 부호와 1차 추세의 방향이 정반대인 경우.
# (Improving은 아래 apply_gate에서 항상 제외하므로 여기 없음)
_CONTRADICTIONS = {
    ("Leading", "Downtrend"),
    ("Weakening", "Uptrend"),
    ("Lagging", "Uptrend"),
}


def _count_whipsaws(labels: pd.Series, horizon: int) -> tuple[int, int]:
    """라벨 시계열의 (전환 수, 휩소 수).

    휩소 = 전환 후 horizon봉(유효 관측 기준) 내에 직전 라벨로 복귀한 전환.
    결측 시점은 건너뛴다.
    """
    s = list(labels.dropna())
    n_transitions = 0
    n_whipsaws = 0
    for i in range(1, len(s)):
        if s[i] != s[i - 1]:
            n_transitions += 1
            if s[i - 1] in s[i + 1 : i + 1 + horizon]:
                n_whipsaws += 1
    return n_transitions, n_whipsaws


def _rate_entry(n_transitions: int, n_whipsaws: int) -> dict:
    # 전환 0건이면 비율을 정의할 수 없으므로 None(NaN 금지, degrade).
    rate = round(n_whipsaws / n_transitions, 4) if n_transitions else None
    return {"transitions": n_transitions, "whipsaws": n_whipsaws, "rate": rate}


def whipsaw_rate(history: pd.DataFrame, horizon: int) -> dict:
    """분면(라벨) 이력의 휩소율 — 전환이 horizon봉 내 직전 라벨로 복귀한 비율.

    반환: {"per_ticker": {tkr: {"transitions", "whipsaws", "rate"}}, "total": {...}}.
    전환이 0건인 티커/전체의 rate는 None.
    """
    per_ticker: dict[str, dict] = {}
    total_transitions = 0
    total_whipsaws = 0
    for tkr in history.columns:
        n, k = _count_whipsaws(history[tkr], horizon)
        per_ticker[tkr] = _rate_entry(n, k)
        total_transitions += n
        total_whipsaws += k
    return {
        "per_ticker": per_ticker,
        "total": _rate_entry(total_transitions, total_whipsaws),
    }


def apply_gate(quadrant: str, trend: str, score: float, rule: str = "none") -> float:
    """추세 게이트 후보 규칙을 점수에 적용한다.

    contradiction_only: 분면과 추세가 정반대(모순 조합)면 점수를 0으로 강등.
    Improving 분면은 어떤 규칙에서도 강등하지 않는다(결정 3 제약).
    """
    if rule not in GATE_RULES:
        raise ValueError(f"알 수 없는 게이트 규칙: {rule!r} (가능: {GATE_RULES})")
    if rule == "none" or quadrant == "Improving":
        return score
    if (quadrant, trend) in _CONTRADICTIONS:
        return 0.0
    return score


def score_sign_stability(
    quadrant_hist: pd.DataFrame,
    trend_hist_by_ticker: Mapping[str, pd.Series],
    weights: Mapping[str, Mapping[str, float]],
    horizon: int,
    rule: str = "none",
) -> dict:
    """시점별 FlowScore '부호'(pos/zero/neg)의 휩소율을 게이트 규칙별로 잰다.

    점수 = quad_flow[분면] + trend[추세] (게이트 규칙 적용 후 부호만 사용).
    회전(rotation) 성분은 모멘텀 시계열이 필요한 ±0.5 보조 신호라 부호 안정성
    비교에서는 제외한다. weights는 {"quad_flow": {...}, "trend": {...}} 형식
    (config.yaml weights와 동일 키).
    반환 형식은 whipsaw_rate와 동일. 분면/추세가 모두 있는 시점만 평가한다.
    """
    quad_w = weights["quad_flow"]
    trend_w = weights["trend"]
    per_ticker: dict[str, dict] = {}
    total_transitions = 0
    total_whipsaws = 0
    for tkr in quadrant_hist.columns:
        th = trend_hist_by_ticker.get(tkr)
        if th is None or th.empty:
            continue
        th = th.reindex(quadrant_hist.index)
        signs: list = []
        for q, tr in zip(quadrant_hist[tkr], th):
            if pd.isna(q) or pd.isna(tr):
                signs.append(pd.NA)
                continue
            score = apply_gate(q, tr, quad_w[q] + trend_w.get(tr, 0.0), rule)
            signs.append("pos" if score > 0 else ("neg" if score < 0 else "zero"))
        n, k = _count_whipsaws(pd.Series(signs, index=quadrant_hist.index, dtype="object"), horizon)
        per_ticker[tkr] = _rate_entry(n, k)
        total_transitions += n
        total_whipsaws += k
    return {
        "per_ticker": per_ticker,
        "total": _rate_entry(total_transitions, total_whipsaws),
    }
