# RRG 차트 렌더.
#
# CLAUDE.md 원칙에 따라 차트 라벨(제목 포함)은 영어로 통일하고, 4분면 의미를
# plain-language 범례로 함께 표시한다. 회전/흐름 신호는 후행적일 수 있다는 점도
# 차트 하단에 명시한다.

from __future__ import annotations

import pandas as pd

# quadrant -> (in-chart label color, plain-language meaning for the legend)
QUADRANT_DESC: dict[str, tuple[str, str]] = {
    "Leading": ("#2ca02c", "Outperforming & still strengthening"),
    "Weakening": ("#bf9000", "Outperforming but losing momentum"),
    "Lagging": ("#d62728", "Underperforming & still weakening"),
    "Improving": ("#1f77b4", "Underperforming but momentum turning up"),
}


def plot_rrg(rrg: pd.DataFrame, outfile: str = "rrg_chart.png", tail: int = 8) -> None:
    """Render a Relative Rotation Graph (RRG) and save it to `outfile`.

    `rrg`는 `compute_rrg()`의 반환값으로, 종목별 `_ratio_series`/`_mom_series`
    (RS-Ratio/RS-Momentum 전체 시계열)을 담고 있어야 한다.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.axhline(100, color="gray", lw=0.8)
    ax.axvline(100, color="gray", lw=0.8)

    # Quadrant backgrounds: top-right=Leading, bottom-right=Weakening,
    # bottom-left=Lagging, top-left=Improving.
    ax.fill_between([100, 200], 100, 200, color="#2ca02c", alpha=0.06)
    ax.fill_between([100, 200], 0, 100, color="#ffbf00", alpha=0.06)
    ax.fill_between([0, 100], 0, 100, color="#d62728", alpha=0.06)
    ax.fill_between([0, 100], 100, 200, color="#1f77b4", alpha=0.06)

    for tkr, row in rrg.iterrows():
        r = row["_ratio_series"].dropna().iloc[-tail:]
        m = row["_mom_series"].dropna().iloc[-tail:]
        n = min(len(r), len(m))
        if n < 1:
            continue
        r, m = r.iloc[-n:], m.iloc[-n:]
        ax.plot(r.values, m.values, "-", alpha=0.5, lw=1.2)
        ax.scatter(r.values[-1], m.values[-1], s=60, zorder=5)
        ax.annotate(
            tkr,
            (r.values[-1], m.values[-1]),
            fontsize=9,
            fontweight="bold",
            xytext=(4, 4),
            textcoords="offset points",
        )

    ax.text(110, 114, "Leading", color=QUADRANT_DESC["Leading"][0], fontweight="bold")
    ax.text(110, 86, "Weakening", color=QUADRANT_DESC["Weakening"][0], fontweight="bold")
    ax.text(86, 86, "Lagging", color=QUADRANT_DESC["Lagging"][0], fontweight="bold")
    ax.text(86, 114, "Improving", color=QUADRANT_DESC["Improving"][0], fontweight="bold")

    ax.set_xlabel("RS-Ratio (relative strength level vs benchmark, 100 = average)")
    ax.set_ylabel("RS-Momentum (direction of change in relative strength, 100 = no change)")
    ax.set_title("Relative Rotation Graph (RRG) - Sector Fund Flow")
    ax.set_xlim(85, 115)
    ax.set_ylim(85, 115)

    legend_lines = [f"{q}: {desc}" for q, (_, desc) in QUADRANT_DESC.items()]
    legend_lines.append("Note: rotation/flow signals can be lagging indicators, not predictions.")
    ax.text(
        0.5,
        -0.12,
        "\n".join(legend_lines),
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8,
    )

    fig.savefig(outfile, dpi=130, bbox_inches="tight")
    print(f"\n[Chart saved] {outfile}")
