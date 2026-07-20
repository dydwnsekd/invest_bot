# Streamlit Dashboard Refactor Tracker

## 목표

`streamlit_dashboard.py`의 책임을 단계적으로 분리해 파일 크기와 변경 충돌을 줄이고, 중간에 작업이 멈춰도 이 문서를 보고 다음 단계부터 바로 이어서 진행할 수 있게 한다.

## 현재 상태

- 기준 파일: `src/invest_bot/dashboard/streamlit_dashboard.py`
- 기준 시점 파일 크기: 약 1,282 lines
- 현재 파일 크기: 72 lines
- 현재 전략: 동작 변경 없이 안전한 분리부터 순차 진행
- 후속 기능 반영: `streamlit_reports.py`가 단일 리포트 본문 흐름과 전략별 판단 요약 렌더링까지 담당
- 현재 공용 차트 경계: `streamlit_charts.py` / `streamlit_state.py`가 리포트 해석·데이터 탐색 공용 전문가형 주가 차트와 데이터 조합(`daily_prices_indicators` / `daily_prices` / `investor_daily`)을 담당
- 현재 관심종목 경계: Watchlist는 별도 차트 구현을 두지 않고 report-card 경로를 재사용해 같은 전문가형 차트를 상속
- 현재 테마/폰트 소유 경계: `.streamlit/config.toml`과 `src/invest_bot/dashboard/streamlit_styles.py`가 A+ dark terminal theme/font를 함께 관리

## 진행 원칙

1. 한 단계마다 책임 하나만 분리한다.
2. 각 단계는 가능한 한 무동작 변경으로 유지한다.
3. 단계 종료 시 테스트 결과와 다음 시작 지점을 이 문서에 기록한다.
4. 중간 중단 시 `다음 작업` 섹션의 첫 `TODO`부터 재개한다.

## 단계 계획

### Phase 1. Styles / Formatters 분리

- 목적
  - 대형 CSS 블록 분리
  - 숫자/상태/종목명/리포트 한국어화 포맷터 분리
- 대상
  - `streamlit_styles.py`
  - `streamlit_formatters.py`
- 상태: `DONE`
- 결과
  - 스타일 적용 함수 분리
  - 표시 포맷팅과 한국어화 함수 분리

### Phase 2. Actions 탭 분리

- 목적
  - 작업 실행 UI와 액션 실행 로직을 별도 모듈로 이동
- 대상
  - `streamlit_actions.py`
- 상태: `DONE`
- 결과
  - 액션 탭 렌더링 분리
  - 선택 종목 기준 배치 실행 로직 분리
  - 선택 검증과 액션 메시지 갱신 로직 분리

### Phase 3. Reports 탭 분리

- 목적
  - 리포트 필터링, 카드 렌더링, 신호 카드 로직 분리
- 대상
  - `streamlit_reports.py`
- 상태: `DONE`
- 결과
  - 리포트 해석 탭 렌더링 분리
  - 리포트 필터/정렬 로직 분리
  - 리포트 카드와 신호 카드 렌더링 분리

### Phase 4. Data / Tests / Overview 분리

- 목적
  - 데이터 탐색, 검증 탭, 상태판 요약 컴포넌트 분리
- 대상
  - `streamlit_data.py`
  - `streamlit_tests.py`
  - `streamlit_overview.py`
- 상태: `DONE`
- 결과
  - 상태판 렌더링과 스케줄 상태 패널 분리
  - 데이터 탐색 탭과 데이터셋 미리보기 렌더링 분리
  - 검증 탭 렌더링 분리
  - 테스트 import를 새 모듈 경계에 맞게 정리

### Phase 5. Entry 조립 파일 정리

- 목적
  - `main()`만 남도록 조립 파일 얇게 정리
- 대상
  - `streamlit_dashboard.py`
