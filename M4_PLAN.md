# M4_PLAN — 백테스트 훅 + 휩소(가짜신호) 리포트 작업 계획서

> **임시 작업 계획서.** 단일 기준은 `00_PROJECT_SPEC.md`(8절 M4) + `ROADMAP.md`(M4 절),
> 작업 규칙은 `CLAUDE.md`. 진행할 때마다 아래 체크박스와 `PROGRESS.md`를 갱신하고,
> **M4 완료 시 확정 결정을 CLAUDE.md(결정 3)/스펙/config 주석에 반영한 뒤 이 파일은 삭제**한다.

## 목표

신호가 과거에 얼마나 자주 번복됐는지(휩소율)를 실측해서,
M1부터 보류해 온 두 가지를 **근거를 갖고 확정**한다:
1. `weights.trend_gate` 기본값(ON/OFF)과 강등 규칙 (CLAUDE.md 결정 3)
2. RRG 윈도우 `rs_window`/`mom_window`(현재 14) 적정값 (ROADMAP 1순위)

원칙: 수익률 백테스트가 아니다. **'신호 상태 변화'만 기록**하고, 출력은
"예측 성과"가 아니라 "신호 일관성/안정성" 관점으로 서술한다(스펙 8절).
모든 새 코드에 합성 데이터 테스트를 붙이고 `pytest -q`가 네트워크 없이 통과해야 한다.

## 사전 확인 (착수 시 1회)

- [x] `git pull` 후 `pytest -q` 통과(현재 115개), `PROGRESS.md`의 "M1~M3 리뷰 보완" 절 읽기.
- [x] 아래 이월 항목이 커밋 C1~C2, C7에 흡수되어 있음을 인지:
      `compute_rrg` 중복 계산(C1), risk/macro 하드코딩 lookback(C2), 사이클 z~0 칼날 경계(C7).

## 커밋 계획 (작은 커밋, 각각 pytest 통과 + PROGRESS.md 갱신)

### C1. `refactor(signals): extract rs_series + reuse rrg in cli`
- [x] `signals/rrg.py`: 루프 본문에서 시계열 계산을 분리 —
      `rs_series(prices, benchmark, ticker, rs_window, mom_window) -> tuple[pd.Series, pd.Series] | None`
      (RS-Ratio/RS-Momentum 전체 시계열; 티커/벤치마크 없으면 None). `compute_rrg`는 이를 호출(출력 불변).
- [x] `report/synthesize.py`: `compute_flow_table(prices, cfg, rrg=None)` — 미리 계산한 RRG 재사용 허용.
- [x] `cli.py`: `compute_rrg` 1회만 계산해 flow_table과 `--plot`에 공유(중복 계산 이월 항목 해소).
- [x] 테스트: 기존 RRG/synthesize 테스트가 회귀 가드(변경 없이 통과해야 함) + rs_series 단위테스트 2~3건.

### C2. `refactor(config): externalize remaining hardcoded lookbacks`
- [x] `config.yaml` `windows`에 `risk_slope: 5`(risk.py의 `sma.iloc[-5]` 기울기 lookback),
      `macro_lookback: 5`(synthesize [4]의 `iloc[-5]`) 추가 — 프로토타입 값 그대로, 의미 주석.
- [x] `risk.py`/`synthesize.py`/`config.py`에 파라미터로 연결. [4] 라벨을 실제 의미("N봉 전 대비")로 정정.
- [x] 테스트: config 파싱 + ratio_score lookback 파라미터화 검증.

### C3. `feat(config): backtest options section`
- [x] `config.yaml`에 옵션 섹션(`fred:`와 같은 방식 — `_REQUIRED_KEYS` 불변, 없으면 기본값):
      ```yaml
      backtest:
        horizon: 4            # 휩소 판정: 전환 후 N봉 내 직전 분면 복귀면 휩소
        min_history: 60       # 이력 추적 최소 봉 수(미만이면 백테스트 생략 degrade)
        window_candidates: [8, 10, 14, 20, 26]   # rs/mom 윈도우 스윕 후보(14=현행)
      ```
- [x] `config.py`: `backtest_horizon`/`backtest_min_history`/`backtest_window_candidates` 필드.
- [x] 테스트: 섹션 없음 하위호환 + 파싱.

### C4. `feat(backtest): quadrant/trend history pure functions`
- [x] 신규 `src/srm/backtest/walk.py` (순수함수만, 네트워크/Config 객체 의존 없음):
  - `quadrant_history(prices, benchmark, members, rs_window, mom_window) -> pd.DataFrame`
    — 인덱스=시간, 컬럼=티커, 값=분면 라벨(C1의 `rs_series` + `classify_quadrant`를 시점별 적용,
    NaN 구간은 결측). 데이터 부족 티커는 컬럼 제외(degrade).
  - `trend_history(prices, ticker, fast, slow) -> pd.Series` — trend_state와 같은 규칙의 시점별 판정.
  - `transitions(labels: pd.Series) -> pd.DataFrame` — (시점, from, to) 전환 기록(결측 건너뜀).
