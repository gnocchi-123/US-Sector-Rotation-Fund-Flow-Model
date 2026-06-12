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
- [x] 6b. `feat(report): rrg chart with english labels and legend`
      — `report/plot.py`: `plot_rrg` 영어 라벨/제목 + 분면별 plain-language 범례
        (Improving/Leading/Weakening/Lagging 의미 + 후행성 안내 문구).
        합성 데이터로 차트 생성 확인(`/tmp`에 임시 저장 후 삭제).
- [x] 6c. `feat(cli): entry point (M1 완료)`
      — `config.py`: `_REQUIRED_KEYS`/`Config`에 `data.period`/`data.interval`
        (`data_period`/`data_interval`) 추가(CLI 기본값 하드코딩 방지).
      — `cli.py`: `collect_tickers`(벤치마크/섹터/위험선호 페어/거시 티커 합집합), `main`
        (config 로드 → fetch_prices → compute_flow_table/compute_risk_appetite →
        render_report 출력 → `--plot` 시 RRG 차트 저장). 다운로드 실패는 메시지 출력 후
        `sys.exit(1)`로 안전 종료.
      - `pytest -q` 14개 통과. `python -m srm.cli`(콘솔 리포트) 및
        `python -m srm.cli --plot --interval 1wk --period 2y`(차트 생성) 실데이터로
        직접 확인 완료.

**M1 완료.** ROADMAP.md 커밋 1~6 모두 반영됨.

## M2 — 캐시/스냅샷 · 내보내기 · 차트 개선

- [x] 1. `feat(data): parquet price cache (--no-cache / --refresh)`
      — `src/srm/data/cache.py`: `cache_path`(키 = 정렬된 티커 집합 + period + interval +
        오늘 날짜 → sha256 해시, 날짜 변경 시 자동 daily refresh), `load_cached_prices`
        (파일 없으면 `None`, 예외 없음), `save_prices`(parquet 저장).
      — `pyproject.toml`에 `pyarrow` 의존성 추가(parquet I/O).
      — `cli.py`: `--no-cache`(캐시 read/write 모두 생략), `--refresh`(캐시 무시하고
        재다운로드, `--no-cache`가 아니면 결과 재저장) 플래그 추가.
      — `tests/test_cache.py` 4개: `cache_path` 안정성/입력별 변화, 저장→로드 라운드트립
        (parquet은 `DatetimeIndex.freq` 미보존 → `check_freq=False`), 캐시 미스 시 `None`.
      - `pytest -q` 18개 통과(회귀 없음). 실데이터로 1차 실행(다운로드+캐시 저장) →
        2차 실행 "[캐시] 저장된 가격 데이터 사용"(네트워크 미사용) 확인. `--refresh`,
        `--no-cache` 동작도 직접 확인 완료.

- [x] 2. `feat(data): snapshot price data for reproducibility (--from-snapshot)`
      — `src/srm/data/snapshot.py`: `save_snapshot`(가격을 `snapshots/<UTC타임스탬프>/
        prices.parquet` + `meta.json`로 저장, timestamp 자동 기록), `load_snapshot`
        (두 파일을 읽어 복원).
      — `cli.py`: `--from-snapshot PATH`(캐시/다운로드 생략하고 스냅샷 데이터로 리포트
        생성, "[스냅샷] ... 사용 (저장 시각 ...)" 출력), `--no-snapshot`(이번 실행
        결과를 스냅샷으로 저장하지 않음, 기본은 저장).
      — `tests/test_snapshot.py` 2개: 저장→로드 라운드트립(meta에 timestamp 포함),
        **재현성 테스트**(같은 스냅샷을 두 번 로드 → `compute_flow_table`+
        `render_report` 결과 문자열이 완전히 동일).
      - `pytest -q` 20개 통과(회귀 없음). 실데이터로 1회 실행(캐시+스냅샷 생성) →
        `--from-snapshot <경로> --no-snapshot`으로 재실행해 동일 리포트 재현 및
        스냅샷이 추가 생성되지 않음을 확인.

