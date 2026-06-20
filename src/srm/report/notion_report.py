# 노션 전용 보고서 렌더 (M6) — Notion-flavored Markdown 문자열을 만든다.
#
# markdown_report(.md/GFM)와 같은 데이터·결론을 쓰되, 노션이 보장하는 블록 문법으로 낸다:
#   - 표는 GFM 파이프표가 아니라 <table header-row="true">.
#   - 핵심 결론/면책은 <callout>, 용어 부록은 <details> 토글.
#   - RRG 차트는 GitHub raw URL(cfg.report_chart_raw_base)로 ![]() 임베드.
# 내용 분기는 report/insight.py 헬퍼를 재사용해 .md 보고서와 일치시킨다.
#
# 스펙 원칙 유지: 상태 서술만(미래 단정 금지), 면책문구는 cfg.disclaimer에서, 흐름
# 데이터는 후행적일 수 있음을 명시. 데이터 부족 시 예외 없이 안내문으로 degrade.

from __future__ import annotations

from typing import Mapping, Sequence

import pandas as pd

from srm.config import Config
from srm.report.backtest_report import GATE_RULE_DESC, _fmt_rate
from srm.report.insight import (
    QUADRANT_KO,
    flow_bar,
    read_guide,
    sector_desc_full,
    sector_label,
    weekly_conclusion,
)
from srm.report.synthesize import (
    CYCLE_BORDERLINE_Z,
    CYCLE_LIMITATION,
    PHASE_KO,
    QUADRANT_DESC,
)

# 노션 마크다운에서 이스케이프가 필요한 문자(스펙 명시). 표 셀의 동적 텍스트에만 적용한다.
_ESC_CHARS = "\\`*_~<>[]^{}|$"


def _esc(value: object) -> str:
    """표 셀의 평문 텍스트를 노션 인라인 문법과 충돌하지 않게 이스케이프한다."""
    s = str(value)
    for ch in _ESC_CHARS:  # 역슬래시가 _ESC_CHARS 맨 앞이라 먼저 처리된다.
        s = s.replace(ch, "\\" + ch)
    return s