- 상태: `DONE`
- 결과
  - 레이아웃 렌더링을 `streamlit_layout.py`로 분리
  - 데이터 로딩 헬퍼를 `streamlit_state.py`로 분리
  - `streamlit_dashboard.py`를 엔트리 조립 파일 중심으로 축소

## 작업 로그

### 2026-07-14

- A+ dark trading-terminal theme high-contrast 조정 반영
- 대상 파일
  - `.streamlit/config.toml`
  - `src/invest_bot/dashboard/streamlit_styles.py`
  - `tests/test_streamlit_dashboard.py`
  - `docs/tasks/04_dashboard.md`
  - `docs/operations/streamlit_dashboard_refactor.md`
- 정리 내용
  - Streamlit base theme를 dark로 고정하고 palette token을 `#38bdf8 / #050816 / #111827 / #f8fafc / #475569`로 정리
  - `streamlit_styles.py`를 단일 CSS source of truth로 유지하면서 저대비 teal/navy 조합을 high-contrast dark navy / slate palette로 치환
  - sidebar / hero / card / summary box / tabs / semantic badge 대비를 dark terminal 기준으로 더 선명하게 재조정
  - 한글 가독성 우선 폰트 스택(`Pretendard`, `Noto Sans KR`, `Apple SD Gothic Neo`, `Malgun Gothic`)과 보조 numeric/label fallback(`Inter`, `IBM Plex Sans`)을 반영
  - Material Symbols override는 그대로 유지
  - 문서 기준 동작도 현재 구현에 맞춰 재정리
    - stock dataset 공용 차트는 Plotly 기반 전문가형 주가 차트 경로를 우선 사용
    - 구성: 캔들 + 이동평균선, 거래량, RSI 14, 선택적 수급 panel, `일봉` / `주봉` / `월봉`, shared x-axis hover / zoom
    - 데이터 소스는 기존 저장 `daily_prices_indicators` / `daily_prices` / `investor_daily`만 사용
    - 수급이 비어도 차트는 유지하고 `수급 데이터 없음`만 표시
    - Watchlist는 report-card 렌더링 경로 재사용으로 같은 차트를 상속
- 범위 메모
  - 데이터 / 전략 / 리포트 로직은 변경하지 않음
  - 새로운 기능은 추가하지 않음