- [x] 3. `feat(report): json/csv export (--export)`
      — `src/srm/report/export.py`: `build_export_payload`(generated_at/interval/
        benchmark/regime/score/max_score/details/ranking/disclaimer를 dict로 묶음),
        `export_json`(들여쓰기 JSON), `export_csv`(랭킹표 CSV).
      — `cli.py`: `--export {json,csv}`(`action="append"`, 반복 지정 가능). 랭킹표가
        비어 있으면 예외 없이 안내 메시지 출력 후 건너뜀. 기본 출력 파일명
        `flow_table.json`/`flow_table.csv`(cwd).
      — `tests/test_export.py` 3개: `build_export_payload` 스키마(키/타입, ranking
        길이, disclaimer 비어있지 않음), `export_json`/`export_csv` 라운드트립.
      - `pytest -q` 23개 통과(회귀 없음). 실데이터로 `--export json --export csv`
        실행해 `flow_table.json`/`flow_table.csv` 생성 및 내용 확인.

- [x] 4. `feat(report): configurable rrg quadrant colors`
      — `report/plot.py`: `DEFAULT_QUADRANT_COLORS`(4분면 배경색 상수화) +
        `plot_rrg(..., quadrant_colors: Mapping[str, str] | None = None)`. 지정한
        분면만 덮어쓰고 나머지는 기본값 유지. 기본 호출 시 기존 출력과 동일.
      — `tests/test_plot.py` 2개: 합성 데이터로 `plot_rrg` 호출 시 파일 생성 확인
        (기본 색상 / `quadrant_colors` 일부 override).
      - `pytest -q` 25개 통과(회귀 없음). 실데이터로 `--plot` 차트 생성 확인.

**M2 완료.** ROADMAP.md 캐시/스냅샷/내보내기/차트 옵션화 4개 작업 모두 반영됨.

## M3 — FRED 선행지표 + 경기 사이클 위치 추정

사전 결정(사용자 확정): ① ISM PMI는 라이선스 문제로 FRED에서 제거됨 →
FRED 대체지표 5종(T10Y2Y/ICSA/PERMIT/UMCSENT/AWHMAN) 기본 + DBnomics ISM PMI
옵션(키 불필요, stale 가드로 정체 시 자동 제외). ② 국면 명칭 = 회복/확장/둔화/수축
(수준×방향 2×2와 1:1 대응). ③ FRED 접근 = 공식 API + `FRED_API_KEY` 환경변수
(무료 발급, 키 없으면 사이클 섹션만 안전 생략).

- [x] 1. `feat(config): optional fred/cycle sections`
      — `config.yaml`: `fred`(series/period_years/dbnomics/stale_months),
        `cycle`(trend_window/level_window/min_indicators/phase_sectors) 옵션 섹션.
      — `config.py`: `_REQUIRED_KEYS` 불변(하위호환), `raw.get()` + 기본값으로 파싱.
        Config에 `fred_series`/`fred_dbnomics`/`fred_period_years`/`fred_stale_months`/
        `cycle_trend_window`/`cycle_level_window`/`cycle_min_indicators`/`phase_sectors`
        필드 추가. `higher_is`는 expansion/contraction만 허용(그 외 ConfigError).
      — `tests/test_config.py`: 섹션 없는 config 하위호환, 섹션 파싱, `higher_is` 검증,
        기본 config.yaml에 M3 섹션 존재 확인.
      - `pytest -q` 29개 통과(회귀 없음).
- [x] 2. `feat(data): fred + dbnomics leading-indicator loaders (network isolated)`
      — `src/srm/data/fred.py`: `fetch_fred_series`(공식 API, 키=환경변수
        `FRED_API_KEY`, 키 없으면 빈 DF로 degrade, 시리즈별 부분 degrade),
        `fetch_dbnomics_series`(키 불필요 보조 소스), `drop_stale_series`
        (마지막 관측이 N개월 이상 오래된 시리즈 제외). urllib(stdlib)만 사용
        — 의존성 추가 없음. 네트워크는 `_request_json` 한 지점에 격리.
      — `tests/test_fred.py` 10케이스: 키 env 읽기, 키 없음→네트워크 미호출+빈 DF,
        FRED "." 결측 파싱, 부분 실패 degrade, DBnomics 파싱/실패, stale 가드.
      - `pytest -q` 39개 통과. **실측**: DBnomics ISM 미러는 2025-12에서 갱신 정체
        + 2025-09 이후 값 손상(≈10) 확인 → stale 가드가 통째로 제외함(설계 적중).
