# PROGRESS — 진행 기록

> 단일 기준은 `00_PROJECT_SPEC.md`(스펙)와 `ROADMAP.md`(마일스톤 작업 지침)다.
> 이 파일은 그 기준에 따라 "지금까지 뭘 했고, 다음에 뭘 할지"를 빠르게 보기 위한
> 진행 로그다. 매 커밋마다 체크리스트와 "다음 작업" 절을 갱신한다.

## M1 — 골격화 + config 외부화 + 단위테스트

ROADMAP.md의 커밋 분할 예시(1~6) 기준 진행 상황:

- [x] 1. `chore: repo skeleton + pyproject + config.yaml` (`dcd36b4`)
      — src/srm 패키지 골격, pyproject.toml, config.yaml(티커/윈도우/가중치/임계값/면책문구).
- [x] 2. `feat(config): config loader` (`5b68b24`)
      — `src/srm/config.py`: config.yaml -> 불변 `Config`(frozen dataclass), 필수 키 검증.
- [x] 3. `feat(data): yfinance loader (network isolated)` (`7567c5e`)
      — `src/srm/data/loader.py`: `fetch_prices()` 이식. yfinance import는 함수 내부로 격리,
        전부 NaN인 티커 컬럼은 제거(degrade).
- [x] 4. `feat(signals): rrg / risk / trend pure functions` (`75a1ad0`)
      — `src/srm/signals/{rrg,risk,trend}.py`에 프로토타입 계산 로직 이식.
        - `rrg.py`: `_zscore_normalize`, `classify_quadrant`(4분면 분류 분리, 결정 1 주석),
          `compute_rrg`.
        - `risk.py`: `ratio_score`, `compute_risk_appetite`(임계값 `risk_on`/`risk_off`를
          인자로 파라미터화).
        - `trend.py`: `trend_state` (그대로 이식, n/a degrade 포함).
        - 모두 순수함수, config/네트워크 의존 없음.
- [x] 5. `test: synthetic-data unit tests (no network)` — **이번 작업**
      — `tests/conftest.py`(시드 고정 random-walk 합성 가격 패널 `price_panel`,
        데이터 부족 검증용 `short_price_panel`) + `tests/test_{rrg,risk,trend}.py`.
        - RRG: `classify_quadrant` 100 경계 4종 + `compute_rrg`의 RS-Ratio 부호(모멘텀/분면
          비단언) + 빈 결과 처리.
        - Risk: `ratio_score`의 1/-1/0/None 4종 + `compute_risk_appetite`의 ±2 임계값
          (RISK-ON/OFF/MIXED/Unknown) + 임계값 파라미터화 검증.
        - Trend: Uptrend/Downtrend/Neutral(눌림목)/n/a(티커 없음)/n/a(데이터 부족).
        - `pytest -q` 14개 통과(네트워크 없음).
- [x] 6a. `feat(report): synthesize composite score and report text`
      — `src/srm/report/synthesize.py`: `compute_flow_score`(quad_flow + rotation 부호 +
        trend, 결정 2; trend_gate는 토글만 존재하고 M1은 ON/OFF 동일, 강등 규칙은 M4로
        보류, 결정 3), `compute_flow_table`(섹터별 RRG/추세/FlowScore 랭킹표),
        `render_report`(콘솔 텍스트 보고서 — 일반인용 `[5] 용어 설명`/4분면 범례 신규
        추가, 면책문구는 `cfg.disclaimer`).
      - `pytest -q` 14개 통과(회귀 없음, 새 테스트는 ROADMAP상 이번 커밋 범위 아님).
- [ ] 6b. `feat(report): rrg chart with english labels and legend` — **다음 작업**
      — `report/plot.py`: `plot_rrg` 영어 라벨 + 분면 의미 범례.
- [ ] 6c. `feat(cli): entry point (M1 완료)`
      — `config.py`에 `data.period`/`data.interval` 추가, `cli.py`(`collect_tickers`,
        `main`)로 fetch → synthesize → (옵션) plot 연결.

**M1 마무리 권장 작업(ROADMAP)**: ruff/black 1회 정리, 실데이터 1회 실행 확인,
`_ratio_series`/`_mom_series` 접근자 분리 여부 검토(선택).

## 다음 작업 (커밋 6a 이후)

1. 커밋 6b: `report/plot.py` (영어 라벨 RRG 차트 + 분면 범례).
2. 커밋 6c: `config.py`(data 섹션) + `cli.py` — M1 완료.
3. M2: parquet 캐시, 스냅샷/재현성, JSON/CSV export, 차트 옵션화.
4. M3: FRED 선행지표 + 경기 사이클 위치 추정.
5. M4: 백테스트 훅, 휩소율 리포트, `trend_gate` 기본값/강등 규칙 확정, 윈도우 튜닝.
