# CLAUDE.md — 이 레포에서 일하는 규칙

> Claude Code는 작업 전 이 파일, `00_PROJECT_SPEC.md`, `ROADMAP.md`를 읽는다.
> **단일 기준(source of truth)은 `00_PROJECT_SPEC.md`**다. 마일스톤 작업 지침은 `ROADMAP.md`.
> 스펙과 충돌하는 요청이 오면 먼저 충돌을 지적하고 확인을 받은 뒤 진행한다.

## 이 시스템의 정체성
미국 증시에서 자금이 '언제(국면)' '어디로(섹터/자산)' 이동하는지를 여러 지표의
합의로 **확인**하는 신호 엔진. **예측기가 아니라 확인기**다.

## 절대 원칙 (항상 지킬 것)
- 단일 지표를 맹신하지 않는다. 여러 신호가 같은 방향을 가리킬 때만 신뢰도를 올린다.
- 흐름/순환 데이터는 **후행적**일 수 있음을 코드 주석과 출력에 명시한다.
- 모든 사용자 대면 출력 하단에 **면책 문구**(투자 자문/매매 권유 아님)를 넣는다.
  면책 문구는 `config.yaml`의 `disclaimer`에서 온다. 하드코딩 금지.
- "오를 것이다" 같은 **단정적 미래 표현 금지**. "유입 신호", "위험선호 우세" 같은
  상태 서술만 쓴다(코드·주석·출력 전부).

## 아키텍처 (3개 층)
- **Layer 1 `signals/rrg.py`** — RS-Ratio/RS-Momentum → 4분면 ("어디로").
- **Layer 2 `signals/risk.py`** — 비율 페어 추세로 risk-on/off ("언제/국면").
- **Layer 3 `signals/trend.py`** — 가격 vs 50/200MA 1차 추세 (안전장치).
- **종합 `report/synthesize.py`** — 세 층을 합의 점수로 묶고 보고서 렌더.

## 기술/품질 기준
- Python 3.11+, pandas / numpy / matplotlib / yfinance / pyyaml / pytest.
- **신호 계산 함수는 순수함수**로 작성한다. 네트워크 접근은 `data/loader.py`에만 격리.
- **외부 네트워크 없이** 합성 데이터로 통과하는 pytest를 함께 유지한다.
  (`tests/conftest.py`의 합성 fixture를 신호 함수에 직접 주입.)
- 티커·윈도우·가중치·면책문구 등 설정값은 **`config.yaml`로만** 관리(하드코딩 금지).
- RRG 4분면 경계(100 기준)와 위험선호 점수 합산은 **반드시 테스트**한다.
  - 단, 노이즈 없는 합성 데이터에서는 RS-Momentum이 100 근처에 머물러
    Leading/Weakening 경계가 칼날 위에 선다. 따라서 **RRG 테스트는 모멘텀 '분면'을
    단언하지 말고 RS-Ratio 좌우 반면(부호)을 단언**한다. 모멘텀 경계 단언은 깨지기 쉬우므로 피한다.
- 데이터 부족·티커 누락 시 **예외로 죽지 말고** 안전하게 degrade한다.
- 차트 라벨은 **영어로 통일**한다(제목 포함). 프로토타입 `plot_rrg`의 제목이 아직 한글이므로
  M1 리팩터링에서 영어로 교체한다.
- 답변·주석·설명은 한국어, 코드 식별자는 영어. 포매팅은 ruff/black.

## 확정된 설계 결정 (변경 시 config 또는 스펙과 함께)
1. **RS-Momentum = RS-Ratio의 '변화량(diff)'의 z-score.** 스펙 초기 문구는 "변화율"이었으나,
   RS-Ratio가 이미 100 근처로 정규화돼 있고 z-score가 상수배를 제거하므로 변화율(pct_change)과
   결과가 사실상 동일하다. 분모가 없어 NaN/극단값이 없는 diff를 채택한다. 기준 정의는
   `signals/rrg.py` 상단 주석을 따른다.
2. **종합 점수 = quad_flow + rotation 부호 + trend.** 가중치 수치는 `config.yaml`의 `weights`이며
   프로토타입 값을 초기값으로 둔다. `quad_flow`의 **Improving(+2) > Leading(+1)** 은 "막 유입이
   시작된 이른 신호를 더 높게 친다"는 의도된 편향이다(모멘텀 추종 아님). config 주석에 이 의도를 명시할 것.
3. **추세 게이트(`weights.trend_gate`)는 기본 OFF**(프로토타입과 동일, 단순 가중합).
   - 게이트를 토글로 구현하되, ON이어도 **Improving 분면은 강등하지 않는다**(이른 신호라 추세가
     아직 Downtrend인 게 정상). 단순 "Downtrend면 양수 점수 0" 식의 일괄 강등은 쓰지 않는다.
   - 게이트 기본값 채택과 강등 규칙 확정은 **M4의 휩소 리포트로 실측한 뒤** 결정한다. M1에서는
     토글만 만들고 OFF로 둔다.

## 작업 방식
- **프로토타입 `sector_rotation_model.py`의 검증된 계산 로직을 출발점으로 삼는다.
  백지에서 새로 짜지 않는다.**
- 큰 변경 전 계획과 파일 트리를 먼저 제시하고 동의를 구한다.
- 거대한 코드를 한 번에 쏟지 않는다. `ROADMAP.md`의 마일스톤(M1~M4) 단위로 쪼갠다.
- 변경 시 무엇을 왜 바꿨는지 짧게 설명하고, 커밋은 모듈 단위로 작게 나눈다.

## 검증 커맨드
```bash
pip install -e ".[dev]"     # 또는: pip install pandas numpy matplotlib pyyaml pytest yfinance
pytest -q                    # 네트워크 없이 전부 통과해야 함
python -m srm.cli            # 실데이터 실행 (네트워크 필요)
python -m srm.cli --plot --interval 1wk --period 2y
```
