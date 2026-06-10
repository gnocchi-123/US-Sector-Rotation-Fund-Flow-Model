# Layer 1 (RRG) 단위테스트 — 합성 데이터, 네트워크 없음.
#
# 주의: 노이즈 없는 합성 데이터에서는 RS-Momentum이 100 근처에 머물러 Leading/Weakening
# 경계가 칼날 위에 선다. compute_rrg 테스트는 모멘텀/분면을 단언하지 말고 RS-Ratio
# 부호(좌/우 반면)만 단언한다 (ROADMAP.md M1 구현 주의 참고).

import pandas as pd

from srm.signals.rrg import classify_quadrant, compute_rrg


def test_classify_quadrant_boundaries():
    assert classify_quadrant(100, 100) == "Leading"
    assert classify_quadrant(100, 99.99) == "Weakening"
    assert classify_quadrant(99.99, 99.99) == "Lagging"
    assert classify_quadrant(99.99, 100) == "Improving"


def test_compute_rrg_rs_ratio_sign(price_panel: pd.DataFrame):
    rrg = compute_rrg(price_panel, "BENCH", ["STRONG", "WEAK", "NOPE"])

    # 존재하지 않는 티커는 결과에서 제외된다.
    assert "NOPE" not in rrg.index
    assert set(rrg.index) == {"STRONG", "WEAK"}

    # BENCH 대비 꾸준히 강세/약세인 티커는 RS-Ratio의 100 기준 좌/우가 갈린다.
    assert rrg.loc["STRONG", "rs_ratio"] >= 100
    assert rrg.loc["WEAK", "rs_ratio"] < 100

    # 차트 렌더용 시계열도 함께 반환된다.
    assert "_ratio_series" in rrg.columns
    assert "_mom_series" in rrg.columns


def test_compute_rrg_returns_empty_when_no_members(price_panel: pd.DataFrame):
    rrg = compute_rrg(price_panel, "BENCH", ["NOPE1", "NOPE2"])
    assert rrg.empty