- 검증 결과
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_charts.py src/invest_bot/dashboard/streamlit_state.py src/invest_bot/dashboard/streamlit_reports.py src/invest_bot/dashboard/streamlit_data.py src/invest_bot/dashboard/streamlit_watchlist.py tests/test_streamlit_dashboard.py`
  - 결과: `PASS`
  - `PYTHONPATH=src:. .venv/bin/pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `78 passed in 0.70s`
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_styles.py tests/test_streamlit_dashboard.py`
  - 결과: `PASS`
  - `git diff --check -- .streamlit/config.toml src/invest_bot/dashboard/streamlit_styles.py tests/test_streamlit_dashboard.py docs/tasks/04_dashboard.md docs/operations/streamlit_dashboard_refactor.md`
  - 결과: `PASS`


### 2026-06-25

- 후속 리포트 UX 반영
- 대상 파일
  - `src/invest_bot/dashboard/streamlit_reports.py`
  - `src/invest_bot/dashboard/service.py`
- 정리 내용
  - `리포트 해석` 탭을 선택된 1건 중심 본문 흐름으로 고정
  - 리포트 카드에 RSI / Trend Filter / Mean Reversion 전략별 판단과 이유를 표시
  - `market_reports` 데이터셋 메타데이터와 추천 컬럼을 새 전략 필드 기준으로 갱신
- 참고
  - 즐겨찾기 저장은 아직 후속 범위로 남아 있음

### 2026-06-27

- favorites/watchlist 1차 반영
- 대상 파일
  - `src/invest_bot/dashboard/report_favorites.py`
  - `src/invest_bot/dashboard/streamlit_reports.py`
  - `src/invest_bot/dashboard/streamlit_watchlist.py`
  - `src/invest_bot/dashboard/streamlit_dashboard.py`
  - `src/invest_bot/dashboard/streamlit_layout.py`
- 정리 내용
  - symbol 기준 DB-backed favorites persistence helper/adapter로 전환
  - selected report 본문에 즐겨찾기 토글 추가
  - favorites-only filter와 즐겨찾기 우선 정렬 추가
  - 별도 `관심종목` 탭을 추가해 저장된 종목만 다시 선택/확인할 수 있게 구성
  - persistence와 session UI state 경계를 분리
- 참고
  - 1차는 DB-backed 단일 watchlist까지만 반영했고 user/account ownership 확장은 후속 범위로 남아 있음

### 2026-06-27 / Session summary

- 사용자 요구 반영
  - 리포트 단위가 아니라 종목 단위 관심종목으로 관리
  - `리포트 해석` 내 빠른 토글은 유지
  - 별도 확인용 `관심종목` 탭 추가
- 이번 세션 산출물
  - `report_favorites.py` 추가
  - `streamlit_watchlist.py` 추가
  - `streamlit_dashboard.py` 탭 라우팅 확장
  - `streamlit_layout.py` 탭 목록 확장
  - `tests/test_report_favorites.py`, `tests/test_streamlit_dashboard.py` 보강
- 현재 결정 사항
  - 저장 단위는 `symbol`
  - 저장 범위는 DB-backed 단일 watchlist 상태
  - `관심종목` 탭 본문은 한 번에 1개만 표시
- 검증 결과
  - `38 passed in 0.69s`
- 후속 판단 포인트
  - 공유형 watchlist 필요 여부
  - 관심종목 탭에 비교 차트까지 확장할지 여부

### 2026-06-10

- Phase 1 시작
- 목표: styles / formatters 분리
- Phase 1 완료
- 추가 파일
  - `src/invest_bot/dashboard/streamlit_styles.py`
  - `src/invest_bot/dashboard/streamlit_formatters.py`
- 정리 내용
  - 대형 CSS 블록을 `streamlit_styles.py`로 이동
  - 숫자 포맷, 상태 레이블, 종목 표시, 리포트 한국어화 로직을 `streamlit_formatters.py`로 이동
- `streamlit_dashboard.py`는 기존 호출 이름을 유지한 채 외부 모듈 import로 전환
- Phase 2 시작
- 목표: actions 탭 분리
- Phase 2 완료
- 추가 파일
  - `src/invest_bot/dashboard/streamlit_actions.py`
- 정리 내용
  - `작업 실행` 탭 렌더링을 `streamlit_actions.py`로 이동
  - 데이터 수집, 전체 파이프라인, 단일 종목 액션 실행 함수를 이동
  - 종목 선택 검증과 액션 메시지 세팅 로직을 이동
- `streamlit_dashboard.py`는 액션 탭 호출만 담당하도록 축소
- Phase 3 시작
- 목표: reports 탭 분리
- Phase 3 완료
- 추가 파일
  - `src/invest_bot/dashboard/streamlit_reports.py`
- 정리 내용
  - `리포트 해석` 탭 렌더링을 `streamlit_reports.py`로 이동
  - 리포트 엔트리 생성, 필터링, 정렬 함수를 이동
  - 시장 리포트 카드와 골든크로스 신호 카드 렌더링을 이동
  - `streamlit_dashboard.py`는 리포트 탭 호출과 상태판 요약만 유지
- Phase 4 시작
- 목표: data / tests / overview 분리
- Phase 4 완료
- 추가 파일
  - `src/invest_bot/dashboard/streamlit_data.py`
  - `src/invest_bot/dashboard/streamlit_overview.py`
  - `src/invest_bot/dashboard/streamlit_tests.py`
- 정리 내용
  - `상태판` 탭 렌더링과 스케줄 상태 패널을 `streamlit_overview.py`로 이동
  - `데이터 탐색` 탭과 데이터셋 미리보기 렌더링을 `streamlit_data.py`로 이동
  - `검증` 탭 렌더링을 `streamlit_tests.py`로 이동
  - `tests/test_streamlit_dashboard.py`
  - `docs/tasks/04_dashboard.md`
  - `docs/operations/streamlit_dashboard_refactor.md`의 포맷터 import를 새 모듈 경계에 맞게 정리
- Phase 5 시작
- 목표: entry 조립 파일 정리
- Phase 5 완료
- 추가 파일
  - `src/invest_bot/dashboard/streamlit_layout.py`
  - `src/invest_bot/dashboard/streamlit_state.py`
- 정리 내용
  - 사이드바, 헤더, 액션 피드백 렌더링을 `streamlit_layout.py`로 이동
  - 스케줄 상태 로딩, 미리보기 CSV 로딩, 지표 데이터 로딩을 `streamlit_state.py`로 이동
  - `streamlit_dashboard.py`를 72 lines 수준의 엔트리 조립 파일로 축소


### 2026-06-28

- UI clarification pass 반영
- 대상 파일
  - `src/invest_bot/dashboard/streamlit_actions.py`
  - `src/invest_bot/dashboard/streamlit_reports.py`
  - `src/invest_bot/dashboard/streamlit_formatters.py`
  - `src/invest_bot/dashboard/streamlit_data.py`
  - `tests/test_streamlit_dashboard.py`
  - `docs/tasks/04_dashboard.md`
  - `docs/operations/streamlit_dashboard_refactor.md`
- 정리 내용
  - `작업 실행` 탭을 여러 종목 기준 배치 실행 구조로 단순화하고 `한 종목` 섹션 제거
  - `리포트 해석` 탭 상단 metrics strip 제거 및 전략 판단 텍스트 색상화 적용
  - `데이터 탐색` 탭을 종목 선택 기반 summary-first 흐름으로 재구성
  - `unsafe_allow_html` 경로에 대한 escaping 보강과 회귀 테스트 추가
- 검증 결과
  - `39 passed in 0.48s`
- 참고
  - 배치 실행 기본 흐름은 `데이터 수집 -> 지표 계산 -> 신호 생성 -> 리포트 생성`을 여러 종목에 대해 반복 수행하는 방향으로 정리됨

### 2026-07-05

- chart interaction upgrade 반영
- 대상 파일
  - `src/invest_bot/dashboard/streamlit_charts.py`
  - `src/invest_bot/dashboard/streamlit_reports.py`
  - `src/invest_bot/dashboard/streamlit_data.py`
  - `requirements.txt`
  - `tests/test_streamlit_dashboard.py`
  - `docs/tasks/04_dashboard.md`
  - `docs/operations/streamlit_dashboard_refactor.md`
- 정리 내용
  - `리포트 해석` / `데이터 탐색` 탭이 같은 `render_chart_selector` 공용 경로를 계속 사용하도록 유지
  - 공용 차트 렌더러에 Plotly 우선 경로 추가, Altair fallback 유지
  - 날짜 기준 unified hover와 vertical crosshair를 적용해 특정 시점 값 해석 개선
  - 빠른 기간 선택(`1개월`, `3개월`, `6개월`, `1년`, `전체`)과 직접 date range 선택 추가
  - `resolve_range_state` / `apply_time_window` 기반으로 최종 유효 조회 기간을 단일 helper path로 정리
  - preset 변경 후 rerun에서 stale widget state가 다시 덮지 않도록 session-state sync 보정
  - 필터된 조회 기간이 차트 builder 내부에서 다시 90개 포인트로 축소되지 않도록 수정
- 검증 결과
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_charts.py src/invest_bot/dashboard/streamlit_data.py src/invest_bot/dashboard/streamlit_reports.py tests/test_streamlit_dashboard.py`
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `50 passed in 0.65s`
- 결정 메모
  - 1차 범위는 both-tabs shared renderer 유지가 우선
  - chart sync / export / mobile optimization은 이번 변경 범위에서 제외
  - Plotly는 기본 의존성으로 선언했지만 Altair fallback도 당장은 유지

