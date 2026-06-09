# ROADMAP — 마일스톤 작업 지침 (M1 ~ M4)

> 각 마일스톤은 작은 커밋으로 쪼갠다. **완료 기준(✅)을 만족하기 전에 다음 단계로 넘어가지 않는다.**
> 단일 기준은 `00_PROJECT_SPEC.md`, 작업 규칙은 `CLAUDE.md`.

---

## M1 — 골격화 + config 외부화 + 단위테스트

프로토타입(`sector_rotation_model.py`)의 검증된 로직을 스펙 7절 구조로 분해하고,
설정을 외부화하고, 네트워크 없이 통과하는 테스트를 붙인다. **백지에서 새로 짜지 말고
프로토타입의 검증된 계산 로직을 출발점으로 삼는다.**

**만들 파일**
- `config.yaml` — 티커/윈도우/가중치/임계값/면책문구. `weights.quad_flow`에 Improving>Leading
  편향의 의도를 주석으로 명시. `weights.trend_gate: false`(기본 OFF).
- `src/srm/config.py` — config 로더(필수 키 검증, 불변 `Config`).
- `src/srm/data/loader.py` — yfinance 다운로드(네트워크 격리).
- `src/srm/signals/{rrg,risk,trend}.py` — 순수 신호 함수 + 테스트용 분류 헬퍼.
  - rrg: RS-Momentum은 **diff** 기반(결정 1). 4분면 분류를 별도 헬퍼로 분리.
- `src/srm/report/{synthesize,plot}.py` — 종합 점수/렌더, RRG 차트(영어 라벨).
  - 종합: `trend_gate` 토글을 읽되 ON이어도 **Improving은 강등 제외**(결정 3). 기본 OFF.
- `src/srm/cli.py` — 엔트리포인트.
- `tests/{conftest,test_rrg,test_risk,test_trend}.py` — 합성 데이터 단위테스트.

**완료 기준**
- [ ] `pytest -q`가 **네트워크 없이** 전부 통과.
- [ ] RRG 4분면 경계(100), 위험선호 임계값(±2), 추세 분류/degrade 테스트 존재.
- [ ] 신호 함수에 네트워크 접근 없음(loader에만 격리).
- [ ] 면책 문구가 config에서 출력으로 전달됨.

**구현 주의 (검증 중 드러난 함정)**
- 완벽히 매끄러운 합성 가격에서는 RS-Momentum이 100 근처에 머물러 Leading/Weakening 경계가
  칼날 위에 선다. 따라서 RRG 테스트는 모멘텀 '분면'이 아니라 상대강도 좌우 반면(RS-Ratio 부호)을
  단언하는 것이 견고하다. 노이즈 없는 데이터의 모멘텀은 신뢰하지 말 것.

**M1 마무리로 남은(권장) 작업**
- [ ] `git init` 후 `.gitignore`(`__pycache__/`, `*.parquet`, `*.png`, `.venv/`) 추가.
- [ ] `ruff`/`black` 1회 정리 커밋.
- [ ] 실데이터 1회 실행해 출력 형태 눈으로 확인(`python -m srm.cli`).
- [ ] (선택) `compute_rrg`가 반환하는 `_ratio_series`/`_mom_series`를 별도 접근자로
      분리할지 검토(데이터 표와 플롯용 시계열의 결합도 낮추기).

**커밋 분할 예시**
1. `chore: repo skeleton + pyproject + config.yaml`
2. `feat(config): config loader`
3. `feat(data): yfinance loader (network isolated)`
4. `feat(signals): rrg / risk / trend pure functions`
5. `test: synthetic-data unit tests (no network)`
6. `feat(report): synthesize + cli + plot`

---

## M2 — 캐시/스냅샷 · 내보내기 · 차트 개선

**목표**: 반복 호출을 줄이고, 분석을 재현 가능하게 만들고, 결과를 외부로 뺀다.

**작업**
- [ ] `data/cache.py`: 다운로드 결과를 **parquet 로컬 캐시**로 저장/로드.
      캐시 키 = (티커 집합 해시, period, interval, 날짜). `--no-cache`, `--refresh` 플래그.
