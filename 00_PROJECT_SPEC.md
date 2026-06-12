# 섹터 순환매 / 자금 흐름 판단 모델 — 프로젝트 스펙 (v1)

> 이 문서는 Claude Project의 **참고 파일**이자, GitHub의 Claude(Claude Code)가
> 구현 시 따라야 할 **요구사항 명세(PRD)** 다. 프로토타입 `sector_rotation_model.py`는
> 이 스펙의 1차 구현 예시이며, 정식 구현은 이 문서를 기준으로 한다.

---

## 1. 한 줄 정의
미국 증시에서 **자금이 '언제(어떤 국면에)' '어디로(어떤 섹터/자산으로)' 이동하는가**를
여러 지표의 합의로 확률적으로 추정·확인하는 신호 엔진.

## 2. 절대 원칙 (구현 시 항상 지킬 것)
- 이 시스템은 **예측기가 아니라 '확인기'**다. 단일 지표를 신뢰하지 않고, 여러 신호가
  같은 방향을 가리킬 때만 신뢰도를 올린다.
- 모든 흐름 데이터는 **후행적**일 수 있음을 코드 주석과 출력에 명시한다.
- **투자 자문/매매 권유가 아니다.** 출력물 하단에 항상 면책 문구를 포함한다.
- 미래 수익률을 단정하는 표현(예: "오를 것이다")을 코드/주석/출력에서 쓰지 않는다.
  대신 "유입 신호", "위험선호 우세" 같은 상태 서술을 쓴다.

## 3. 아키텍처 — 3개 층(layer)
### Layer 1. RRG 엔진 (핵심: "어디로")
- 각 섹터의 상대강도 수준(RS-Ratio)과 변화(RS-Momentum)를 계산.
- RS = 100 × (섹터가격 / 벤치마크가격), 벤치마크 = SPY.
- RS-Ratio = 100 + 롤링 z-score(RS).
- RS-Momentum = 100 + 롤링 z-score(RS-Ratio의 **변화량(diff)**).
  - (정정) 초기 문구는 "변화율"이었으나 RS-Ratio가 이미 100 근처로 정규화돼 있고,
    z-score는 상수배를 제거하므로 변화율(pct_change)과 변화량(diff)의 결과가 사실상
    동일하다. 분모가 없어 NaN/극단값이 없는 diff를 단일 기준으로 확정한다.
- 4분면 분류와 자금흐름 해석:
  | 분면 | 조건 | 자금 흐름 의미 |
  |---|---|---|
  | Improving | Ratio<100, Mom≥100 | 유입 **시작** (이른 신호) |
  | Leading | Ratio≥100, Mom≥100 | 이미 주도 중 |
  | Weakening | Ratio≥100, Mom<100 | 유출 **시작** (이른 경고) |
  | Lagging | Ratio<100, Mom<100 | 소외 / 빠져나간 상태 |

### Layer 2. 위험선호 층 (핵심: "언제/어떤 국면")
- 비율 페어의 추세로 risk-on / risk-off 점수화. 페어:
  - IWM/SPY (소형/대형), RSP/SPY (동일가중/시총가중, breadth),
    XLY/XLP (경기/방어), HYG/LQD (신용 위험선호), VUG/VTV (성장/가치).
- 각 페어: 이동평균 위 + 기울기 상승 → +1(risk-on), 반대 → −1, 혼조 → 0.
- 합산 점수로 RISK-ON / MIXED / RISK-OFF 국면 판정.

### Layer 3. 추세 필터 층 (안전장치)
- 가격 vs 50/200일 이동평균으로 각 자산 1차 추세(Uptrend/Neutral/Downtrend).
- 순환 신호의 가짜 신호를 거르는 데 사용.
  - 구현 방식은 **config 토글(`weights.trend_gate`)** 로 둔다. **기본 OFF(가중합)로
    확정** — M4 휩소 실측(주봉 2y/5y, 2026-06)에서 게이트가 FlowScore 부호 휩소율을
    77~79%→81%로 오히려 올려 안정성 개선 근거가 없었다(`--backtest`로 재실측 가능).
  - ON이면 **contradiction_only** 규칙으로 확정: 분면과 추세가 정반대인 모순 조합
    (Leading+Downtrend, Weakening/Lagging+Uptrend)만 점수를 0으로 강등한다.
  - ON이어도 **Improving 분면은 처벌하지 않는다**: Improving은 가격이 오르기 전에
    유입을 잡는 이른 신호라 추세가 아직 Downtrend인 것이 정상이기 때문이다.