## 검증 로그

### 2026-07-03 / DB watchlist persistence

- 관심종목 persistence 안정화 반영
- 대상 파일
  - `src/invest_bot/db/models.py`
  - `migrations/versions/20260703_000003_add_report_favorite_symbols.py`
  - `src/invest_bot/db/contracts.py`
  - `src/invest_bot/db/repositories.py`
  - `src/invest_bot/dashboard/report_favorites.py`
  - `tests/test_init_db_script.py`
  - `tests/test_report_favorites.py`
  - `tests/test_streamlit_dashboard.py`
  - `docs/tasks/04_dashboard.md`
  - `docs/operations/streamlit_dashboard_refactor.md`
  - `docs/tasks/04_dashboard.md`
- 정리 내용
  - 로컬 JSON 기반 관심종목 저장을 DB-backed 단일 watchlist로 교체
  - `report_favorite_symbols` 테이블과 migration 추가
  - `ReportFavoritesStore`를 DB repository 위의 thin adapter로 유지
  - 기존 `ReportFavoritesStore(Path(...))` 호출 형태 호환 유지
  - duplicate insert race 시 `IntegrityError`를 삼켜 `False`를 반환하도록 보강
  - automatic JSON backfill/import는 추가하지 않음
- 검증 결과
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_report_favorites.py tests/test_init_db_script.py tests/test_streamlit_dashboard.py -q`
  - 결과: `51 passed in 1.64s`
  - `docker compose` web recreate 이후 container 내부 `ReportFavoritesStore().load_symbols()`가 `['005930']` 유지
  - `curl http://127.0.0.1:8000` → `HTTP/1.1 200 OK`