- [x] 테스트(`tests/test_walk.py`, conftest의 `price_panel` 재사용):
      결정론성(같은 입력→같은 출력), **마지막 시점 값이 `compute_rrg`/`trend_state`와 일치**,
      transitions가 인위적 라벨 시퀀스에서 정확, 빈/부족 입력 degrade.
      **모멘텀 분면 자체는 단언 금지(M1 교훈)** — 좌우 반면·일관성만.

### C5. `feat(backtest): whipsaw metrics + trend-gate candidate comparison`
- [x] 신규 `src/srm/backtest/whipsaw.py`:
  - `whipsaw_rate(history: pd.DataFrame, horizon: int) -> dict`
    — 분면 전환이 horizon봉 내 직전 분면으로 복귀한 비율. 반환:
    `{"per_ticker": {tkr: {"transitions": n, "whipsaws": k, "rate": k/n}}, "total": {...}}`.
    전환 0건이면 rate 대신 None(degrade, NaN 금지).
  - 게이트 후보 규칙(순수함수): `apply_gate(quadrant, trend, score, rule)` —
    `rule="none"`(현행) / `rule="contradiction_only"`(**Leading인데 Downtrend, Weakening인데
    Uptrend 같은 모순 조합만 점수 0으로 강등. Improving은 항상 제외** — 결정 3 제약).
  - `score_sign_stability(quadrant_hist, trend_hist_by_ticker, weights, horizon, rule) -> dict`
    — 시점별 FlowScore 부호 시계열을 만들고 부호 플립의 휩소율을 규칙별 비교.
- [x] 테스트: 인위적 전환·복귀 패턴으로 비율 검증, Improving 비강등 단언, 규칙별 차이 발생 케이스.

### C6. `feat(backtest): window sweep`
- [x] 신규 `src/srm/backtest/sweep.py`:
      `sweep_windows(prices, benchmark, members, candidates, horizon) -> pd.DataFrame`
      — 후보 윈도우별(rs=mom 동일값 스윕) 전환 수/휩소율 표. 컬럼: window/transitions/whipsaws/rate.
- [x] 테스트: 결정론성 + 후보 수만큼 행 + 현행(14) 포함.

### C7. `feat(report): cycle borderline note + backtest report rendering`
- [x] `signals/cycle.py` 또는 `synthesize.py`: 사이클 수준 z 평균이 0 근처(|z| < 0.25, 상수로 두되
      의미 주석)면 국면 표기에 "(경계 근처 — 판정이 바뀌기 쉬움)" 문구 추가(이월 항목).
- [x] 신규 `report/backtest_report.py`: `render_backtest_report(whipsaw, gate_cmp, sweep, cfg) -> str`
      — 일반인이 읽을 수 있는 표(휩소율 = "신호가 N봉 안에 번복된 비율") + 게이트 규칙 비교 +
      윈도우 스윕 표. **"안정성" 서술만, 수익/예측 표현 금지.** 하단 `cfg.disclaimer`.
- [x] 테스트: 렌더 문자열에 핵심 섹션/면책 존재, 단정 표현 부재, 사이클 경계 문구 on/off.

### C8. `feat(cli): --backtest flag (M4 신호 안정성 리포트)`
- [ ] `cli.py`: `--backtest` — 가격 로드(캐시/스냅샷 경로 공유) 후 walk→whipsaw→sweep→
      `render_backtest_report` 출력. 실패해도 본 리포트를 절대 막지 않음(try/except degrade).
- [ ] 실측: `python -m srm.cli --backtest`(주봉 2y)와 `--period 5y`로 휩소율·게이트 비교·스윕 실측.

### C9. `feat: trend_gate default decision (M4 완료)` — **사용자 결정 체크포인트**
- [ ] C8 실측 표를 **사용자에게 보여주고** 함께 확정: ① trend_gate 기본값 ON/OFF,
      ② 강등 규칙(contradiction_only 채택 여부), ③ 윈도우 변경 여부.
      **실측 전에 임의로 기본값을 바꾸지 않는다.**
- [ ] 확정 반영: `config.yaml`(값+의도 주석), `CLAUDE.md` 결정 3 갱신, `00_PROJECT_SPEC.md`,
      `tests/test_synthesize.py`의 trend_gate 토글 테스트를 새 규칙으로 **의도적으로 갱신**
      (Improving 비강등 단언 유지), PROGRESS.md에 M4 완료 기록.
- [ ] **이 파일(M4_PLAN.md) 삭제** — 결정의 영구 기록은 CLAUDE.md/스펙/PROGRESS.md로 이관.

## 완료 기준 (ROADMAP M4)

- [ ] 백테스트가 합성 시계열에서 결정론적으로 동작(테스트).
- [ ] 휩소율 리포트 + trend_gate on/off 비교 + 윈도우 스윕 표.
- [ ] trend_gate 기본값/강등 규칙이 실측 근거와 함께 확정·문서화.
- [ ] 전 출력에 후행성·면책 문구 유지, 단정적 미래 표현 없음. `pytest -q` 네트워크 없이 통과.
