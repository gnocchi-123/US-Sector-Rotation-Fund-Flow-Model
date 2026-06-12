# 종합 점수 계산 + 텍스트 보고서 렌더.
#
# 종합 점수 = quad_flow + rotation(부호) + trend (CLAUDE.md 결정 2).
# weights.trend_gate 토글은 config.yaml에서 읽지만, M1에서는 ON/OFF 모두 동일한
# 단순 가중합이다. ON일 때의 강등 규칙은 M4에서 휩소 실측 후 확정한다(결정 3).
# 강등 자체가 아직 없으므로 "Improving 분면은 강등하지 않는다"는 제약은 자동으로
# 만족된다.
#
# 이 모듈의 신호/점수는 모두 '현재 상태 확인'이며, 미래 방향을 단정하지 않는다.
# 흐름/순환 데이터는 후행적일 수 있다.

from __future__ import annotations

import pandas as pd

from srm.config import Config
from srm.signals.rrg import compute_rrg
from srm.signals.trend import trend_state

# 4분면별 의미 (signals/rrg.py의 classify_quadrant 표와 동일한 정의).
QUADRANT_DESC: dict[str, str] = {
    "Improving": "유입 시작(이른 신호) - 상대적으로 약세였으나 모멘텀이 전환 중",
    "Leading": "이미 주도 중 - 상대적으로 강세이고 모멘텀도 유지",
    "Weakening": "유출 경고(이른 신호) - 상대적으로 강세였으나 모멘텀이 둔화",
    "Lagging": "소외/유출 - 상대적으로 약세이고 모멘텀도 약함",
}

# 경기 사이클 국면의 한글 표기 (signals/cycle.py의 2x2 분류와 동일한 정의).
PHASE_KO: dict[str, str] = {
    "Recovery": "회복",
    "Expansion": "확장",
    "Slowdown": "둔화",
    "Contraction": "수축",
}

# 선행지표의 한계 — 사용자 대면 출력(콘솔/JSON)에 항상 함께 내보낸다.
CYCLE_LIMITATION = (
    "선행지표는 발표 지연(수일~1개월)과 사후 개정이 있어 최신 경제 상태와 "
    "다를 수 있으며, 국면 분류는 미래 예측이 아닌 참고용 맥락 정보입니다."
)


def compute_flow_score(quadrant: str, mom_delta: float, trend: str, cfg: Config) -> float:
    """종합 점수 = quad_flow + rotation(부호) + trend (결정 2).

    cfg.trend_gate는 M1에서 토글만 존재하며 ON/OFF 모두 이 단순 가중합과 동일하다.
    ON일 때의 강등 규칙은 M4 휩소 실측 후 결정한다(결정 3).
    """
    if mom_delta > 0:
        rotate = cfg.rotation["up"]
    elif mom_delta < 0:
        rotate = cfg.rotation["down"]
    else:
        rotate = cfg.rotation["flat"]
    trend_score = cfg.trend.get(trend, 0.0)
    return cfg.quad_flow[quadrant] + rotate + trend_score


def compute_flow_table(
    prices: pd.DataFrame, cfg: Config, rrg: pd.DataFrame | None = None
) -> pd.DataFrame:
    """섹터별 RRG 분면 + 추세를 종합해 FlowScore 내림차순 랭킹표를 만든다.

    `rrg`에 미리 계산한 compute_rrg 결과를 넘기면 재사용한다(차트 렌더와 공유해
    중복 계산을 피한다). RRG 계산에 필요한 데이터가 부족하면 빈 DataFrame을
    반환한다(예외 없이 degrade).
    """
    if rrg is None:
        rrg = compute_rrg(prices, cfg.benchmark, list(cfg.sectors), cfg.rs_window, cfg.mom_window)
    if rrg.empty:
        return rrg

    rows = []
    for tkr, row in rrg.iterrows():
        trend = trend_state(prices, tkr, cfg.trend_fast, cfg.trend_slow)
        score = compute_flow_score(row["quadrant"], row["mom_delta"], trend, cfg)
        rows.append(
            {
                "Sector": cfg.sectors[tkr],
                "Ticker": tkr,
                "Quadrant": row["quadrant"],
                "RS-Ratio": row["rs_ratio"],
                "RS-Mom": row["rs_momentum"],
                "Rot": "U" if row["mom_delta"] > 0 else ("D" if row["mom_delta"] < 0 else "-"),
                "Trend": trend,
                "FlowScore": round(score, 2),
            }
        )
    return pd.DataFrame(rows).sort_values("FlowScore", ascending=False).reset_index(drop=True)