- 결정 메모
  - 1차 범위는 user/account ownership 없는 single global symbol table
  - persistence 매체만 DB로 바꾸고 기존 리포트/관심종목 UX는 유지

### 2026-06-25 / Report UX follow-up

- Host syntax check
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/jobs/generate_market_report.py src/invest_bot/dashboard/streamlit_reports.py src/invest_bot/dashboard/service.py tests/test_market_report_generator.py tests/test_streamlit_dashboard.py tests/test_dashboard_service.py`
  - 결과: `PASS`
- Targeted tests
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_market_report_generator.py tests/test_streamlit_dashboard.py tests/test_dashboard_service.py tests/test_db_frame_storage.py -q`
  - 결과: `33 passed in 0.50s`

### 2026-06-27 / Favorites follow-up

- Host syntax check
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/report_favorites.py src/invest_bot/dashboard/streamlit_reports.py src/invest_bot/dashboard/streamlit_watchlist.py src/invest_bot/dashboard/streamlit_dashboard.py src/invest_bot/dashboard/streamlit_layout.py tests/test_report_favorites.py tests/test_streamlit_dashboard.py`
  - 결과: `PASS`
- Targeted tests
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_report_favorites.py tests/test_streamlit_dashboard.py -q`
  - 결과: `38 passed in 0.69s`

### 2026-06-28 / UI clarification follow-up

