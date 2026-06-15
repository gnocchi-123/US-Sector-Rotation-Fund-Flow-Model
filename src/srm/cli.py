# 엔트리포인트 (argparse).
#
# 흐름: config 로드 -> 가격 데이터 수집(data/loader) -> 종합 점수/리포트(report/synthesize)
# -> (옵션) RRG 차트(report/plot). 다운로드 실패 등은 예외로 죽지 않고 메시지 출력 후 종료한다.

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from srm.backtest.sweep import sweep_windows
from srm.backtest.walk import quadrant_history, trend_history
from srm.backtest.whipsaw import GATE_RULES, score_sign_stability, whipsaw_rate
from srm.config import Config, load_config
from srm.data.cache import load_cached_prices, prune_cache, save_prices
from srm.data.fred import drop_stale_series, fetch_dbnomics_series, fetch_fred_series
from srm.data.loader import fetch_prices
from srm.data.snapshot import load_snapshot, load_snapshot_frame, prune_snapshots, save_snapshot
from srm.report.backtest_report import render_backtest_report
from srm.report.export import build_export_payload, export_csv, export_json
from srm.report.markdown_report import render_markdown_report
from srm.report.plot import plot_rrg
from srm.report.synthesize import compute_flow_table, render_report
from srm.signals.cycle import compute_cycle_position
from srm.signals.risk import compute_risk_appetite
from srm.signals.rrg import compute_rrg

FRED_CACHE_DIR = ".cache/fred"


def load_dotenv(path: str = ".env") -> None:
    """`.env` 파일이 있으면 환경변수로 주입한다 (FRED_API_KEY 등 로컬 비밀값용).

    이미 설정된 환경변수는 덮어쓰지 않는다. 파일이 없으면 조용히 넘어간다.
    `.env`는 .gitignore에 포함되어 있어 키가 레포에 커밋되지 않는다.
    """
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))
    except OSError:
        pass


def collect_tickers(cfg: Config) -> list[str]:
    """리포트 계산에 필요한 모든 티커(벤치마크/섹터/위험선호 페어/거시) 목록.

    FRED/DBnomics 선행지표는 yfinance 티커가 아니므로 여기 포함하지 않는다.
    """
    tickers = {cfg.benchmark}
    tickers.update(cfg.sectors)
    for num, den in cfg.risk_pairs.values():
        tickers.add(num)
        tickers.add(den)
    tickers.update(cfg.macro)
    return sorted(tickers)


def _load_indicators(cfg: Config, args: argparse.Namespace) -> pd.DataFrame:
    """선행지표 패널 로드: 캐시 → FRED(키 필요) + DBnomics(키 불필요) 다운로드.

    어떤 실패도 예외로 전파하지 않는다 — 빈 DataFrame이면 사이클 섹션만 생략된다.
    """
    ids = sorted(set(cfg.fred_series) | set(cfg.fred_dbnomics))
    period = f"{cfg.fred_period_years}y"

    if not args.no_cache and not args.refresh:
        cached = load_cached_prices(ids, period, "fred", cache_dir=FRED_CACHE_DIR)
        if cached is not None:
            print("[캐시] 저장된 선행지표 데이터 사용")
            return cached

    fred_df = fetch_fred_series(cfg.fred_series, cfg.fred_period_years)
    db_df = fetch_dbnomics_series(cfg.fred_dbnomics)
    indicators = pd.concat([fred_df, db_df], axis=1)
    if not args.no_cache and not indicators.empty:
        save_prices(indicators, ids, period, "fred", cache_dir=FRED_CACHE_DIR)
        removed = prune_cache(FRED_CACHE_DIR, keep_days=cfg.cache_keep_days)
        if removed:
            print(f"[정리] 오래된 선행지표 캐시 {len(removed)}개 삭제")
    return indicators


def _compute_cycle(cfg: Config, indicators: pd.DataFrame | None) -> dict | None:
    """선행지표 → 사이클 위치. 데이터가 없거나 처리에 실패하면 None(안전 degrade)."""
    if indicators is None or indicators.empty:
        return None
    try:
        kept, stale = drop_stale_series(indicators, cfg.fred_stale_months)
        if stale:
            print(f"[사이클] 갱신 정체로 판정에서 제외된 지표: {', '.join(stale)}")
        meta = {**cfg.fred_series, **cfg.fred_dbnomics}
        return compute_cycle_position(
            kept,
            meta,
            trend_window=cfg.cycle_trend_window,
            level_window=cfg.cycle_level_window,
            min_indicators=cfg.cycle_min_indicators,
        )
    except Exception as e:
        print(f"[사이클] 선행지표 처리 실패, 사이클 섹션 생략: {e}")
        return None


