# Markdown 종합 보고서 렌더 (M5).
#
# 콘솔 리포트 전체(국면/랭킹/요약/거시/사이클) + RRG 차트 임베드 + 신호 안정성(백테스트)
# + 용어 부록을 가시성 좋은 단일 Markdown 문자열로 묶는다. Claude AI 루틴(예약 클라우드
# 에이전트)으로 주기 수신하는 것을 전제로, 한 번의 호출로 자기완결적 .md를 만든다.
#
# 스펙 원칙 유지: 모든 신호는 '현재 상태 확인'이며 미래를 단정하지 않는다. 흐름/순환
# 데이터는 후행적일 수 있다. 면책문구는 cfg.disclaimer에서 온다(하드코딩 금지).
#
# 상수/포맷터는 기존 모듈에서 재사용한다(중복 정의 금지):
#   - synthesize: QUADRANT_DESC / PHASE_KO / CYCLE_BORDERLINE_Z / CYCLE_LIMITATION
#   - backtest_report: GATE_RULE_DESC / _fmt_rate

from __future__ import annotations

from typing import Mapping, Sequence

import pandas as pd

from srm.config import Config
from srm.report.backtest_report import GATE_RULE_DESC, _fmt_rate
from srm.report.insight import (
    QUADRANT_KO,
    flow_bar,
    read_guide,
    sector_label,
    weekly_conclusion,
)
from srm.report.synthesize import (
    CYCLE_BORDERLINE_Z,
    CYCLE_LIMITATION,
    PHASE_KO,
    QUADRANT_DESC,
)

# 국면 한 글자 배지 — 단정이 아니라 '상태'를 한눈에 보이게 한다(이모지는 장식일 뿐).
REGIME_BADGE = {"RISK-ON": "🟢", "RISK-OFF": "🔴", "MIXED": "🟡"}
PHASE_BADGE = {"Recovery": "🌱", "Expansion": "📈", "Slowdown": "🌥️", "Contraction": "🧊"}


def _badge(text: str, table: Mapping[str, str]) -> str:
    """text의 머리말 키워드에 맞는 배지를 앞에 붙인다(없으면 그대로)."""
    for key, mark in table.items():
        if text.startswith(key):
            return f"{mark} {text}"
    return text


