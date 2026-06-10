# report/plot.py 단위테스트 — 합성 데이터, 차트는 tmp_path에 저장 후 존재만 확인.

import pandas as pd

from srm.report.plot import plot_rrg
from srm.signals.rrg import compute_rrg


def test_plot_rrg_creates_file(tmp_path, price_panel: pd.DataFrame):
    rrg = compute_rrg(price_panel, "BENCH", ["STRONG", "WEAK"])

    outfile = tmp_path / "out.png"
    plot_rrg(rrg, outfile=str(outfile))

    assert outfile.exists()


def test_plot_rrg_with_custom_quadrant_colors(tmp_path, price_panel: pd.DataFrame):
    rrg = compute_rrg(price_panel, "BENCH", ["STRONG", "WEAK"])

    outfile = tmp_path / "out_custom.png"
    plot_rrg(rrg, outfile=str(outfile), quadrant_colors={"Leading": "#000000"})

    assert outfile.exists()