- [x] 3. `feat(signals): cycle phase pure functions`
      — `src/srm/signals/cycle.py`: `classify_cycle_phase`(수준×방향 2×2 →
        Recovery/Expansion/Slowdown/Contraction, rrg.classify_quadrant와 동형),
        `indicator_state`(월말 리샘플 → 수준 z-score(롤링 120개월) + 최근 6개월
        방향, `higher_is=contraction` 부호 반전, 데이터 부족 시 None),
        `compute_cycle_position`(방향 투표 합 + 수준 z 평균 합성, 유효 지표
        `min_indicators` 미만이면 Unknown degrade). 전부 순수함수.
      — `tests/conftest.py`: `expansion_panel`/`contraction_panel` fixture
        (시드 고정, 월간+일간 혼합 주기, drift 크게 — 칼날 경계 단언 회피).
      — `tests/test_cycle.py` 12케이스: 2×2 전수, 방향/반전, Expansion/Contraction
        판정, 빈 입력·지표 부족 degrade, 혼합 주기, 단정 표현 부재 검사.
      - `pytest -q` 51개 통과(회귀 없음).
- [x] 4. `feat(report): cycle section + cli wiring (M3 완료)`
      — `report/synthesize.py`: `render_report(..., cycle=None)` — [4] 거시 참고 뒤에
        "[5] 경기 사이클 위치 (선행지표 합의, 참고용 맥락)" 삽입, 용어 설명은 [6]으로.
        국면 한글 표기(PHASE_KO), 정합 섹터군(참고/추천 아님), 발표지연·개정 한계
        고정 문구(CYCLE_LIMITATION). `cycle=None`이면 생략 안내 한 줄(degrade).
      — `report/export.py`: payload에 `cycle` 키(None이면 null, 있으면 한계 note 포함).
      — `data/snapshot.py`: `save_snapshot(..., extra_frames=)` + `load_snapshot_frame`
        — 선행지표 패널을 스냅샷에 함께 저장해 사이클 섹션까지 재현(하위호환 유지).
      — `cli.py`: `_load_indicators`(캐시 `.cache/fred` → FRED+DBnomics, --no-cache/
        --refresh 공유) + `_compute_cycle`(stale 가드 → compute_cycle_position,
        실패 시 None). 사이클 실패가 본 리포트를 절대 막지 않음.
      — 테스트: `test_report_cycle.py` 3건(사이클 섹션/None degrade/Unknown),
        `test_export.py` +2건(cycle null/note), `test_snapshot.py` +1건(extra_frames).
      - `pytest -q` 57개 통과. **실데이터 검증**(키 미설정 환경): 기존 리포트 정상 +
        [5] Unknown 표시, ISM_PMI stale 제외 메시지, 선행지표 캐시 2회차 재사용,
        스냅샷에 indicators.parquet 포함되어 사이클까지 재현, JSON에 cycle 키 확인.
        FRED 키 설정 시의 5종 지표 실측은 사용자 키 발급 후 확인 예정.

**M3 완료.** ROADMAP.md의 FRED 선행지표/사이클 추정/보고서 섹션 3개 작업 모두 반영됨.
(FRED_API_KEY는 fred.stlouisfed.org에서 무료 발급 → 환경변수로 설정. 미설정이어도
기존 기능은 그대로 동작하고 사이클 섹션만 Unknown/생략으로 degrade.)

- [x] 후속. `feat(config): replace broken ism mirror with regional fed surveys`
      — ISM PMI 무료 입수 경로 전수 실측(2026-06): DBnomics 미러 **값 손상**(2025-09부터
        ≈10) + 갱신 정체(2026-01~), Nasdaq Data Link 404(라이선스 삭제), Trading
        Economics 게스트 중단, ISM 공식 보도자료 로그인 게이트, S&P Global은 헤드라인만
        무료(이력 유료), OECD BCI는 2024-01 중단. → **무료·합법 ISM PMI API 없음** 결론.
      — 대체: 같은 성격(제조업 서베이 확산지수)의 공공 지표인 지역 연준 서베이 2종을
        `fred.series`에 추가 — `GACDFSA066MSFRBPHI`(필라델피아, 1968~),
        `GACDISA066MSFRBNY`(Empire State, 2001~). 둘 다 2026-05까지 갱신 실측 확인.
        코드 변경 없음(config.yaml만). 사이클 판정은 5개 → 7개 지표 합의로 확대.
      — DBnomics ISM_PMI 옵션 제거(`dbnomics: {}`): 손상값인 채 갱신만 재개되면 stale
        가드를 통과해 z-score를 오염시킬 수 있어 선제 제거. `fetch_dbnomics_series`
        코드는 범용 기능이라 유지.
      - `pytest -q` 57개 통과(회귀 없음).

