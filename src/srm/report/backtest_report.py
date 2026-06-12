# 신호 안정성(휩소) 리포트 렌더 (M4).
#
# 수익률 백테스트가 아니다 — 과거에 신호 상태가 얼마나 자주 번복됐는지(휩소율)만
# 요약한다. 출력은 전부 '안정성' 서술이며, 수익/예측 표현을 쓰지 않는다.
# 면책문구는 cfg.disclaimer에서 온다(하드코딩 금지).

from __future__ import annotations

from typing import Mapping

import pandas as pd

from srm.config import Config

# 게이트 후보 규칙의 일반인용 설명 (backtest/whipsaw.py의 GATE_RULES와 1:1).
GATE_RULE_DESC: dict[str, str] = {
    "none": "게이트 없음 — 현행 단순 가중합",
    "contradiction_only": "분면과 추세가 정반대인 조합만 0점 강등 (Improving 제외)",
}


def _fmt_rate(rate: float | None) -> str:
    return "n/a (전환 없음)" if rate is None else f"{rate * 100:.0f}%"


def _fmt_entry(entry: Mapping) -> str:
    return (
        f"전환 {entry['transitions']:>3}건 / 휩소 {entry['whipsaws']:>3}건"
        f" / 휩소율 {_fmt_rate(entry['rate'])}"
    )


def render_backtest_report(
    whipsaw: Mapping,
    gate_cmp: Mapping[str, Mapping],
    sweep: pd.DataFrame,
    cfg: Config,
) -> str:
    """휩소율 + 게이트 후보 비교 + 윈도우 스윕을 일반인용 텍스트 표로 렌더한다.

    whipsaw  = backtest.whipsaw.whipsaw_rate 결과(분면 이력 기준),
    gate_cmp = {규칙 이름: score_sign_stability 결과},
    sweep    = backtest.sweep.sweep_windows 결과 표.
    """
    horizon = cfg.backtest_horizon
    bar = "=" * 78
    lines = [
        bar,
        " 신호 안정성(휩소) 리포트 — 수익률 백테스트가 아닙니다",
        bar,
        "",
        f" 휩소율 = 신호가 바뀐 뒤 {horizon}봉 안에 직전 상태로 번복된 비율."
        " 낮을수록 신호가 안정적이라는 뜻입니다.",
        " ※ 과거 신호 이력의 요약일 뿐, 미래 성과나 방향을 보장하지 않습니다."
        " 흐름/순환 데이터는 후행적일 수 있습니다.",
    ]

    lines.append(f"\n[1] 섹터별 RRG 분면 휩소율 (분면 전환이 {horizon}봉 내 번복된 비율)")
    per_ticker = whipsaw.get("per_ticker", {})
    if not per_ticker:
        lines.append("     데이터 부족으로 측정을 생략합니다.")
    else:
        for tkr, entry in per_ticker.items():
            name = cfg.sectors.get(tkr, tkr)
            lines.append(f"     - {name:<14}({tkr:<5}): {_fmt_entry(entry)}")
        lines.append(f"     - {'전체':<14}{'':7}: {_fmt_entry(whipsaw['total'])}")

    lines.append("\n[2] 추세 게이트 후보 비교 (종합 점수 FlowScore '부호'의 안정성)")
    if not gate_cmp:
        lines.append("     데이터 부족으로 측정을 생략합니다.")
    else:
        for rule, result in gate_cmp.items():
            desc = GATE_RULE_DESC.get(rule, rule)
            lines.append(f"     - {rule:<18}: {_fmt_entry(result['total'])}")
            lines.append(f"       ({desc})")
        lines.append(
            "     ※ Improving 분면은 어떤 규칙에서도 강등하지 않습니다"
            "(이른 신호라 추세가 아직 약한 게 정상)."
        )

    lines.append(f"\n[3] RRG 윈도우 후보별 안정성 (현행 rs/mom 윈도우 = {cfg.rs_window})")
    if sweep is None or sweep.empty:
        lines.append("     데이터 부족으로 측정을 생략합니다.")
    else:
        for row in sweep.itertuples():
            mark = " <- 현행" if row.window == cfg.rs_window else ""
            entry = {"transitions": row.transitions, "whipsaws": row.whipsaws, "rate": row.rate}
            if pd.isna(entry["rate"]):
                entry["rate"] = None
            lines.append(f"     - window {row.window:>3}: {_fmt_entry(entry)}{mark}")
        lines.append(
            "     ※ 윈도우가 길수록 신호가 느리고 안정적, 짧을수록 빠르고 번복이 잦은"
            " 경향이 있습니다(측정값으로 확인할 것)."
        )

    lines += ["", bar, cfg.disclaimer.strip(), bar]
    return "\n".join(lines)