- Host syntax check
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_actions.py src/invest_bot/dashboard/streamlit_reports.py src/invest_bot/dashboard/streamlit_formatters.py src/invest_bot/dashboard/streamlit_data.py tests/test_streamlit_dashboard.py`
  - 결과: `PASS`
- Targeted tests
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache .venv/bin/python -m pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `39 passed in 0.48s`

### 2026-06-10 / Phase 1

- Host syntax check
  - `python3 -m py_compile src/invest_bot/dashboard/streamlit_dashboard.py src/invest_bot/dashboard/streamlit_styles.py src/invest_bot/dashboard/streamlit_formatters.py tests/test_streamlit_dashboard.py`
  - 결과: `PASS`
- Container tests
  - `python -m pytest tests/test_streamlit_dashboard.py tests/test_symbol_lookup.py tests/test_dashboard_service.py -q`
  - 결과: `17 passed in 0.45s`

### 2026-06-10 / Phase 2

- Host syntax check
  - `python3 -m py_compile src/invest_bot/dashboard/streamlit_dashboard.py src/invest_bot/dashboard/streamlit_actions.py src/invest_bot/dashboard/streamlit_formatters.py tests/test_streamlit_dashboard.py`
  - 결과: `PASS`
- Container tests
  - `python -m pytest tests/test_streamlit_dashboard.py tests/test_symbol_lookup.py tests/test_dashboard_service.py -q`
  - 결과: `17 passed in 0.41s`

### 2026-06-10 / Phase 3

- Host syntax check
  - `python3 -m py_compile src/invest_bot/dashboard/streamlit_dashboard.py src/invest_bot/dashboard/streamlit_reports.py tests/test_streamlit_dashboard.py`
  - 결과: `PASS`
- Container tests
  - `python -m pytest tests/test_streamlit_dashboard.py tests/test_symbol_lookup.py tests/test_dashboard_service.py -q`
  - 결과: `18 passed in 0.41s`

### 2026-06-10 / Phase 4-5

- Host syntax check
  - `python3 -m py_compile src/invest_bot/dashboard/streamlit_dashboard.py src/invest_bot/dashboard/streamlit_overview.py src/invest_bot/dashboard/streamlit_data.py src/invest_bot/dashboard/streamlit_tests.py src/invest_bot/dashboard/streamlit_layout.py src/invest_bot/dashboard/streamlit_state.py src/invest_bot/dashboard/streamlit_formatters.py tests/test_streamlit_dashboard.py`
  - 결과: `PASS`
- Container tests
  - `python -m pytest tests/test_streamlit_dashboard.py tests/test_symbol_lookup.py tests/test_dashboard_service.py -q`
  - 결과: `18 passed in 0.40s`

## 다음 작업

- 현재 분리 계획 완료
- 후속 개선 후보:
  - user/account ownership을 가진 shared watchlist 확장 필요성 재검토
  - 필요 시 `streamlit_layout.py` 내부 UI 조각을 더 세분화
  - 탭별 시각 회귀 검증을 추가할지 검토

### 2026-07-19 / Report chart and strategy display follow-up

- 목표
  - `리포트 해석` 탭의 전략별 판단을 한글 중심으로 표시
  - 공용 차트 조회 기간 UX와 전문가형 차트 가독성을 보강
- 변경 사항
  - `streamlit_reports.py` / `streamlit_formatters.py`
    - 전략명: `RSI 전략`, `추세 필터 전략`, `평균회귀 전략`
    - 전략 판단 근거의 가격/이동평균 숫자를 천 단위 쉼표 형식으로 표시
  - `streamlit_charts.py`
    - 빠른 조회 기간과 직접 조회 기간 표시를 같은 최종 유효 기간으로 동기화
    - Streamlit date widget state 충돌 방지를 위해 기간별 widget key 사용
    - 전문가형 Plotly 차트 최소 높이와 패널 간격 확대
    - 가격 y축 및 캔들/가격 hover 값을 천 단위 쉼표 형식으로 표시
    - 구분선/가로 y축 범례 실험은 제거하고 기본 y축 제목 방식을 유지
    - 전문가형 차트 trace 구성을 가격/거래량/RSI/수급 패널 helper로 분리
- 검증
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_charts.py src/invest_bot/dashboard/streamlit_formatters.py src/invest_bot/dashboard/streamlit_reports.py tests/test_streamlit_dashboard.py`
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `80 passed`

