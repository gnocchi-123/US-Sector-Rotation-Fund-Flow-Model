# Layer 2: 위험선호 층 — 비율 페어 추세로 risk-on/off 점수화 ("언제/국면").
# 순수함수만 둔다. 임계값(risk_on/risk_off)은 config.yaml의 thresholds에서 인자로 받는다.

from __future__ import annotations

import pandas as pd


def ratio_score(
    prices: pd.DataFrame, num: str, den: str, ma: int = 20, slope: int = 5
) -> int | None:
    """비율 페어(num/den)의 추세 점수.

    이동평균 위 + 이동평균 자체가 상승 중 -> +1(risk-on)
    이동평균 아래 + 이동평균 하락 중 -> -1(risk-off)
    그 외(혼조) -> 0
    데이터가 부족하거나 티커가 없으면 None.
    `slope`는 이동평균 기울기 판정 lookback — 마지막 값을 마지막에서 slope번째 값
    (= slope-1봉 전)과 비교한다(config.yaml windows.risk_slope).
    """
    if num not in prices.columns or den not in prices.columns:
        return None
    ratio = (prices[num] / prices[den]).dropna()
    if len(ratio) < ma + slope:
        return None
    sma = ratio.rolling(ma).mean()
    above = ratio.iloc[-1] > sma.iloc[-1]
    up = sma.iloc[-1] > sma.iloc[-slope]
    if above and up:
        return 1
    if (not above) and (not up):
        return -1
    return 0


def compute_risk_appetite(
    prices: pd.DataFrame,
    pairs: dict[str, tuple[str, str]],
    ma: int = 20,
    risk_on: float = 2,
    risk_off: float = -2,
    slope: int = 5,
) -> dict:
    """페어별 점수를 합산해 위험선호 국면을 상태 서술로 판정한다.

    반환: {"score": 합산 점수, "max": 채점된 페어 수,
           "regime": 상태 서술, "details": 페어별 "risk-ON"/"neutral"/"risk-OFF"/"n/a"}
    """
    details: dict[str, str] = {}
    total = 0
    counted = 0
    for name, (num, den) in pairs.items():
        s = ratio_score(prices, num, den, ma, slope)
        if s is None:
            details[name] = "n/a"
            continue
        details[name] = {1: "risk-ON", 0: "neutral", -1: "risk-OFF"}[s]
        total += s
        counted += 1
    if counted == 0:
        regime = "Unknown (데이터 부족)"
    elif total >= risk_on:
        regime = "RISK-ON (위험선호 우세)"
    elif total <= risk_off:
        regime = "RISK-OFF (위험회피 우세)"
    else:
        regime = "MIXED (혼조 / 전환 가능 구간)"
    return {"score": total, "max": counted, "regime": regime, "details": details}