def _md_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """GFM 파이프 테이블 문자열. pandas.to_markdown(tabulate 의존)을 피해 직접 만든다."""
    head = "| " + " | ".join(str(h) for h in headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _frame_table(df: pd.DataFrame) -> str:
    """DataFrame을 GFM 표로. 컬럼명을 헤더로, 행을 그대로 옮긴다."""
    return _md_table(list(df.columns), df.itertuples(index=False, name=None))


def _ranking_table(flow_table: pd.DataFrame, cfg: Config) -> str:
    """섹터 랭킹표 — 한글 라벨 + 분면 한글 꼬리표 + FlowScore 발산 막대 칼럼."""
    headers = [
        "Sector",
        "Ticker",
        "Quadrant",
        "흐름",
        "FlowScore",
        "RS-Ratio",
        "RS-Mom",
        "Rot",
        "Trend",
    ]
    rows = []
    for rec in flow_table.to_dict("records"):
        quad = f"{rec['Quadrant']} ({QUADRANT_KO.get(rec['Quadrant'], '')})"
        rows.append(
            (
                sector_label(rec["Ticker"], cfg),
                rec["Ticker"],
                quad,
                flow_bar(rec["FlowScore"]),
                rec["FlowScore"],
                rec["RS-Ratio"],
                rec["RS-Mom"],
                rec["Rot"],
                rec["Trend"],
            )
        )
    return _md_table(headers, rows)


def render_markdown_report(
    flow_table: pd.DataFrame,
    risk: Mapping,
    prices: pd.DataFrame,
    cfg: Config,
    interval: str,
    *,
    cycle: Mapping | None = None,
    backtest: Mapping | None = None,
    chart_name: str | None = None,
) -> str:
    """종합 결과를 단일 Markdown 보고서 문자열로 렌더한다.

    cycle    = signals/cycle.compute_cycle_position 결과(없으면 사이클 섹션 생략 안내).
    backtest = {"whipsaw":..., "gate_cmp":..., "sweep":...}(없으면 백테스트 섹션 생략 안내).
    chart_name = md와 같은 디렉터리에 저장된 RRG PNG 파일명(없으면 차트 섹션 생략 안내).
    """
    # 가격 데이터가 비면 prices.index[-1] 접근이 죽으므로 먼저 안전 degrade한다.
    if prices.empty:
        return "\n".join(
            [
                "# 섹터 자금흐름 판단 보고서",
                "",
                "가격 데이터를 불러오지 못해 보고서를 생성하지 못했습니다 "
                "(전 티커 다운로드 실패 또는 빈 데이터).",
                "",
                "---",
                f"_{cfg.disclaimer.strip()}_",
            ]
        )

    last_date = prices.index[-1].date()
    out: list[str] = [
        f"# 섹터 자금흐름 판단 보고서 — {last_date}",
        "",
        f"> 기준 **{interval}봉** · 벤치마크 **{cfg.benchmark}** · 데이터 마지막 **{last_date}**",
        ">",
        "> 이 보고서의 모든 신호는 '현재 상태 확인'이며 미래 방향을 **단정하지 않습니다**. "
        "흐름/순환 데이터는 후행적일 수 있습니다.",
        "",
    ]

    if flow_table.empty:
        out += [
            "RRG 계산에 필요한 데이터가 부족해 보고서를 생성하지 못했습니다.",
            "",
            "---",
            f"_{cfg.disclaimer.strip()}_",
        ]
        return "\n".join(out)

    # [0] 이번 주 결론 — 표를 해석하기 전에 핵심을 한눈에(상태 서술, 단정 금지).
    concl = weekly_conclusion(flow_table, risk, cfg)
    out += [
        "## 0. 이번 주 결론",
        "",
        f"> {concl['one_liner']}",
        "",
        f"_{concl['caveat']}_",
        "",
        "### 읽는 법",
        "",
    ]
    out += [f"- {line}" for line in read_guide()]
    out += [""]

    # [1] 시장 국면
    out += [
        "## 1. 시장 국면 — 위험선호 vs 안전선호",
        "",
        f"**{_badge(risk['regime'], REGIME_BADGE)}**  ·  점수 **{risk['score']:+d} / {risk['max']}**",
        "",
        "- 🟢 RISK-ON = 위험자산이 안전자산 대비 상대적 강세 우세",
        "- 🔴 RISK-OFF = 안전자산 선호 우세 · 🟡 MIXED = 혼조/전환 가능 구간",
        "",
        _md_table(["페어", "상태"], list(risk["details"].items())),
        "",
    ]

    # [2] 섹터 자금흐름 랭킹 — 한글 라벨 + FlowScore 발산 막대로 친화적으로.
    out += [
        "## 2. 섹터 자금흐름 랭킹",
        "",
        "_위로 갈수록 여러 신호가 자금 '유입' 쪽으로 합의(FlowScore 내림차순). "
        "막대 🟩=유입 / 🟥=유출 우세._",
        "",
        _ranking_table(flow_table, cfg),
        "",
    ]

    # [3] 핵심 요약
    out += ["## 3. 핵심 요약", ""]
    summary_any = False
    for label, q in [
        ("🟦 유입 시작(Improving)", "Improving"),
        ("🟩 주도 중(Leading)", "Leading"),
        ("🟨 유출 경고(Weakening)", "Weakening"),
    ]:
        sub = flow_table[flow_table["Quadrant"] == q]
        if not sub.empty:
            summary_any = True
            names = ", ".join(sector_label(r.Ticker, cfg) for r in sub.itertuples())
            out.append(f"- **{label}**: {names}")
    if not summary_any:
        out.append("- 해당 분면에 속한 섹터가 없습니다.")
    out.append("")

    # [4] RRG 차트
    out += ["## 4. RRG 4분면 차트", ""]
    if chart_name:
        out += [
            f"![Relative Rotation Graph]({chart_name})",
            "",
            "_세로축=RS-Momentum(상대강도 변화 방향), 가로축=RS-Ratio(상대강도 수준, 100=벤치마크)._",
            "",
        ]
    else:
        out += ["_차트를 생성하지 못해 이 섹션을 생략합니다._", ""]

    # [5] 거시 참고
    look = cfg.macro_lookback
    out += [
        "## 5. 거시 참고 (후행 지표)",
        "",
        f"_{look - 1}봉 전 대비 변화. 후행 지표이므로 맥락 참고용입니다._",
        "",
    ]
    macro_rows = []
    for tkr, label in cfg.macro.items():
        if tkr in prices.columns:
            s = prices[tkr].dropna()
            if len(s) > look + 1:
                pct = (s.iloc[-1] / s.iloc[-look] - 1) * 100
                macro_rows.append((f"{label} ({tkr})", f"{pct:+.2f}%"))
    if macro_rows:
        out += [_md_table(["지표", "변화"], macro_rows), ""]
    else:
        out += ["_표시할 거시 지표가 없습니다._", ""]

    # [6] 경기 사이클
    out += ["## 6. 경기 사이클 위치 (선행지표 합의, 참고용 맥락)", ""]
    out += _cycle_section(cycle, cfg)

    # [7] 신호 안정성(백테스트)
    out += ["## 7. 신호 안정성 — 휩소(가짜신호) 점검", ""]
    out += _backtest_section(backtest, cfg)

    # [부록] 용어 설명 — 접이식으로 본문 가시성을 해치지 않는다.
    out += _glossary_section()

    out += ["", "---", f"_{cfg.disclaimer.strip()}_", ""]
    return "\n".join(out)


def _cycle_section(cycle: Mapping | None, cfg: Config) -> list[str]:
    if cycle is None:
        return [
            "_FRED 설정/`FRED_API_KEY` 미설정 또는 다운로드 실패로 사이클 분석을 생략합니다._",
            "(FRED API 키는 fred.stlouisfed.org에서 무료 발급 가능)",
            "",
        ]
    phase = cycle["phase"]
    lines: list[str] = []
    if phase in PHASE_KO:
        label = f"{phase} ({PHASE_KO[phase]})"
        badge = _badge(phase, PHASE_BADGE).split(" ", 1)[0]
        borderline = (
            " ⚠️ (경계 근처 — 판정이 바뀌기 쉬움)"
            if abs(cycle["level_score"]) < CYCLE_BORDERLINE_Z
            else ""
        )
        lines.append(f"**{badge} {label}**{borderline} — {cycle['description']}")
        lines.append("")
        lines.append(
            f"_지표 {cycle['counted']}개 합의: 방향 {cycle['direction_score']:+d}, "
            f"수준 z {cycle['level_score']:+.2f}_"
        )
    else:
        lines.append(f"**{phase}** — {cycle['description']}")
    lines.append("")
    rows = [(name, desc) for name, desc in cycle["details"].items()]
    if rows:
        lines += [_md_table(["선행지표", "상태"], rows), ""]
    sectors = cfg.phase_sectors.get(phase)
    if sectors:
        names = ", ".join(f"{cfg.sectors.get(t, t)}({t})" for t in sectors)
        lines.append(f"- 이 국면과 역사적으로 정합적이라 알려진 섹터군(참고, 추천 아님): {names}")
        lines.append("")
    lines += [f"> ⚠️ {CYCLE_LIMITATION}", ""]
    return lines


def _entry(e: Mapping) -> str:
    return f"전환 {e['transitions']}건 / 휩소 {e['whipsaws']}건 / 휩소율 {_fmt_rate(e['rate'])}"


def _backtest_section(backtest: Mapping | None, cfg: Config) -> list[str]:
    if backtest is None:
        return [
            "_데이터(이력)가 부족해 신호 안정성 측정을 생략합니다 (`--period`를 늘려 보세요)._",
            "",
        ]
    horizon = cfg.backtest_horizon
    whipsaw = backtest["whipsaw"]
    gate_cmp = backtest["gate_cmp"]
    sweep = backtest["sweep"]
    lines = [
        "_**수익률 백테스트가 아닙니다.** 신호가 바뀐 뒤 "
        f"{horizon}봉 안에 직전 상태로 번복된 비율(휩소율)만 요약합니다. 낮을수록 안정적._",
        "",
        f"### 7-1. 섹터별 RRG 분면 휩소율 (분면 전환이 {horizon}봉 내 번복된 비율)",
        "",
    ]
    per_ticker = whipsaw.get("per_ticker", {})
    if per_ticker:
        rows = [
            (
                sector_label(t, cfg),
                e["transitions"],
                e["whipsaws"],
                _fmt_rate(e["rate"]),
            )
            for t, e in per_ticker.items()
        ]
        rows.append(
            (
                "**전체**",
                whipsaw["total"]["transitions"],
                whipsaw["total"]["whipsaws"],
                _fmt_rate(whipsaw["total"]["rate"]),
            )
        )
        lines += [_md_table(["섹터", "전환", "휩소", "휩소율"], rows), ""]
    else:
        lines += ["_데이터 부족으로 생략._", ""]

    lines += ["### 7-2. 추세 게이트 후보 비교 (FlowScore '부호'의 안정성)", ""]
    if gate_cmp:
        rows = [
            (rule, _entry(res["total"]), GATE_RULE_DESC.get(rule, rule))
            for rule, res in gate_cmp.items()
        ]
        lines += [_md_table(["규칙", "안정성", "설명"], rows), ""]
        lines += [
            "> Improving 분면은 어떤 규칙에서도 강등하지 않습니다(이른 신호라 추세가 아직 약한 게 정상).",
            "",
        ]
    else:
        lines += ["_데이터 부족으로 생략._", ""]

    lines += [f"### 7-3. RRG 윈도우 후보별 안정성 (현행 rs/mom = {cfg.rs_window})", ""]
    if sweep is not None and not sweep.empty:
        rows = []
        for row in sweep.itertuples():
            rate = None if pd.isna(row.rate) else row.rate
            mark = " ← 현행" if row.window == cfg.rs_window else ""
            rows.append((f"{row.window}{mark}", row.transitions, row.whipsaws, _fmt_rate(rate)))
        lines += [_md_table(["window", "전환", "휩소", "휩소율"], rows), ""]
        lines += [
            "> 윈도우가 길수록 신호가 느리고 안정적, 짧을수록 빠르고 번복이 잦은 경향이 있습니다.",
            "",
        ]
    else:
        lines += ["_데이터 부족으로 생략._", ""]
    return lines


def _glossary_section() -> list[str]:
    lines = [
        "<details>",
        "<summary><b>부록: 용어 설명 (펼치기)</b></summary>",
        "",
        "모든 신호는 '현재 상태 확인'이며, 미래 방향을 단정하지 않습니다. "
        "흐름/순환 데이터는 후행적일 수 있습니다.",
        "",
        "**RRG 4분면** — RS-Ratio(상대강도 수준) × RS-Momentum(상대강도 변화 방향)",
        "",
    ]
    rows = [(q, QUADRANT_DESC[q]) for q in ["Improving", "Leading", "Weakening", "Lagging"]]
    lines += [_md_table(["분면", "의미"], rows), ""]
    terms = [
        ("RS-Ratio", "벤치마크 대비 상대강도 '수준' (100 = 벤치마크와 같은 수준)"),
        ("RS-Mom", "RS-Ratio의 '변화 방향/세기' (100 = 변화 없음)"),
        ("Rot(회전)", "RS-Mom의 직전 대비 변화 방향 (U=상승/D=하락/-=변화없음)"),
        ("Trend", "가격이 단/장기 이동평균 위/아래로 정렬됐는지(1차 추세, 안전장치)"),
        ("FlowScore", "4분면+회전+추세 합산 종합 점수 (높을수록 유입 쪽 합의)"),
    ]
    lines += [_md_table(["용어", "뜻"], terms), "", "</details>", ""]
    return lines