def _compute_backtest(prices: pd.DataFrame, cfg: Config) -> dict | None:
    """신호 안정성(휩소) 백테스트 계산만 수행 (M4). 이력 부족 시 None(degrade).

    수익률 백테스트가 아니라 신호 상태 변화만 기록한다. 콘솔(`--backtest`)과
    Markdown 보고서(`--report-md`)가 같은 결과를 공유해 이중 계산을 피한다.
    """
    if len(prices) < cfg.backtest_min_history:
        return None
    members = list(cfg.sectors)
    quad_hist = quadrant_history(prices, cfg.benchmark, members, cfg.rs_window, cfg.mom_window)
    trend_hists = {t: trend_history(prices, t, cfg.trend_fast, cfg.trend_slow) for t in members}
    weights = {"quad_flow": cfg.quad_flow, "trend": cfg.trend}
    return {
        "whipsaw": whipsaw_rate(quad_hist, cfg.backtest_horizon),
        "gate_cmp": {
            rule: score_sign_stability(quad_hist, trend_hists, weights, cfg.backtest_horizon, rule)
            for rule in GATE_RULES
        },
        "sweep": sweep_windows(
            prices, cfg.benchmark, members, cfg.backtest_window_candidates, cfg.backtest_horizon
        ),
    }


def _run_backtest(prices: pd.DataFrame, cfg: Config) -> None:
    """신호 안정성(휩소) 리포트 계산 + 콘솔 출력 (M4).

    호출부의 try/except와 _compute_backtest의 min_history 가드로, 어떤 실패도
    본 리포트를 막지 않는다.
    """
    bt = _compute_backtest(prices, cfg)
    if bt is None:
        print(
            f"[백테스트] 데이터 {len(prices)}봉 < 최소 {cfg.backtest_min_history}봉 — "
            "신호 안정성 리포트를 생략합니다 (--period를 늘려 보세요)."
        )
        return
    print()
    print(render_backtest_report(bt["whipsaw"], bt["gate_cmp"], bt["sweep"], cfg))


def _resolve_report_path(arg: str, cfg: Config, last_date) -> Path:
    """--report-md 경로 결정. 빈 문자열이면 기본 경로(날짜별 자기완결)."""
    if arg:
        return Path(arg)
    return Path(cfg.report_output_dir) / f"flow-report-{last_date}.md"


def _write_markdown_report(
    md_path: Path,
    prices: pd.DataFrame,
    cfg: Config,
    interval: str,
    rrg: pd.DataFrame,
    flow_table: pd.DataFrame,
    risk: dict,
    cycle: dict | None,
) -> None:
    """RRG 차트(동명 PNG) + 백테스트 + Markdown 보고서를 한 번에 생성한다 (M5).

    차트/백테스트의 부분 실패는 해당 섹션만 degrade시키고 본 보고서를 막지 않는다.
    md의 이미지 링크는 같은 디렉터리 상대경로(파일명만)라 어디서 열어도 해석된다.
    """
    md_path.parent.mkdir(parents=True, exist_ok=True)

    chart_name: str | None = None
    if not flow_table.empty:
        try:
            png_path = md_path.with_suffix(".png")
            plot_rrg(rrg, outfile=str(png_path))
            chart_name = png_path.name
        except Exception as e:  # 차트 실패가 보고서를 막지 않음
            print(f"[보고서] 차트 생성 실패, 차트 섹션 생략: {e}")

    try:
        backtest = _compute_backtest(prices, cfg)
    except Exception as e:
        print(f"[보고서] 백테스트 처리 실패, 안정성 섹션 생략: {e}")
        backtest = None

    md = render_markdown_report(
        flow_table,
        risk,
        prices,
        cfg,
        interval,
        cycle=cycle,
        backtest=backtest,
        chart_name=chart_name,
    )
    md_path.write_text(md, encoding="utf-8")
    print(f"[보고서] {md_path}")