### 종합
- 섹터별 종합 점수 = (4분면 흐름 가중) + (모멘텀 회전 방향) + (1차 추세).
- 가중치 수치는 `config.yaml`의 `weights`에서 관리한다(프로토타입 값을 초기값으로).
  - **의도된 편향**: `quad_flow`에서 Improving(+2) > Leading(+1)로 둔다. 이는
    "이미 주도 중인 곳보다 막 유입이 시작된 이른 신호를 더 높게 친다"는 본 시스템의
    성격이며 모멘텀 추종이 아니다. RRG 윈도우(rs/mom=14)는 M4 스윕 실측에서
    전환 수·휩소율의 균형점으로 확인되어 유지로 확정했다.
- 출력: 시장 국면 → 섹터 자금흐름 랭킹표 → 핵심 요약(유입/주도/유출) → 거시 참고.

## 4. 데이터
- 1차 소스: **yfinance** (무료, 일/주봉).
- 거시 참고: 10Y 금리(^TNX), 유가(USO), 금(GLD), 달러(UUP), 변동성(^VIX).
- (확장) FRED API로 ISM PMI, 장단기 금리차(T10Y2Y), 신규 실업수당 청구 등 선행지표 추가.
- 데이터는 로컬 캐시(parquet)로 저장해 반복 호출을 줄인다.

## 5. 정식 구현에서 갖춰야 할 것 (프로토타입 대비 확장)
1. **모듈 분리**: `data/`, `signals/`(rrg, risk, trend), `report/`, `cli.py`.
2. **설정 외부화**: 티커·윈도우·가중치를 `config.yaml`로 분리.
3. **테스트**: 합성 데이터로 각 신호 함수 단위테스트(pytest). 외부 네트워크 없이 통과해야 함.
4. **재현성**: 데이터 스냅샷 저장 + 분석 시점 기록.
5. **백테스트 훅(선택)**: 과거 시점에서 4분면/국면이 어떻게 변했는지 추적하는 함수.
6. **출력**: 콘솔 표 + (선택) RRG PNG 차트 + JSON/CSV 내보내기.
7. **에러 처리**: 데이터 부족·티커 누락 시 안전하게 degrade.

## 6. 기술 스택 / 컨벤션
- Python 3.11+, pandas, numpy, matplotlib, yfinance, pyyaml, pytest.
- 타입 힌트 사용, docstring은 한국어 허용, 함수는 순수함수 지향(테스트 용이).
- 포매팅: ruff/black. 커밋은 작고 의미 단위로.

## 7. 제안 파일 구조
```
sector-rotation/
├─ README.md
├─ config.yaml
├─ pyproject.toml
├─ src/srm/
│  ├─ data/loader.py        # yfinance 다운로드 + 캐시
│  ├─ signals/rrg.py        # Layer 1
│  ├─ signals/risk.py       # Layer 2
│  ├─ signals/trend.py      # Layer 3
│  ├─ report/synthesize.py  # 종합 점수 + 출력
│  ├─ report/plot.py        # RRG 차트
│  └─ cli.py                # 엔트리포인트(argparse/typer)
└─ tests/
   ├─ conftest.py           # 합성 가격 데이터 fixture
   ├─ test_rrg.py
   ├─ test_risk.py
   └─ test_trend.py
```

## 8. 단계별 로드맵(마일스톤)
- **M1**: 프로토타입을 위 구조로 리팩터링 + 단위테스트 + config 외부화.
- **M2**: 캐시/스냅샷, JSON·CSV 내보내기, 차트 개선.
- **M3**: FRED 선행지표 결합, 경기 사이클 위치 추정 추가.
- **M4**: 백테스트 훅 + 신호 안정성(가짜신호) 점검 리포트. (완료 — `--backtest`가
  휩소율/게이트 비교/윈도우 스윕을 출력. trend_gate 기본 OFF + contradiction_only
  규칙 + 윈도우 14 유지를 실측 근거로 확정.)