def _ntable(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """Notion-flavored <table>. 첫 행을 헤더로 둔다(header-row=true)."""
    out = ['<table header-row="true">']
    out.append("\t<tr>" + "".join(f"<td>{_esc(h)}</td>" for h in headers) + "</tr>")
    for row in rows:
        out.append("\t<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in row) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def _callout(body_lines: Sequence[str], icon: str = "💡", color: str | None = None) -> list[str]:
    """callout 블록. 본문은 노션 마크다운(이미 포맷된 줄)을 그대로 들여쓴다."""
    attr = f' icon="{icon}"' + (f' color="{color}"' if color else "")
    return [f"<callout{attr}>", *[f"\t{line}" for line in body_lines], "</callout>"]


def render_notion_report(
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
    """종합 결과를 노션 페이지 본문(Notion-flavored Markdown)으로 렌더한다.

    인자 스키마는 render_markdown_report와 동일하다(같은 호출부에서 재사용 가능).
    """
    disc = cfg.disclaimer.strip()

    if prices.empty:
        return "\n".join(
            _callout(
                [
                    "가격 데이터를 불러오지 못해 보고서를 생성하지 못했습니다 "
                    "(전 티커 다운로드 실패 또는 빈 데이터)."
                ],
                icon="⚠️",
                color="red_bg",
            )
            + ["", "---", *_callout([disc], icon="⚖️")]
        )

    last_date = prices.index[-1].date()
    out: list[str] = _callout(
        [
            f"기준 **{interval}봉** · 벤치마크 **{cfg.benchmark}** · 데이터 마지막 **{last_date}**",
            "이 보고서의 모든 신호는 '현재 상태 확인'이며 미래 방향을 **단정하지 않습니다**. "
            "흐름/순환 데이터는 후행적일 수 있습니다.",
        ],
        icon="📅",
        color="blue_bg",
    )
    out += [""]

    if flow_table.empty:
        out += _callout(
            ["RRG 계산에 필요한 데이터가 부족해 보고서를 생성하지 못했습니다."],
            icon="⚠️",
            color="red_bg",
        )
        out += ["", "---", *_callout([disc], icon="⚖️")]
        return "\n".join(out)

    # [0] 이번 주 결론
    concl = weekly_conclusion(flow_table, risk, cfg)
    out += ["## 0. 이번 주 결론", ""]
    out += _callout([concl["one_liner"], "", f"_{concl['caveat']}_"], icon="🧭", color="gray_bg")
    out += ["", "### 읽는 법", ""]
    out += [f"- {line}" for line in read_guide()]
    out += [""]

    # [1] 시장 국면
    out += [
        "## 1. 시장 국면 — 위험선호 vs 안전선호",
        "",
        f"**{concl['regime_ko']}**  ·  점수 **{risk['score']:+d} / {risk['max']}**",
        "",
        "- 🟢 RISK-ON = 위험자산이 안전자산 대비 상대적 강세 우세",
        "- 🔴 RISK-OFF = 안전자산 선호 우세 · 🟡 MIXED = 혼조/전환 가능 구간",
        "",
        _ntable(["페어", "상태"], list(risk["details"].items())),
        "",
    ]

    # [2] 섹터 자금흐름 랭킹
    out += [
        "## 2. 섹터 자금흐름 랭킹",
        "",
        "_위로 갈수록 여러 신호가 자금 '유입' 쪽으로 합의(FlowScore 내림차순). "
        "막대 🟩=유입 / 🟥=유출 우세._",
        "",
        _ranking_ntable(flow_table, cfg),
        "",
    ]

    # [3] 핵심 요약
    out += ["## 3. 핵심 요약", ""]
    out += _summary_lines(flow_table, cfg)
    out += [""]

    # [4] RRG 차트 — repo가 PUBLIC이면 raw URL로 실제 이미지를 임베드한다.
    out += ["## 4. RRG 4분면 차트", ""]
    if chart_name and cfg.report_chart_raw_base:
        url = f"{cfg.report_chart_raw_base.rstrip('/')}/{chart_name}"
        out += [
            f"![Relative Rotation Graph]({url})",
            "",
            "_세로축=RS-Momentum(상대강도 변화 방향), 가로축=RS-Ratio(상대강도 수준, 100=벤치마크)._",
            "",
        ]
    else:
        out += _callout(
            [
                "RRG 차트 이미지를 임베드할 수 없어 이 섹션을 생략합니다 "
                "(차트 미생성 또는 chart_raw_base 미설정)."
            ],
            icon="📈",
            color="gray_bg",
        )
        out += [""]

    # [5] 거시 참고
    out += _macro_section(prices, cfg)

    # [6] 경기 사이클
    out += ["## 6. 경기 사이클 위치 (선행지표 합의, 참고용 맥락)", ""]
    out += _cycle_section(cycle, cfg)

    # [7] 신호 안정성(백테스트)
    out += ["## 7. 신호 안정성 — 휩소(가짜신호) 점검", ""]
    out += _backtest_section(backtest, cfg)

    # [부록] 용어 — 토글
    out += _glossary_section(flow_table, cfg)

    out += ["", "---", *_callout([disc], icon="⚖️")]
    return "\n".join(out)


def _ranking_ntable(flow_table: pd.DataFrame, cfg: Config) -> str:
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
    return _ntable(headers, rows)


def _summary_lines(flow_table: pd.DataFrame, cfg: Config) -> list[str]:
    lines: list[str] = []
    any_quad = False
    for label, q in [
        ("🟦 유입 시작(Improving)", "Improving"),
        ("🟩 주도 중(Leading)", "Leading"),
        ("🟨 유출 경고(Weakening)", "Weakening"),
    ]:
        sub = flow_table[flow_table["Quadrant"] == q]
        if not sub.empty:
            any_quad = True
            names = ", ".join(sector_label(r.Ticker, cfg) for r in sub.itertuples())
            lines.append(f"- **{label}**: {names}")
    if not any_quad:
        lines.append("- 해당 분면에 속한 섹터가 없습니다.")
    return lines


def _macro_section(prices: pd.DataFrame, cfg: Config) -> list[str]:
    look = cfg.macro_lookback
    out = [
        "## 5. 거시 참고 (후행 지표)",
        "",
        f"_{look - 1}봉 전 대비 변화. 후행 지표이므로 맥락 참고용입니다._",
        "",
    ]
    rows = []
    for tkr, label in cfg.macro.items():
        if tkr in prices.columns:
            s = prices[tkr].dropna()
            if len(s) > look + 1:
                pct = (s.iloc[-1] / s.iloc[-look] - 1) * 100
                rows.append((f"{label} ({tkr})", f"{pct:+.2f}%"))
    out += [_ntable(["지표", "변화"], rows) if rows else "_표시할 거시 지표가 없습니다._", ""]
    return out


def _cycle_section(cycle: Mapping | None, cfg: Config) -> list[str]:
    if cycle is None:
        return _callout(
            [
                "FRED 설정/`FRED_API_KEY` 미설정 또는 다운로드 실패로 사이클 분석을 생략합니다.",
                "(FRED API 키는 fred.stlouisfed.org에서 무료 발급 가능)",
            ],
            icon="🧊",
            color="gray_bg",
        ) + [""]
    phase = cycle["phase"]
    lines: list[str] = []
    if phase in PHASE_KO:
        label = f"{phase} ({PHASE_KO[phase]})"
        borderline = (
            " ⚠️ (경계 근처 — 판정이 바뀌기 쉬움)"
            if abs(cycle["level_score"]) < CYCLE_BORDERLINE_Z
            else ""
        )
        lines.append(f"**{label}**{borderline} — {cycle['description']}")
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
        lines += [_ntable(["선행지표", "상태"], rows), ""]
    sectors = cfg.phase_sectors.get(phase)
    if sectors:
        names = ", ".join(sector_label(t, cfg) for t in sectors)
        lines.append(f"- 이 국면과 역사적으로 정합적이라 알려진 섹터군(참고, 추천 아님): {names}")
        lines.append("")
    lines += _callout([f"⚠️ {CYCLE_LIMITATION}"], icon="⚠️", color="yellow_bg") + [""]
    return lines


def _entry(e: Mapping) -> str:
    return f"전환 {e['transitions']}건 / 휩소 {e['whipsaws']}건 / 휩소율 {_fmt_rate(e['rate'])}"


def _backtest_section(backtest: Mapping | None, cfg: Config) -> list[str]:
    if backtest is None:
        return _callout(
            ["데이터(이력)가 부족해 신호 안정성 측정을 생략합니다 (`--period`를 늘려 보세요)."],
            icon="📉",
            color="gray_bg",
        ) + [""]
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
            (sector_label(t, cfg), e["transitions"], e["whipsaws"], _fmt_rate(e["rate"]))
            for t, e in per_ticker.items()
        ]
        rows.append(
            (
                "전체",
                whipsaw["total"]["transitions"],
                whipsaw["total"]["whipsaws"],
                _fmt_rate(whipsaw["total"]["rate"]),
            )
        )
        lines += [_ntable(["섹터", "전환", "휩소", "휩소율"], rows), ""]
    else:
        lines += ["_데이터 부족으로 생략._", ""]

    lines += ["### 7-2. 추세 게이트 후보 비교 (FlowScore '부호'의 안정성)", ""]
    if gate_cmp:
        rows = [
            (rule, _entry(res["total"]), GATE_RULE_DESC.get(rule, rule))
            for rule, res in gate_cmp.items()
        ]
        lines += [_ntable(["규칙", "안정성", "설명"], rows), ""]
        lines += _callout(
            [
                "Improving 분면은 어떤 규칙에서도 강등하지 않습니다(이른 신호라 추세가 아직 약한 게 정상)."
            ],
            icon="ℹ️",
        ) + [""]
    else:
        lines += ["_데이터 부족으로 생략._", ""]

    lines += [f"### 7-3. RRG 윈도우 후보별 안정성 (현행 rs/mom = {cfg.rs_window})", ""]
    if sweep is not None and not sweep.empty:
        rows = []
        for row in sweep.itertuples():
            rate = None if pd.isna(row.rate) else row.rate
            mark = " (현행)" if row.window == cfg.rs_window else ""
            rows.append((f"{row.window}{mark}", row.transitions, row.whipsaws, _fmt_rate(rate)))
        lines += [_ntable(["window", "전환", "휩소", "휩소율"], rows), ""]
        lines += ["_윈도우가 길수록 신호가 느리고 안정적, 짧을수록 빠르고 번복이 잦은 경향._", ""]
    else:
        lines += ["_데이터 부족으로 생략._", ""]
    return lines


def _glossary_section(flow_table: pd.DataFrame, cfg: Config) -> list[str]:
    lines = [
        "<details>",
        "<summary>부록: 용어·섹터 설명 (펼치기)</summary>",
        "",
        "모든 신호는 '현재 상태 확인'이며, 미래 방향을 단정하지 않습니다. "
        "흐름/순환 데이터는 후행적일 수 있습니다.",
        "",
        "**RRG 4분면** — RS-Ratio(상대강도 수준) × RS-Momentum(상대강도 변화 방향)",
        "",
    ]
    quad_rows = [(q, QUADRANT_KO[q], QUADRANT_DESC[q]) for q in QUADRANT_KO]
    lines += [_ntable(["분면", "한글", "의미"], quad_rows), ""]
    terms = [
        ("RS-Ratio", "벤치마크 대비 상대강도 '수준' (100 = 벤치마크와 같은 수준)"),
        ("RS-Mom", "RS-Ratio의 '변화 방향/세기' (100 = 변화 없음)"),
        ("Rot(회전)", "RS-Mom의 직전 대비 변화 방향 (U=상승/D=하락/-=변화없음)"),
        ("Trend", "가격이 단/장기 이동평균 위/아래로 정렬됐는지(1차 추세, 안전장치)"),
        ("FlowScore", "4분면+회전+추세 합산 종합 점수 (높을수록 유입 쪽 합의, 범위 −3.5~+3.5)"),
    ]
    lines += [_ntable(["용어", "뜻"], terms), ""]
    # 이번 보고서에 등장한 섹터 풀이만 곁들인다.
    sec_rows = [(sector_label(t, cfg), sector_desc_full(t, cfg)) for t in flow_table["Ticker"]]
    lines += ["**섹터 풀이**", "", _ntable(["섹터", "설명"], sec_rows), "", "</details>", ""]
    return lines
