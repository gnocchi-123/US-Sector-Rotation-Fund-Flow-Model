#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================================================================
Sector Rotation & Fund-Flow Decision Model  (섹터 순환매 / 자금 흐름 판단 모델)
프로토타입 (v1) — 정식 구현의 참고 기준. 스펙은 00_PROJECT_SPEC.md 참고.
========================================================================

3개 층:
  1) RRG 엔진      : 섹터별 RS-Ratio / RS-Momentum -> 4분면 (어디로)
  2) 위험선호 층   : 비율 페어 추세로 risk-on/off 점수화 (언제/국면)
  3) 추세 필터 층  : 가격 vs 50/200MA로 1차 추세 (안전장치)

한계: 예측기가 아니라 '확인기'. 데이터는 후행적. 투자 자문 아님.

사용법:
    pip install yfinance pandas numpy matplotlib
    python sector_rotation_model.py
    python sector_rotation_model.py --plot --interval 1wk --period 2y
========================================================================
"""

import argparse
import sys
import numpy as np
import pandas as pd

BENCHMARK = "SPY"

SECTORS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care",
    "XLY": "Cons. Disc.", "XLP": "Cons. Staples", "XLE": "Energy",
    "XLI": "Industrials", "XLB": "Materials", "XLU": "Utilities",
    "XLRE": "Real Estate", "XLC": "Communication",
}

RISK_PAIRS = {
    "SmallVsLarge": ("IWM", "SPY"),
    "EqualVsCap":   ("RSP", "SPY"),
    "CycVsDef":     ("XLY", "XLP"),
    "CreditRisk":   ("HYG", "LQD"),
    "GrowthVsValue":("VUG", "VTV"),
}

MACRO = {"^TNX": "10Y Yield", "USO": "Oil", "GLD": "Gold", "UUP": "Dollar", "^VIX": "VIX"}


def fetch_prices(tickers, period="2y", interval="1wk"):
    import yfinance as yf
    tickers = sorted(set(tickers))
    raw = yf.download(tickers, period=period, interval=interval,
                      auto_adjust=True, progress=False, group_by="column")
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:
        close = raw[["Close"]].copy()
        close.columns = tickers
    return close.dropna(how="all").ffill()


def _zscore_normalize(series, window):
    m = series.rolling(window, min_periods=window // 2).mean()
    s = series.rolling(window, min_periods=window // 2).std()
    return 100.0 + (series - m) / s.replace(0, np.nan)


def compute_rrg(prices, benchmark, members, rs_window=14, mom_window=14):
    bench = prices[benchmark]
    rows = []
    for tkr in members:
        if tkr not in prices.columns:
            continue
        rs = 100.0 * prices[tkr] / bench
        rs_ratio = _zscore_normalize(rs, rs_window)
        rs_mom = _zscore_normalize(rs_ratio.diff(), mom_window)
        lr, lm = rs_ratio.iloc[-1], rs_mom.iloc[-1]
        if np.isnan(lr) or np.isnan(lm):
            continue
        if lr >= 100 and lm >= 100:
            quad = "Leading"
        elif lr >= 100 and lm < 100:
            quad = "Weakening"
        elif lr < 100 and lm < 100:
            quad = "Lagging"
        else:
            quad = "Improving"
        rows.append({
            "ticker": tkr, "rs_ratio": round(lr, 2), "rs_momentum": round(lm, 2),
            "quadrant": quad,
            "mom_delta": round(rs_mom.iloc[-1] - rs_mom.iloc[-2], 2)
                         if len(rs_mom.dropna()) > 1 else 0.0,
            "_ratio_series": rs_ratio, "_mom_series": rs_mom,
        })
    return pd.DataFrame(rows).set_index("ticker") if rows else pd.DataFrame()


def _ratio_score(prices, num, den, ma=20):
    if num not in prices.columns or den not in prices.columns:
        return None
    ratio = (prices[num] / prices[den]).dropna()
    if len(ratio) < ma + 5:
        return None
    sma = ratio.rolling(ma).mean()
    above = ratio.iloc[-1] > sma.iloc[-1]
    up = sma.iloc[-1] > sma.iloc[-5]
    if above and up:
        return 1
    if (not above) and (not up):
        return -1
    return 0


def compute_risk_appetite(prices, pairs, ma=20):
    details, total, counted = {}, 0, 0
    for name, (num, den) in pairs.items():
        s = _ratio_score(prices, num, den, ma)
        if s is None:
            details[name] = "n/a"
            continue
        details[name] = {1: "risk-ON", 0: "neutral", -1: "risk-OFF"}[s]
        total += s; counted += 1
    if counted == 0:
        regime = "Unknown (데이터 부족)"
    elif total >= 2:
        regime = "RISK-ON (위험선호 우세)"
    elif total <= -2:
        regime = "RISK-OFF (위험회피 우세)"
    else:
        regime = "MIXED (혼조 / 전환 가능 구간)"
    return {"score": total, "max": counted, "regime": regime, "details": details}


def trend_state(prices, ticker, fast=50, slow=200):
    if ticker not in prices.columns:
        return "n/a"
    px = prices[ticker].dropna()
    if len(px) < slow:
        slow = max(20, len(px) // 2); fast = min(fast, slow // 2)
    mf = px.rolling(fast).mean().iloc[-1]
    ms = px.rolling(slow).mean().iloc[-1]
    last = px.iloc[-1]
    if np.isnan(mf) or np.isnan(ms):
        return "n/a"
    if last > mf > ms:
        return "Uptrend"
    if last < mf < ms:
        return "Downtrend"
    return "Neutral"


QUAD_FLOW = {"Improving": 2, "Leading": 1, "Weakening": -1, "Lagging": -2}
TREND_SCORE = {"Uptrend": 1, "Neutral": 0, "Downtrend": -1, "n/a": 0}


def build_report(prices, interval):
    rrg = compute_rrg(prices, BENCHMARK, list(SECTORS.keys()))
    risk = compute_risk_appetite(prices, RISK_PAIRS)
    if rrg.empty:
        print("RRG 계산 실패: 데이터 부족.")
        return rrg, risk

    table = []
    for tkr, row in rrg.iterrows():
        tr = trend_state(prices, tkr)
        rotate = 0.5 if row["mom_delta"] > 0 else (-0.5 if row["mom_delta"] < 0 else 0)
        score = QUAD_FLOW[row["quadrant"]] + rotate + TREND_SCORE[tr]
        table.append({
            "Sector": SECTORS[tkr], "Ticker": tkr, "Quadrant": row["quadrant"],
            "RS-Ratio": row["rs_ratio"], "RS-Mom": row["rs_momentum"],
            "Rot": "U" if row["mom_delta"] > 0 else ("D" if row["mom_delta"] < 0 else "-"),
            "Trend": tr, "FlowScore": round(score, 2),
        })
    df = pd.DataFrame(table).sort_values("FlowScore", ascending=False).reset_index(drop=True)

    bar = "=" * 78
    print(bar)
    print(f" 섹터 자금흐름 판단 모델  (기준 {interval}봉, 벤치마크 {BENCHMARK})")
    print(f" 데이터 마지막: {prices.index[-1].date()}")
    print(bar)
    print(f"\n[1] 시장 국면: {risk['regime']}  (점수 {risk['score']:+d}/{risk['max']})")
    for k, v in risk["details"].items():
        print(f"     - {k:<14}: {v}")
    print("\n[2] 섹터 자금흐름 랭킹 (위=유입 우세)")
    print(df.to_string(index=False))
    print("\n[3] 핵심 요약")
    for label, q in [("유입 시작(Improving)", "Improving"),
                     ("주도 중(Leading)", "Leading"),
                     ("유출 경고(Weakening)", "Weakening")]:
        sub = df[df["Quadrant"] == q]
        if not sub.empty:
            print(f"  · {label}: " + ", ".join(f"{r.Sector}({r.Ticker})" for r in sub.itertuples()))
    print("\n[4] 거시 참고 (최근 5봉 변화)")
    for tkr, label in MACRO.items():
        if tkr in prices.columns:
            s = prices[tkr].dropna()
            if len(s) > 6:
                print(f"     - {label:<10}({tkr:<6}): {(s.iloc[-1]/s.iloc[-5]-1)*100:+.2f}%")
    print("\n" + bar)
    print(" 주의: 신호 '확인' 도구이며 예측이 아님. 여러 신호 합의 시 신뢰. 투자자문 아님.")
    print(bar)
    return df, rrg


def plot_rrg(rrg, outfile="rrg_chart.png", tail=8):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.axhline(100, color="gray", lw=0.8); ax.axvline(100, color="gray", lw=0.8)
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
        ax.annotate(tkr, (r.values[-1], m.values[-1]), fontsize=9, fontweight="bold",
                    xytext=(4, 4), textcoords="offset points")
    ax.text(110, 114, "Leading", color="#2ca02c", fontweight="bold")
    ax.text(110, 86, "Weakening", color="#bf9000", fontweight="bold")
    ax.text(86, 86, "Lagging", color="#d62728", fontweight="bold")
    ax.text(86, 114, "Improving", color="#1f77b4", fontweight="bold")
    ax.set_xlabel("RS-Ratio"); ax.set_ylabel("RS-Momentum")
    ax.set_title("Relative Rotation Graph — 섹터 자금 회전")
    ax.set_xlim(85, 115); ax.set_ylim(85, 115)
    fig.tight_layout(); fig.savefig(outfile, dpi=130)
    print(f"\n[차트 저장] {outfile}")


def all_tickers():
    t = {BENCHMARK}; t.update(SECTORS.keys())
    for num, den in RISK_PAIRS.values():
        t.add(num); t.add(den)
    t.update(MACRO.keys())
    return sorted(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="2y")
    ap.add_argument("--interval", default="1wk")
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--tail", type=int, default=8)
    args = ap.parse_args()
    print("데이터 다운로드 중...")
    try:
        prices = fetch_prices(all_tickers(), args.period, args.interval)
    except Exception as e:
        print(f"다운로드 실패: {e}"); sys.exit(1)
    df, rrg = build_report(prices, args.interval)
    if args.plot and not rrg.empty:
        plot_rrg(rrg, tail=args.tail)


if __name__ == "__main__":
    main()