- [ ] **스냅샷/재현성**: 실행 시 사용한 가격 데이터와 분석 시점(타임스탬프)을
      `snapshots/<timestamp>/`에 저장. 같은 스냅샷으로 동일 결과를 재생산할 수 있어야 함.
- [ ] **내보내기**: 랭킹표를 JSON/CSV로 (`report/export.py`, `--export json|csv`).
      JSON에는 국면·점수·면책문구 메타 포함.
- [ ] **차트 개선**: 4분면 색·꼬리 길이 옵션화, 범례, 저장 경로 인자화.

**완료 기준**
- 두 번째 실행이 캐시로 네트워크 없이 동작.
- 같은 스냅샷 → 같은 보고서(재현성) 테스트.
- export 산출물의 스키마 테스트(합성 데이터).

---

## M3 — FRED 선행지표 결합 + 경기 사이클 위치 추정

**목표**: 후행적 가격 신호에 **선행지표** 맥락을 더한다(스펙 4절 확장).

**작업**
- [ ] `data/fred.py`: FRED API로 ISM PMI, 장단기 금리차(`T10Y2Y`),
      신규 실업수당 청구 등 선행지표 로드. **API 키는 환경변수**, 네트워크는 데이터 층에만.
- [ ] `signals/cycle.py`: 선행지표 묶음으로 경기 사이클 위치(예: 둔화/저점/회복/과열)를
      **상태 서술**로 추정(단정 표현 금지). 어떤 섹터군이 그 국면과 '정합적'인지 참고 표.
- [ ] 종합 보고서에 사이클 위치 섹션 추가(어디까지나 참고/맥락).

**완료 기준**
- FRED 없이도(키 미설정) 안전 degrade하여 기존 기능은 그대로 동작.
- 사이클 분류 함수의 합성 입력 단위테스트.
- 선행지표 후행/발표지연 한계를 출력에 명시.

---

## M4 — 백테스트 훅 + 가짜신호 안정성 리포트

**목표**: 신호가 과거에 어떻게 변했는지 추적하고, 가짜 신호 빈도를 점검한다(스펙 8절 M4).

**작업**
- [ ] `backtest/walk.py`: 과거 각 시점에서 4분면/국면이 어떻게 바뀌었는지 추적하는
      훅. (수익률 단정 금지 — '신호 상태 변화'만 기록.)
- [ ] **가짜신호 점검 리포트**: 분면 전환이 다음 N봉 안에 되돌려진 비율(휩소율),
      추세 게이트(`trend_gate`) on/off가 신호 안정성에 주는 차이.
- [ ] **추세 게이트 기본값 결정**: 위 휩소 실측을 근거로 `trend_gate` 기본값과
      강등 규칙을 확정한다. 후보 규칙은 "Downtrend 일괄"이 아니라 "Leading인데 Downtrend"처럼
      **모순 조합만 강등**, 그리고 Improving은 항상 제외. 결정과 근거를 스펙/CLAUDE.md에 반영.
- [ ] **윈도우 튜닝(1순위)**: 주봉 `window=14`(~3.5개월)는 반응이 빨라 휩소가 많을 수 있다.
      `rs_window`/`mom_window`를 후보값으로 스윕해 안정성 변화를 표로 비교.
- [ ] 신호 안정성 요약을 표/차트로.

**완료 기준**
- 백테스트가 합성 시계열에서 결정론적으로 동작(테스트 가능).
- 리포트는 '예측 성과'가 아니라 '신호 일관성/안정성' 관점으로 서술.
- 모든 출력에 후행성·면책 문구 유지.

---

### 전 마일스톤 공통 점검
- 새 기능마다 합성 데이터 테스트를 추가하고 `pytest -q`가 네트워크 없이 통과.
- 단정적 미래 표현이 새로 들어오지 않았는지 검토(상태 서술만).
- 모든 사용자 대면 출력에 면책 문구 유지.