def main() -> None:
    load_dotenv()
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
    ap.add_argument(
        "--from-snapshot", help="저장된 스냅샷 디렉터리의 가격 데이터로 리포트를 재현한다"
    )
    ap.add_argument(
        "--no-snapshot",
        action="store_true",
        help="이번 실행에 사용한 가격 데이터를 저장하지 않는다",
    )
    ap.add_argument(
        "--export",
        action="append",
        choices=["json", "csv"],
        help="섹터 자금흐름 랭킹을 파일로 내보낸다(반복 지정 가능)",
    )
    ap.add_argument(
        "--backtest",
        action="store_true",
        help="신호 안정성(휩소) 리포트를 함께 출력한다 (수익률 백테스트 아님)",
    )
    ap.add_argument(
        "--report-md",
        nargs="?",
        const="",
        default=None,
        metavar="PATH",
        help="콘솔 리포트 전체+RRG 차트+백테스트+용어 부록을 단일 Markdown 보고서로 저장한다"
        " (경로 생략 시 report.output_dir/flow-report-<날짜>.md)",
    )
    args = ap.parse_args()

    tickers = collect_tickers(cfg)

    if args.from_snapshot:
        prices, meta = load_snapshot(args.from_snapshot)
        print(f"[스냅샷] {args.from_snapshot} 사용 (저장 시각 {meta.get('timestamp', '?')})")
        # 스냅샷에 선행지표가 함께 저장돼 있으면 사이클 섹션까지 재현된다.
        indicators = load_snapshot_frame(args.from_snapshot, "indicators")
    else:
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
                removed = prune_cache(keep_days=cfg.cache_keep_days)
                if removed:
                    print(f"[정리] 오래된 가격 캐시 {len(removed)}개 삭제")

        indicators = None
        if cfg.fred_series or cfg.fred_dbnomics:
            indicators = _load_indicators(cfg, args)

        if not args.no_snapshot:
            extra = (
                {"indicators": indicators}
                if indicators is not None and not indicators.empty
                else None
            )
            save_snapshot(
                prices,
                {"period": args.period, "interval": args.interval, "tickers": tickers},
                extra_frames=extra,
            )
            removed = prune_snapshots(keep=cfg.snapshot_keep)
            if removed:
                print(
                    f"[정리] 오래된 스냅샷 {len(removed)}개 삭제 (최신 {cfg.snapshot_keep}개 보관)"
                )

    # 가격 데이터가 비어 있으면(전 티커 다운로드 실패 등) 이후 렌더가 빈 인덱스
    # 접근으로 죽으므로, 여기서 명확한 메시지와 함께 안전하게 종료한다(스펙: degrade).
    if prices is None or prices.empty:
        print(
            "가격 데이터를 불러오지 못했습니다 (전 티커 다운로드 실패 또는 빈 데이터). "
            "네트워크 연결/방화벽(yahoo finance 접근)을 확인하세요."
        )
        sys.exit(1)

    cycle = _compute_cycle(cfg, indicators)

    # RRG는 1회만 계산해 랭킹표와 --plot 차트가 공유한다.
    rrg = compute_rrg(prices, cfg.benchmark, list(cfg.sectors), cfg.rs_window, cfg.mom_window)
    flow_table = compute_flow_table(prices, cfg, rrg=rrg)
    risk = compute_risk_appetite(
        prices, cfg.risk_pairs, cfg.risk_ma, cfg.risk_on, cfg.risk_off, slope=cfg.risk_slope
    )
    print(render_report(flow_table, risk, prices, cfg, args.interval, cycle=cycle))

    if args.plot and not flow_table.empty:
        plot_rrg(rrg, tail=args.tail)

    if args.export:
        if flow_table.empty:
            print("내보내기 건너뜀: 랭킹표가 비어 있습니다.")
        else:
            generated_at = datetime.now(timezone.utc).isoformat()
            for fmt in args.export:
                if fmt == "json":
                    payload = build_export_payload(
                        flow_table, risk, cfg, args.interval, generated_at, cycle=cycle
                    )
                    path = export_json(payload, "flow_table.json")
                else:
                    path = export_csv(flow_table, "flow_table.csv")
                print(f"[내보내기] {path}")

    if args.backtest:
        try:
            _run_backtest(prices, cfg)
        except Exception as e:
            print(f"[백테스트] 처리 실패, 신호 안정성 리포트 생략: {e}")

    if args.report_md is not None:
        try:
            md_path = _resolve_report_path(args.report_md, cfg, prices.index[-1].date())
            _write_markdown_report(
                md_path, prices, cfg, args.interval, rrg, flow_table, risk, cycle
            )
        except Exception as e:
            print(f"[보고서] Markdown 보고서 생성 실패: {e}")


if __name__ == "__main__":
    main()
