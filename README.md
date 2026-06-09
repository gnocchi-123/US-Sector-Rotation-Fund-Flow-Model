# 섹터 순환매 / 자금 흐름 판단 모델 (SRM)

미국 증시에서 자금이 **언제(어떤 국면에) 어디로(어떤 섹터/자산으로)** 이동하는지를
여러 지표의 합의로 확률적으로 **확인**하는 신호 엔진입니다.

> ⚠️ 이 시스템은 **예측기가 아니라 확인기**입니다. 흐름/순환 데이터는 후행적일 수
> 있습니다. 본 자료는 **투자 자문이나 매매 권유가 아닙니다.**

## 3개 층
1. **RRG 엔진** (`signals/rrg.py`) — 섹터별 RS-Ratio / RS-Momentum → 4분면 ("어디로").
2. **위험선호 층** (`signals/risk.py`) — 비율 페어 추세로 risk-on/off ("언제/국면").
3. **추세 필터 층** (`signals/trend.py`) — 가격 vs 50/200일 이동평균 (안전장치).

종합(`report/synthesize.py`)에서 세 층을 합의 점수로 묶어 섹터 자금흐름 랭킹을 만듭니다.

## 설치
```bash
pip install -e ".[dev]"
# 또는
pip install pandas numpy matplotlib pyyaml pytest yfinance
```

## 사용
```bash
python -m srm.cli                                  # 기본 실행 (config.yaml 사용)
python -m srm.cli --interval 1wk --period 2y       # 주봉 2년
python -m srm.cli --plot                           # RRG 차트 PNG 저장
python -m srm.cli --config path/to/config.yaml     # 다른 설정 사용
```

## 테스트 (네트워크 불필요)
```bash
pytest -q     # 합성 데이터로 신호 함수 검증
```

## 설정
모든 티커·윈도우·가중치·임계값·면책문구는 `config.yaml`에서만 바꿉니다(코드 하드코딩 금지).
종합 점수 가중치, 위험선호 임계값(±2), 추세 게이트(`trend_gate`)도 여기 있습니다.
`trend_gate`는 기본 OFF이며, 켜더라도 Improving(이른 유입 신호) 분면은 강등하지 않습니다.
게이트 기본값과 윈도우 튜닝은 M4에서 휩소(가짜신호) 실측으로 결정합니다.

## 구조
```
sector-rotation/
├─ config.yaml            # 설정 (단일 변경 지점)
├─ pyproject.toml
├─ CLAUDE.md              # 작업 규칙
├─ ROADMAP.md             # M1~M4 단계
├─ src/srm/
│  ├─ config.py
│  ├─ data/loader.py      # 네트워크 격리 (yfinance)
│  ├─ signals/{rrg,risk,trend}.py
│  ├─ report/{synthesize,plot}.py
│  └─ cli.py
└─ tests/                 # 합성 데이터 단위테스트
```

## 한계
- 흐름·순환·이동평균 기반 신호는 **후행적**입니다.
- 단일 신호는 신뢰하지 않습니다. 여러 층이 같은 방향일 때만 신뢰도가 올라갑니다.
- 미래 수익을 단정하지 않으며, 상태 서술("유입 신호", "위험선호 우세")만 제공합니다.
