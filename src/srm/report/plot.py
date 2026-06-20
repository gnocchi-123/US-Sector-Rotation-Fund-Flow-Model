# RRG 차트 렌더.
#
# CLAUDE.md 원칙에 따라 차트 라벨(제목 포함)은 영어로 통일하고, 4분면 의미를
# plain-language 범례로 함께 표시한다. 회전/흐름 신호는 후행적일 수 있다는 점도
# 차트 하단에 명시한다.

from __future__ import annotations

from typing import Mapping

import pandas as pd

# quadrant -> (in-chart label color, plain-language meaning for the legend)
QUADRANT_DESC: dict[str, tuple[str, str]] = {
    "Leading": ("#2ca02c", "Outperforming & still strengthening"),
    "Weakening": ("#bf9000", "Outperforming but losing momentum"),
    "Lagging": ("#d62728", "Underperforming & still weakening"),
    "Improving": ("#1f77b4", "Underperforming but momentum turning up"),
}

# quadrant -> background fill color (plot_rrg의 기본값, quadrant_colors로 덮어쓸 수 있음)
DEFAULT_QUADRANT_COLORS: dict[str, str] = {
    "Leading": "#2ca02c",
    "Weakening": "#ffbf00",
    "Lagging": "#d62728",
    "Improving": "#1f77b4",
}


def plot_rrg(
    rrg: pd.DataFrame,
    outfile: str = "rrg_chart.png",
    tail: int = 8,
    quadrant_colors: Mapping[str, str] | None = None,
) -> None:
    """Render a Relative Rotation Graph (RRG) and save it to `outfile`.

    `rrg`는 `compute_rrg()`의 반환값으로, 종목별 `_ratio_series`/`_mom_series`
    (RS-Ratio/RS-Momentum 전체 시계열)을 담고 있어야 한다.

    `quadrant_colors`로 4분면 배경색 일부/전체를 덮어쓸 수 있다(기본값=
    `DEFAULT_QUADRANT_COLORS`).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {**DEFAULT_QUADRANT_COLORS, **(quadrant_colors or {})}

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.axhline(100, color="gray", lw=0.8)
    ax.axvline(100, color="gray", lw=0.8)

    # Quadrant backgrounds: top-right=Leading, bottom-right=Weakening,
    # bottom-left=Lagging, top-left=Improving.
    ax.fill_between([100, 200], 100, 200, color=colors["Leading"], alpha=0.06)
    ax.fill_between([100, 200], 0, 100, color=colors["Weakening"], alpha=0.06)
    ax.fill_between([0, 100], 0, 100, color=colors["Lagging"], alpha=0.06)
    ax.fill_between([0, 100], 100, 200, color=colors["Improving"], alpha=0.06)

    # 그려진 모든 점(꼬리 포함)의 좌표를 모아 축 자동 줌에 쓴다. 실데이터는
    # RS-Ratio/RS-Momentum이 100 근처 좁은 영역에 뭉치는 경향이 있어, 고정 85~115
    # 축에서는 라벨이 겹쳐 판독이 어렵다. 데이터 범위에 맞춰 축을 좁혀 분산을 키운다.
    all_x: list[float] = []
    all_y: list[float] = []
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
            xytext=(5, 5),
            textcoords="offset points",
            zorder=6,
            # 점이 겹쳐도 라벨을 읽을 수 있게 옅은 흰 배경을 깐다.
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.65),
        )
        all_x.extend(r.values.tolist())
        all_y.extend(m.values.tolist())

    # 축 범위: 데이터에 맞춰 줌하되 100 기준선을 항상 포함하고, 가로/세로를 같은
    # 스팬(정사각형)으로 맞춰 4분면 대칭을 유지한다. 데이터가 없으면 기본 85~115.
    if all_x and all_y:
        xmin, xmax = min(min(all_x), 100.0), max(max(all_x), 100.0)
        ymin, ymax = min(min(all_y), 100.0), max(max(all_y), 100.0)
        cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
        half = max((xmax - xmin) / 2, (ymax - ymin) / 2) * 1.25  # 25% 여백
        half = max(half, 1.0)  # 최소 ±1 (전부 100 근처여도 납작해지지 않게)
        ax.set_xlim(cx - half, cx + half)
        ax.set_ylim(cy - half, cy + half)
    else:
        ax.set_xlim(85, 115)
        ax.set_ylim(85, 115)

    # 4분면 코너 라벨은 줌 배율과 무관하게 모서리에 고정(축 비율 좌표).
    corners = {
        "Improving": (0.02, 0.98, "left", "top"),
        "Leading": (0.98, 0.98, "right", "top"),
        "Lagging": (0.02, 0.02, "left", "bottom"),
        "Weakening": (0.98, 0.02, "right", "bottom"),
    }
    for quad, (fx, fy, ha, va) in corners.items():
        ax.text(
            fx,
            fy,
            quad,
            transform=ax.transAxes,
            color=QUADRANT_DESC[quad][0],
            fontweight="bold",
            ha=ha,
            va=va,
        )

    ax.set_xlabel("RS-Ratio (relative strength level vs benchmark, 100 = average)")
    ax.set_ylabel("RS-Momentum (direction of change in relative strength, 100 = no change)")
    ax.set_title("Relative Rotation Graph (RRG) - Sector Fund Flow")

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