- [x] 후속. `feat(cli): load FRED_API_KEY from local .env file`
      — `cli.py`에 `load_dotenv()`(stdlib only): CLI 시작 시 `.env`를 환경변수로 주입.
        기존 환경변수 우선(덮어쓰지 않음), 파일 없으면 무시. `.env`는 .gitignore에
        이미 포함되어 키가 커밋되지 않음. `tests/test_dotenv.py` 3건.
      - `pytest -q` 60개 통과.

- [x] 후속. FRED 키 검증 완료 (2026-06-11) — `.env` 설정 후 실데이터로 [5] 사이클
      섹션 7종 지표 출력·캐시 재사용·스냅샷 포함 확인. 국면 Contraction(z -0.11) 판정.

## M1~M3 리뷰 보완 (M4 사전 정비)

전 모듈 리뷰(2026-06-11)에서 나온 보완 1~3 처리:

- [x] 1. `test: flow score/table unit tests + rrg benchmark-missing degrade fix`
      — `tests/test_synthesize.py`: 결정 2(가중 합산) 전수 파라미터화, Improving>Leading
        의도 편향 부등식, rotation 순서, trend_gate 토글 동일성(M4에서 강등 규칙 추가 시
        의도적으로 갱신할 것), 랭킹표 스키마/정렬/RS-Ratio 반면/점수 자기일관성, degrade 2종.
      — 테스트가 드러낸 버그 수정: **벤치마크 티커 누락 시 `compute_rrg`가 KeyError로
        죽던 것**을 빈 DataFrame degrade로 수정(`signals/rrg.py`).
- [x] 2. `fix(report): cycle last_obs shows actual observation date`
      — `signals/cycle.py`: 월말 리샘플 라벨(06-30처럼 미래로 보임) 대신 원 시계열의
        실제 마지막 관측일 표기. 실데이터로 06-10/04-01 등 정확한 날짜 확인.
- [x] 3. `feat(config): extend fred history to 15y for stable level z-score`
      — `period_years` 10→15: level_window(120개월)와 같으면 z-score가 항상 불완전
        윈도우(min_periods)로 계산되던 것을 해소.
- `pytest -q` 115개 통과. 실데이터 재검증 완료.

리뷰에서 나온 나머지 항목은 M4로 이월: 하드코딩 잔재(risk `iloc[-5]`, 거시 `iloc[-5]`),
`compute_rrg` 중복 계산(rs_series 헬퍼와 함께), 사이클 z~0 칼날 경계(휩소 측정 대상에
포함), 캐시/스냅샷 정리, risk_pairs 형식 검증.

## M4 — 백테스트 훅 + 휩소(가짜신호) 리포트

상세 계획: `M4_PLAN.md` (커밋 C1~C9). 완료 시 결정을 CLAUDE.md/스펙에 반영하고 삭제.

- [x] C1. `refactor(signals): extract rs_series + reuse rrg in cli`
      — `signals/rrg.py`: `rs_series`(한 티커의 RS-Ratio/RS-Momentum 전체 시계열,
        티커/벤치마크 없으면 None) 분리, `compute_rrg`는 이를 호출(출력 불변).
        백테스트 분면 이력 추적과 공유할 단일 정의.
      — `report/synthesize.py`: `compute_flow_table(..., rrg=None)` 재사용 허용.
      — `cli.py`: RRG 1회 계산해 랭킹표/`--plot` 공유(M1~M3 리뷰 이월 항목 해소).
      — `tests/test_rrg.py` +2건: rs_series↔compute_rrg 마지막 값 일치, 누락 시 None.
      - `pytest -q` 117개 통과(기존 테스트 무변경 회귀 가드).

