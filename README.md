# 섹터 순환매 / 자금 흐름 판단 모델 (SRM)

미국 증시에서 자금이 **언제(어떤 국면에) 어디로(어떤 섹터/자산으로)** 이동하는지를
여러 지표의 합의로 확률적으로 **확인**하는 신호 엔진입니다.

> ⚠️ 이 시스템은 **예측기가 아니라 확인기**입니다. 흐름/순환 데이터는 후행적일 수
> 있습니다. 본 자료는 **투자 자문이나 매매 권유가 아닙니다.**

## 3개 층 + 참고 맥락

1. **RRG 엔진** (`signals/rrg.py`) — 섹터별 RS-Ratio / RS-Momentum → 4분면 ("어디로").
2. **위험선호 층** (`signals/risk.py`) — 비율 페어 추세로 risk-on/off ("언제/국면").
3. **추세 필터 층** (`signals/trend.py`) — 가격 vs 50/200일 이동평균 (안전장치).

종합(`report/synthesize.py`)에서 세 층을 합의 점수(FlowScore)로 묶어 섹터 자금흐름
랭킹을 만들고, 여기에 **경기 사이클 위치**(`signals/cycle.py`, FRED 선행지표 7종 합의)를
참고용 맥락으로 덧붙입니다.

## 설치

```bash
pip install -e ".[dev]"
# 또는
pip install pandas numpy matplotlib pyyaml pytest yfinance pyarrow
```

(선택) 경기 사이클 섹션을 보려면 [fred.stlouisfed.org](https://fred.stlouisfed.org)에서
무료 API 키를 발급받아 환경변수 또는 레포 루트의 `.env` 파일에 넣습니다.
키가 없어도 나머지 기능은 그대로 동작하고 사이클 섹션만 생략됩니다.

```bash
echo "FRED_API_KEY=발급받은키" > .env   # .env는 .gitignore에 포함됨
```

## 사용

```bash
python -m srm.cli                                  # 기본 실행 (config.yaml의 주봉 2년)
python -m srm.cli --interval 1wk --period 5y       # 봉/기간 변경
python -m srm.cli --plot                           # RRG 차트 PNG 저장
python -m srm.cli --export json --export csv       # 랭킹표 내보내기
python -m srm.cli --backtest                       # 신호 안정성(휩소) 리포트 추가 출력
```

데이터 캐시/스냅샷 옵션:

```bash
python -m srm.cli --refresh                        # 캐시 무시하고 새로 다운로드
python -m srm.cli --no-cache                       # 캐시를 읽지도 쓰지도 않음
python -m srm.cli --no-snapshot                    # 이번 실행을 스냅샷으로 남기지 않음
python -m srm.cli --from-snapshot snapshots/<ts>   # 저장된 스냅샷으로 리포트 재현
```

- **캐시**: 다운로드 결과를 `.cache/`에 parquet으로 저장해 같은 날 재실행 시 재사용
  (날짜가 키에 포함되어 하루 단위 자동 갱신, 오래된 파일은 보관 정책에 따라 자동 정리).
- **스냅샷**: 실행에 사용한 데이터를 `snapshots/<타임스탬프>/`에 보존 — 같은 스냅샷이면
  언제 다시 돌려도 동일한 리포트가 재현됩니다(최신 N개만 보관).
- **`--backtest`**: 수익률 백테스트가 아니라 과거 신호가 얼마나 자주 번복됐는지(휩소율),
  추세 게이트 규칙 비교, RRG 윈도우 스윕을 출력하는 **신호 안정성** 리포트입니다.

## 테스트 (네트워크 불필요)

```bash
pytest -q     # 합성 데이터로 신호/백테스트/리포트 전부 검증 (155개)
```

## 설정

모든 티커·윈도우·가중치·임계값·면책문구는 `config.yaml`에서만 바꿉니다(코드 하드코딩 금지).
주요 섹션:

- `tickers` — 벤치마크(SPY)/섹터 ETF/위험선호 페어/거시 참고 지표.
- `windows` — RRG(rs/mom=14), 위험선호 MA(20)와 기울기 lookback, 추세 MA(50/200) 등.
- `weights` — 종합 점수 가중치. Improving(+2) > Leading(+1)은 "막 유입이 시작된 이른
  신호를 더 높게 친다"는 의도된 편향입니다.
  - `trend_gate`는 **기본 OFF** — M4 휩소 실측(주봉 2y/5y)에서 게이트가 점수 부호의
    번복률을 오히려 올려 켤 근거가 없었습니다. ON이면 분면과 추세가 정반대인 모순
    조합만 0점으로 강등하되, Improving(이른 유입 신호) 분면은 절대 강등하지 않습니다.
- `data` — 기본 period/interval + 캐시(7일)/스냅샷(20개) 보관 정책.
- `fred` / `cycle` — 선행지표 시리즈와 사이클 판정 파라미터(없으면 사이클 생략).
- `backtest` — 휩소 판정 horizon, 윈도우 스윕 후보.

## 구조

```
.
├─ config.yaml              # 설정 (단일 변경 지점)
├─ 00_PROJECT_SPEC.md       # 요구사항 명세 (단일 기준)
├─ CLAUDE.md / ROADMAP.md   # 작업 규칙 / 마일스톤 (M1~M4 완료)
├─ PROGRESS.md              # 진행 기록
├─ src/srm/
│  ├─ config.py             # config.yaml 로더 + 형식 검증
│  ├─ data/                 # 네트워크 접근은 이 층에만 격리
│  │  ├─ loader.py          #   yfinance 가격 다운로드
│  │  ├─ fred.py            #   FRED/DBnomics 선행지표
│  │  ├─ cache.py           #   parquet 캐시 + 보관 정리
│  │  └─ snapshot.py        #   재현용 스냅샷 + 보관 정리
│  ├─ signals/              # 순수함수 신호 계산
│  │  ├─ rrg.py             #   Layer 1: RS-Ratio/RS-Momentum 4분면
│  │  ├─ risk.py            #   Layer 2: 위험선호 점수
│  │  ├─ trend.py           #   Layer 3: 1차 추세
│  │  └─ cycle.py           #   경기 사이클 위치 (선행지표 합의)
│  ├─ backtest/             # 신호 안정성 측정 (수익률 백테스트 아님)
│  │  ├─ walk.py            #   시점별 분면/추세 이력
│  │  ├─ whipsaw.py         #   휩소율 + 게이트 규칙 비교
│  │  └─ sweep.py           #   RRG 윈도우 스윕
│  ├─ report/
│  │  ├─ synthesize.py      #   종합 점수 + 텍스트 리포트
│  │  ├─ plot.py            #   RRG 차트 (영어 라벨/범례)
│  │  ├─ export.py          #   JSON/CSV 내보내기
│  │  └─ backtest_report.py #   신호 안정성 리포트
│  └─ cli.py                # 엔트리포인트
└─ tests/                   # 합성 데이터 단위테스트 (네트워크 없음)
```

## 한계

- 흐름·순환·이동평균 기반 신호는 **후행적**입니다. 선행지표도 발표 지연과 사후
  개정이 있습니다.
- 단일 신호는 신뢰하지 않습니다. 여러 층이 같은 방향일 때만 신뢰도가 올라갑니다.
- 미래 수익을 단정하지 않으며, 상태 서술("유입 신호", "위험선호 우세")만 제공합니다.
- `--backtest`의 휩소율은 과거 신호 이력의 요약일 뿐, 미래 성과를 보장하지 않습니다.
