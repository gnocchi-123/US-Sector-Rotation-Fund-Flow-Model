# 엔트리포인트 (argparse).
#
# 흐름: config 로드 -> 가격 데이터 수집(data/loader) -> 종합 점수/리포트(report/synthesize)
# -> (옵션) RRG 차트(report/plot). 다운로드 실패 등은 예외로 죽지 않고 메시지 출력 후 종료한다.

from __future__ import annotations

import argparse
import sys

from srm.config import Config, load_config
from srm.data.cache import load_cached_prices, save_prices
from srm.data.loader import fetch_prices
from srm.report.plot import plot_rrg
from srm.report.synthesize import compute_flow_table, render_report
from srm.signals.risk import compute_risk_appetite
from srm.signals.rrg import compute_rrg


def collect_tickers(cfg: Config) -> list[str]:
    """리포트 계산에 필요한 모든 티커(벤치마크/섹터/위험선호 페어/거시) 목록."""
    tickers = {cfg.benchmark}
    tickers.update(cfg.sectors)
    for num, den in cfg.risk_pairs.values():
        tickers.add(num)
        tickers.add(den)
    tickers.update(cfg.macro)
    return sorted(tickers)


def main() -> None:
    ap = argparse.ArgumentParser(description="섹터 자금흐름 판단 모델")
    cfg = load_config()
    ap.add_argument("--period", default=cfg.data_period)
    ap.add_argument("--interval", default=cfg.data_interval)
    ap.add_argument("--plot", action="store_true", help="RRG 차트를 저장한다")
    ap.add_argument("--tail", type=int, default=8, help="RRG 차트에 표시할 최근 봉 수")
    ap.add_argument("--no-cache", action="store_true", help="가격 캐시를 읽거나 쓰지 않는다")
    ap.add_argument(
        "--refresh", action="store_true", help="캐시를 무시하고 가격 데이터를 새로 받는다"
    )
    args = ap.parse_args()

    tickers = collect_tickers(cfg)

    prices = None
    if not args.no_cache and not args.refresh:
        prices = load_cached_prices(tickers, args.period, args.interval)
        if prices is not None:
            print("[캐시] 저장된 가격 데이터 사용")

    if prices is None:
        print("데이터 다운로드 중...")
        try:
            prices = fetch_prices(tickers, args.period, args.interval)
        except Exception as e:
            print(f"다운로드 실패: {e}")
            sys.exit(1)
        if not args.no_cache:
            save_prices(prices, tickers, args.period, args.interval)

    flow_table = compute_flow_table(prices, cfg)
    risk = compute_risk_appetite(prices, cfg.risk_pairs, cfg.risk_ma, cfg.risk_on, cfg.risk_off)
    print(render_report(flow_table, risk, prices, cfg, args.interval))

    if args.plot and not flow_table.empty:
        rrg = compute_rrg(prices, cfg.benchmark, list(cfg.sectors), cfg.rs_window, cfg.mom_window)
        plot_rrg(rrg, tail=args.tail)


if __name__ == "__main__":
    main()