- [x] C2. `refactor(config): externalize remaining hardcoded lookbacks`
      — `config.yaml` `windows`에 `risk_slope: 5`/`macro_lookback: 5`(프로토타입
        iloc[-5] 그대로, 의미 주석). `config.py`는 옵션 필드(기본 5, 하위호환 —
        dataclass 기본값 순서 제약으로 M3 옵션 섹션 앞에 배치).
      — `risk.py`: `ratio_score(..., slope=5)`/`compute_risk_appetite(..., slope=5)`,
        `synthesize.py` [4] 라벨을 실제 의미("N-1봉 전 대비")로 정정, `cli.py` 연결.
      — 테스트 +2건: config 기본값/파싱, ratio_score slope 파라미터화(0 vs -1).
      - `pytest -q` 119개 통과.

- [x] C3. `feat(config): backtest options section`
      — `config.yaml` `backtest:` 옵션 섹션(horizon 4 / min_history 60 /
        window_candidates [8,10,14,20,26]) + "수익률 백테스트가 아님" 주석.
      — `config.py`: `backtest_horizon`/`backtest_min_history`/
        `backtest_window_candidates`(tuple) — 섹션 없으면 기본값(하위호환).
      — 테스트 +2건: 기본값/파싱, 레포 config 후보에 현행 rs_window 포함.
      - `pytest -q` 121개 통과.

- [x] C4. `feat(backtest): quadrant/trend history pure functions`
      — 신규 `src/srm/backtest/walk.py`: `quadrant_history`(rs_series+
        classify_quadrant를 시점별 적용, NaN 결측/티커 제외 degrade),
        `trend_history`(trend_state 동일 규칙의 시점별 판정), `transitions`
        ((time,from,to) 전환 기록, 결측 건너뜀). 전부 순수함수.
      — `tests/test_walk.py` 5건: 결정론성, 마지막 시점 compute_rrg/trend_state
        일치(분면 자체 비단언 — M1 교훈), 결측 사이 동일 라벨 비전환, degrade.
      - `pytest -q` 126개 통과.

- [x] C5. `feat(backtest): whipsaw metrics + trend-gate candidate comparison`
      — 신규 `src/srm/backtest/whipsaw.py`: `whipsaw_rate`(전환 후 horizon봉 내
        직전 라벨 복귀 비율, per_ticker/total, 전환 0건은 None — NaN 금지),
        `apply_gate`(후보 규칙 none/contradiction_only — 모순 조합
        Leading+Downtrend/Weakening+Uptrend/Lagging+Uptrend만 0 강등,
        **Improving은 항상 제외**), `score_sign_stability`(FlowScore 부호
        pos/zero/neg 시계열의 휩소율을 규칙별 비교; rotation 성분은 모멘텀
        시계열이 필요한 ±0.5 보조 신호라 제외 — 주석 명시).
      — `tests/test_whipsaw.py` 10건: 전환·복귀 비율, horizon 경계, 결측 건너뜀,
        Improving 비강등, 미지 규칙 ValueError, 규칙별 차이 발생, degrade.
      - `pytest -q` 136개 통과.

- [x] C6. `feat(backtest): window sweep`
      — 신규 `src/srm/backtest/sweep.py`: `sweep_windows` — 후보 윈도우별
        (rs=mom 동일값) quadrant_history 재계산 → whipsaw_rate total을 행으로.
        컬럼 window/transitions/whipsaws/rate. 이력 비면 전환 0/None degrade.
      — `tests/test_sweep.py` 2건: 결정론성/후보 수만큼 행/전환 발생, degrade.
      - `pytest -q` 138개 통과.

- [x] C7. `feat(report): cycle borderline note + backtest report rendering`
      — `synthesize.py`: `CYCLE_BORDERLINE_Z = 0.25` — 사이클 수준 z 평균이 0
        근처면 국면에 "(경계 근처 — 판정이 바뀌기 쉬움)" 추가(칼날 경계 이월 항목).
      — 신규 `report/backtest_report.py`: `render_backtest_report` — [1] 섹터별
        분면 휩소율 / [2] 게이트 후보 비교(규칙 설명 + Improving 비강등 안내) /
        [3] 윈도우 스윕(현행 표식). "수익률 백테스트가 아닙니다" 헤더, 안정성
        서술만, rate None은 "n/a (전환 없음)", 하단 cfg.disclaimer.
      — 테스트 +5건: 섹션/면책, 단정 표현 부재(수익은 부정 맥락만 허용),
        빈 입력 degrade, n/a 포맷, 사이클 경계 문구 on/off.
      - `pytest -q` 143개 통과.