def render_report(
    flow_table: pd.DataFrame,
    risk: dict,
    prices: pd.DataFrame,
    cfg: Config,
    interval: str,
    cycle: dict | None = None,
) -> str:
    """콘솔 출력용 텍스트 보고서를 만든다. 면책문구는 cfg.disclaimer에서 가져온다.

    cycle은 signals/cycle.py의 compute_cycle_position 결과(없으면 None —
    FRED 키 미설정/다운로드 실패 시 사이클 섹션만 안내문으로 degrade).
    """
    bar = "=" * 78
    lines = [
        bar,
        f" 섹터 자금흐름 판단 모델  (기준 {interval}봉, 벤치마크 {cfg.benchmark})",
        f" 데이터 마지막: {prices.index[-1].date()}",
        bar,
    ]

    if flow_table.empty:
        lines += ["", "RRG 계산 실패: 데이터 부족.", "", bar, cfg.disclaimer.strip(), bar]
        return "\n".join(lines)

    lines.append(f"\n[1] 시장 국면: {risk['regime']}  (점수 {risk['score']:+d}/{risk['max']})")
    lines.append("     ※ RISK-ON = 위험자산이 안전자산 대비 상대적 강세 우세")
    lines.append("        RISK-OFF = 안전자산 선호 우세, MIXED = 혼조/전환 가능 구간")
    for k, v in risk["details"].items():
        lines.append(f"     - {k:<14}: {v}")

    lines.append("\n[2] 섹터 자금흐름 랭킹 (위=유입 신호 우세)")
    lines.append(flow_table.to_string(index=False))

    lines.append("\n[3] 핵심 요약")
    for label, q in [
        ("유입 시작(Improving)", "Improving"),
        ("주도 중(Leading)", "Leading"),
        ("유출 경고(Weakening)", "Weakening"),
    ]:
        sub = flow_table[flow_table["Quadrant"] == q]
        if not sub.empty:
            names = ", ".join(f"{r.Sector}({r.Ticker})" for r in sub.itertuples())
            lines.append(f"  · {label}: {names}")

    lines.append("\n[4] 거시 참고 (최근 5봉 변화, 후행 지표)")
    for tkr, label in cfg.macro.items():
        if tkr in prices.columns:
            s = prices[tkr].dropna()
            if len(s) > 6:
                pct = (s.iloc[-1] / s.iloc[-5] - 1) * 100
                lines.append(f"     - {label:<10}({tkr:<6}): {pct:+.2f}%")

    lines.append("\n[5] 경기 사이클 위치 (선행지표 합의, 참고용 맥락)")
    if cycle is None:
        lines.append(
            "     데이터 없음 — fred 설정 또는 FRED_API_KEY 미설정, 혹은 다운로드 실패로"
            " 사이클 분석을 생략합니다."
        )
        lines.append("     (FRED API 키는 fred.stlouisfed.org에서 무료 발급 가능)")
    else:
        phase = cycle["phase"]
        label = f"{phase} ({PHASE_KO[phase]})" if phase in PHASE_KO else phase
        lines.append(f"     국면: {label} — {cycle['description']}")
        if phase in PHASE_KO:
            lines.append(
                f"     (지표 {cycle['counted']}개 합의: 방향 {cycle['direction_score']:+d},"
                f" 수준 z {cycle['level_score']:+.2f})"
            )
        for name, desc in cycle["details"].items():
            lines.append(f"     - {name:<28}: {desc}")
        sectors = cfg.phase_sectors.get(phase)
        if sectors:
            names = ", ".join(f"{cfg.sectors.get(t, t)}({t})" for t in sectors)
            lines.append("     · 이 국면과 역사적으로 정합적이라 알려진 섹터군(참고, 추천 아님):")
            lines.append(f"       {names}")
    lines.append(f"     ※ {CYCLE_LIMITATION}")

    lines.append("\n[6] 용어 설명")
    lines.append("     이 표의 모든 신호는 '현재 상태 확인'이며, 미래 방향을 단정하지 않습니다.")
    lines.append("     흐름/순환 데이터는 후행적일 수 있습니다.")
    lines.append("")
    lines.append("     [4분면] RS-Ratio(상대강도 수준) x RS-Momentum(상대강도 변화 방향)")
    for q in ["Improving", "Leading", "Weakening", "Lagging"]:
        lines.append(f"       - {q:<10}: {QUADRANT_DESC[q]}")
    lines.append("")
    lines.append("     [용어]")
    lines.append("       - RS-Ratio  : 벤치마크 대비 상대강도 '수준' (100 = 벤치마크와 같은 수준)")
    lines.append("       - RS-Mom    : RS-Ratio의 '변화 방향/세기' (100 = 변화 없음)")
    lines.append("       - Rot(회전) : RS-Mom의 직전 대비 변화 방향 (U=상승/D=하락/-=변화없음)")
    lines.append(
        "       - Trend     : 가격이 단/장기 이동평균 위/아래로 정렬됐는지(1차 추세, 안전장치)"
    )
    lines.append(
        "       - FlowScore : 4분면+회전+추세를 합산한 종합 점수. 높을수록 여러 신호가"
        " 자금 유입 쪽으로 합의함을 뜻함"
    )

    lines += ["", bar, cfg.disclaimer.strip(), bar]
    return "\n".join(lines)