- [x] C8. `feat(cli): --backtest flag (신호 안정성 리포트)`
      — `cli.py`: `--backtest` 플래그 + `_run_backtest`(min_history 가드,
        walk→whipsaw→gate 비교→sweep→render, 호출부 try/except — 어떤 실패도
        본 리포트를 막지 않음). 가격 로드는 기존 캐시/스냅샷 경로 공유.
      — **실측**(주봉 2y/5y, 일관됨): ① 분면 휩소율 전체 70%(섹터별 59~79%).
        ② 게이트 비교: none 79%/77% vs contradiction_only 81%/81% — 전환 수는
        소폭 줄지만 휩소율은 오히려 상승(부호 안정성 개선 없음).
        ③ 윈도우 스윕: 8→26으로 갈수록 전환 수는 감소(1684→1455), 휩소율은
        상승(65%→78%). 현행 14는 중간(70%, 절대 휩소 수 최소 구간).
      - `pytest -q` 143개 통과.

- [x] C9. `feat: trend_gate default decision (M4 완료)` — **사용자 확정(2026-06-12)**
      ① trend_gate 기본값 **OFF 유지** — 실측상 게이트가 부호 휩소율을 77~79%→81%로
        올려 안정성 개선 근거 없음. ② ON 시 강등 규칙 **contradiction_only 채택** —
        모순 조합(Leading+Downtrend, Weakening/Lagging+Uptrend)만 0점 강등,
        Improving은 항상 제외. 단일 정의는 `backtest/whipsaw.py`의 `apply_gate`이며
        `compute_flow_score`가 trend_gate ON일 때 이를 호출. ③ RRG 윈도우 **14 유지**
        — 스윕상 균형점(짧으면 전환 과다, 길면 휩소율 상승).
      — 반영: `config.yaml`(trend_gate 주석에 실측 근거), `CLAUDE.md` 결정 3,
        `00_PROJECT_SPEC.md`(Layer 3/종합/로드맵), `tests/test_synthesize.py`의
        토글 테스트를 새 규칙으로 의도적 갱신(Improving 비강등 단언 유지).
      — `M4_PLAN.md` 삭제(결정의 영구 기록은 CLAUDE.md/스펙/이 파일로 이관).
      - `pytest -q` 144개 통과.

**M4 완료.** ROADMAP.md의 백테스트 훅/휩소 리포트/게이트·윈도우 확정 모두 반영됨.

## M4 후속 — 리뷰 잔여 이월 항목 정리

- [x] 1. `feat(config): validate risk_pairs format`
      — `config.py`: `_parse_risk_pairs` — 각 항목이 [분자, 분모] 티커 문자열
        2개인지 검증, 아니면 IndexError 대신 명확한 ConfigError.
      — `tests/test_config.py` +6건: 길이/타입/빈 문자열/비매핑 케이스.
      - `pytest -q` 150개 통과.

- [x] 2. `feat(data): cache/snapshot retention policy`
      — `config.yaml` `data`에 옵션 키 `cache_keep_days: 7`/`snapshot_keep: 20`
        (0 = 정리 끄기), `config.py` 기본값 파싱(하위호환).
      — `cache.py`: `prune_cache` — 새 저장 시 mtime이 keep_days보다 오래된
        캐시 파일 삭제(키에 날짜가 들어가 하루마다 쌓이는 문제 해소).
      — `snapshot.py`: `prune_snapshots` — 타임스탬프순 최신 N개만 보관.
        meta.json 있는 디렉터리만 스냅샷으로 간주(오삭제 방지). 둘 다 삭제 실패
        무시(degrade), 삭제 목록 반환.
      — `cli.py`: 가격/선행지표 캐시 저장 후 + 스냅샷 저장 후 정리 호출,
        삭제 시 "[정리] ..." 메시지.
      — 테스트 +5건(config 1, cache 2, snapshot 2): 오래된 것만 삭제, 끄기/
        디렉터리 없음/한도 이내 degrade.
      - `pytest -q` 155개 통과. 실데이터 확인: 10일 묵은 캐시 파일이
        "[정리] 오래된 가격 캐시 1개 삭제"로 정리됨.

**리뷰 이월 항목 전부 처리 완료.**

## 다음 작업

1. 마일스톤 M1~M4 + 이월 항목 완료 — 이후 작업은 새 요구사항 발생 시
   스펙/ROADMAP 갱신부터.
