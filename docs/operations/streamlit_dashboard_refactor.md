# Streamlit Dashboard Refactor Tracker

## 목표

`streamlit_dashboard.py`의 책임을 단계적으로 분리해 파일 크기와 변경 충돌을 줄이고, 중간에 작업이 멈춰도 이 문서를 보고 다음 단계부터 바로 이어서 진행할 수 있게 한다.

## 현재 상태

- 기준 파일: `src/invest_bot/dashboard/streamlit_dashboard.py`
- 기준 시점 파일 크기: 약 1,282 lines
- 현재 파일 크기: 72 lines
- 현재 전략: 분리된 모듈 구조를 유지하면서 사용자 여정 중심 UI로 점진 개편
- 후속 기능 반영: `streamlit_reports.py`가 투자 리포트 단일 본문 흐름, 상단 해석 모아보기 토글, 전략별 판단 요약 렌더링까지 담당
- 현재 공용 차트 경계: `streamlit_charts.py` / `streamlit_state.py`가 투자 리포트·데이터 보기 공용 전문가형 주가 차트와 데이터 조합(`daily_prices_indicators` / `daily_prices` / `investor_daily`)을 담당
- 현재 관심종목 경계: Watchlist는 별도 차트 구현을 두지 않고 report-card 경로를 재사용해 같은 전문가형 차트를 상속
- 현재 용어 해설 경계: `streamlit_glossary.py`가 리포트/전략/지표/수급/데이터 용어집과 추천 순서 안내 카드를 담당
- 현재 해석 모아보기 경계: 독립 메뉴가 아니라 `투자 리포트` 상단 토글 내부에서 `streamlit_interpretations.py` 카드 UI를 호출
- 현재 테마/폰트 소유 경계: `.streamlit/config.toml`과 `src/invest_bot/dashboard/streamlit_styles.py`가 A+ dark terminal theme/font, compact hero, quick-start card를 함께 관리

## 2026-08-01 UI 개편 기록

- `DESIGN.md`를 repo-local source of truth로 추가해 정보 구조, 디자인 원칙, 접근성, 구현 제약을 고정
- `streamlit_layout.py`
  - 메뉴명을 사용자 행동 기준으로 `홈`, `데이터 갱신`, `투자 리포트`, `관심종목`, `백테스트`, `데이터 보기`, `용어 해설`, `시스템 검증`으로 재정리
  - 기존 메뉴명(`상태판`, `작업 실행`, `리포트 해석`, `데이터 탐색`, `검증`)은 `resolve_tab_name()` alias로 유지
  - 선택 메뉴별 hero eyebrow/title/copy를 `TAB_META`에서 렌더링
- `streamlit_overview.py`
  - 홈 안내를 긴 numbered markdown에서 quick-start 카드로 변경
- `streamlit_styles.py`
  - compact hero와 quick-start card 스타일 추가
- 검증
  - `PYTHONPYCACHEPREFIX=/tmp/invest_bot_pycache python3 -m compileall -q ...`
  - `PYTHONPATH=. .venv/bin/pytest tests/test_streamlit_dashboard.py tests/test_streamlit_backtest.py -q` (`96 passed`)
  - `PYTHONPATH=. .venv/bin/pytest -q` (`254 passed`)

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

### 2026-08-02 / Home content investor briefing refresh

- 목표
  - 좌측 메뉴뿐 아니라 우측 홈 본문도 주식 서비스처럼 종목/판단/다음 행동 중심으로 재배치
- 변경 사항
  - `streamlit_overview.py`
    - 최신 리포트/신호 row를 모아 `오늘의 투자 브리핑` 렌더링
    - 매수 관점·상승 추세·전략 매수 신호를 `오늘 볼 만한 종목` 카드로 표시
    - 정기 수집/테스트 상태에 따른 `다음 행동` 카드 추가
  - `streamlit_styles.py`
    - investor briefing, watch target, next action 카드 스타일 추가
  - `DESIGN.md`
    - 홈 본문은 운영 상태보다 종목 중심 브리핑을 먼저 보여주는 원칙 추가
- 참고 비교
  - TradingView watchlist, Seeking Alpha earnings/stock flow, 네이버페이 증권 앱 설명의 관심종목·뉴스·요약 중심 흐름을 참고
- 검증
  - `PYTHONPYCACHEPREFIX=/tmp/invest_bot_pycache python3 -m compileall -q src/invest_bot/dashboard tests/test_streamlit_dashboard.py tests/test_streamlit_backtest.py`
  - `PYTHONPATH=. .venv/bin/pytest -q` (`255 passed`)

### 2026-08-05 / Report, watchlist, backtest content card refresh

- 목표
  - 투자 리포트, 관심종목, 백테스트 우측 본문도 주식 서비스처럼 종목/선택/결과 중심 카드로 정리
- 변경 사항
  - `streamlit_reports.py`
    - 현재 후보 리포트를 `리포트 후보` 카드 grid로 먼저 표시
    - 선택된 리포트 본문을 focus card로 재구성하고 핵심 상태를 meta card로 표시
  - `streamlit_watchlist.py`
    - 관심종목 브리핑 카드와 후보 카드 grid 추가
  - `streamlit_backtest.py`
    - 전략 검증 흐름 카드, 선택 요약 카드, 준비 상태 카드, 결과 카드 추가
  - `streamlit_styles.py`
    - symbol/report/backtest card CSS 추가
  - `DESIGN.md` / README / task docs 반영
- 검증
  - `PYTHONPYCACHEPREFIX=/tmp/invest_bot_pycache python3 -m compileall -q src/invest_bot/dashboard tests/test_streamlit_dashboard.py tests/test_streamlit_backtest.py`
  - `PYTHONPATH=. .venv/bin/pytest -q` (`255 passed`)

### 2026-08-07 / Backtest result interpretation copy

- 목표
  - 백테스트 결과 숫자를 초보자가 바로 이해할 수 있도록 결과 카드에 해석 문장 추가
- 변경 사항
  - `streamlit_backtest.py`
    - `build_backtest_result_interpretation()` 추가
    - 총수익률, 거래 수, 승률, 평균수익, 최대낙폭 기준으로 표본 부족, 손실, 변동성, 낮은 승률/평균수익 해석을 생성
    - 종목/전략별 결과 카드에 해석 문장 표시
  - `streamlit_styles.py`
    - 결과 해석 문장 구분선/문단 스타일 추가
  - `tests/test_streamlit_backtest.py`
    - 표본 부족, 낮은 승률 플러스 수익, 손실/낙폭 케이스 회귀 테스트 추가
- 검증
  - `PYTHONPYCACHEPREFIX=/tmp/invest_bot_pycache python3 -m compileall -q src/invest_bot/dashboard tests/test_streamlit_backtest.py tests/test_streamlit_dashboard.py`
  - `PYTHONPATH=. .venv/bin/pytest -q` (`256 passed`)

### 2026-08-09 / Candidate card direct selection

- 목표
  - 투자 리포트와 관심종목 후보 카드를 본 뒤 selectbox에서 다시 찾지 않아도 바로 본문을 전환할 수 있게 개선
- 변경 사항
  - `streamlit_reports.py`
    - `render_report_candidate_cards()`에 `selection_key`와 `key_prefix` 인자 추가
    - 후보 카드마다 `이 종목 보기` 버튼을 렌더링하고 선택 session state를 갱신
  - `streamlit_watchlist.py`
    - 관심종목 후보 카드도 같은 직접 선택 버튼 사용
  - `tests/test_streamlit_dashboard.py`
    - 후보 카드 버튼이 선택 리포트 key를 갱신하는 회귀 테스트 추가
- 검증
  - `PYTHONPYCACHEPREFIX=/tmp/invest_bot_pycache python3 -m compileall -q src/invest_bot/dashboard tests/test_streamlit_dashboard.py tests/test_streamlit_backtest.py`
  - `PYTHONPATH=. .venv/bin/pytest -q` (`257 passed`)

### 2026-08-09 / Candidate selection state fix

- 문제
  - 후보 카드의 `이 종목 보기` 버튼이 selectbox와 같은 session state key를 직접 변경해 실제 Streamlit 위젯 상태 반영이 불안정할 수 있음
- 수정
  - 버튼 클릭 시 위젯 key를 직접 쓰지 않고 `__candidate_pending` pending key에 선택값 저장
  - 다음 rerun에서 selectbox 생성 전에 pending 값을 실제 선택 key로 해소
  - 투자 리포트와 관심종목 모두 같은 경로 사용
- 검증
  - 후보 카드 버튼이 pending key를 세팅하는 테스트 추가
  - pending 선택값이 selectbox 렌더 전 실제 선택값으로 해소되는 테스트 추가
  - `PYTHONPYCACHEPREFIX=/tmp/invest_bot_pycache python3 -m compileall -q src/invest_bot/dashboard tests/test_streamlit_dashboard.py tests/test_streamlit_backtest.py`
  - `PYTHONPATH=. .venv/bin/pytest -q` (`258 passed`)

### 2026-08-09 / Tab persistence, detail scroll, action progress

- 목표
  - UI 전반 사용감을 개선하기 위해 새로고침 탭 유지, 후보 선택 후 상세 이동, 작업 진행 상태 표시 추가
- 변경 사항
  - `streamlit_layout.py` / `streamlit_dashboard.py`
    - 선택 탭을 `?tab=` query param과 동기화
    - 새로고침 시 query param에서 기존 탭 복원
  - `streamlit_reports.py` / `streamlit_watchlist.py`
    - 후보 카드 버튼 선택값을 pending key로 처리한 뒤 실제 선택값으로 해소
    - 선택 해소 후 상세 영역 anchor로 smooth scroll 실행
  - `streamlit_actions.py`
    - 데이터 수집, 전체 파이프라인, 지표 계산, 신호 생성, 리포트 생성 버튼 실행 중 status/progress copy 표시
  - `tests/test_streamlit_dashboard.py`
    - query param 탭 유지, scroll anchor, action progress 회귀 테스트 추가
- 검증
  - `PYTHONPYCACHEPREFIX=/tmp/invest_bot_pycache python3 -m compileall -q src/invest_bot/dashboard tests/test_streamlit_dashboard.py tests/test_streamlit_backtest.py`
  - `PYTHONPATH=. .venv/bin/pytest -q` (`267 passed`)

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

### 2026-07-25 / Report glossary and embedded interpretation overview

- 목표
  - 사용자가 말한 “해석”을 용어 해설 의미로 재정의하고, 종목/전략 판단 비교는 리포트 해석의 하위 기능으로 정리
- 변경 사항
  - `streamlit_glossary.py` 추가
    - 리포트, 전략, 지표, 수급, 데이터 용어를 검색·분류 조회
    - `DashboardDataService.COLUMN_META` 기반 컬럼 설명도 용어집에 포함
    - 처음 볼 때 추천 순서는 expander가 아닌 안내 카드로 표시
  - `streamlit_reports.py` / `streamlit_interpretations.py`
    - `해석 모아보기` 독립 메뉴 제거
    - `리포트 해석` 상단의 `해석 모아보기 열기` 토글로 종목/전략 판단 비교 제공
    - 긴 텍스트 겹침 방지를 위해 카드 UI와 줄바꿈 CSS 적용
  - `streamlit_styles.py`
    - 해석 카드, 전략 근거 카드, 용어 안내 카드 스타일 추가
    - 화면 안내에서 화살표/아이콘 문자가 텍스트처럼 노출되는 패턴 제거
- 검증
  - `PYTHONPATH=. .venv/bin/pytest tests/test_streamlit_dashboard.py tests/test_streamlit_backtest.py -q`
  - 결과: `94 passed`
  - 전체 테스트는 기존 DB migration schema revision 판정 1건 실패 외 대시보드/문서 변경으로 인한 추가 실패 없음

### 2026-07-29 / Sidebar text navigation and collection default

- 목표
  - 좌측 메뉴를 둥근 박스형 버튼이 아니라 텍스트 중심 내비게이션처럼 보이도록 정리
  - 데이터 수집 기본 조회일수를 365일로 통일
- 변경 사항
  - `streamlit_styles.py`
    - sidebar 메뉴 버튼의 배경, 테두리, 둥근 박스 스타일 제거
    - 선택 메뉴는 왼쪽 얇은 강조선과 밝은 텍스트로만 구분
  - `streamlit_layout.py`
    - sidebar의 `화면 이동` 라벨 제거
  - `collect_market_data.py` / `scheduled_collection.py`
    - 기본 수집일수 `DEFAULT_COLLECTION_LOOKBACK_DAYS`를 365일로 변경
    - 정기 수집 설정에서 `days` 생략 시 365일 사용
  - `config/collection_schedule.yaml.example` / `README.md`
    - 예시 기본 수집일수를 365일로 갱신
- 검증
  - `PYTHONPATH=. .venv/bin/pytest tests/test_domestic_stock_collector.py tests/test_scheduled_collection.py tests/test_streamlit_dashboard.py tests/test_streamlit_backtest.py tests/test_db_migration_artifacts.py -q`
  - 결과: `115 passed`
  - 전체 테스트는 기존 DB migration schema revision 판정 1건 실패 외 추가 실패 없음

### 2026-08-01 / Calendar-based collection period controls

- 목표
  - 작업 실행과 백테스트 준비에서 숫자형 수집 일수 대신 날짜 범위 캘린더로 데이터 조회 기간을 선택
- 변경 사항
  - `streamlit_collection_period.py` 추가
    - 기본 최근 365일 기간 계산
    - 날짜 범위 정규화와 수집 일수 변환 helper 제공
  - `streamlit_actions.py`
    - `수집 일수` number input을 `수집 조회 기간` date range input으로 교체
  - `streamlit_backtest.py`
    - `준비용 수집 일수` number input을 `준비용 수집 조회 기간` date range input으로 교체
  - `README.md` / `docs/tasks/04_dashboard.md`
    - 캘린더 기반 조회 기간 선택 동작 문서화
- 검증
  - `PYTHONPATH=. .venv/bin/pytest tests/test_streamlit_dashboard.py tests/test_streamlit_backtest.py -q`
  - 결과: `95 passed`

### 2026-08-09 / Full watchlist overview

- 목표
  - 관심종목 선택 드롭다운을 열지 않아도 등록한 종목 전체와 최신 판단을 한눈에 확인
- 변경 사항
  - `streamlit_watchlist.py`
    - 리포트가 아직 없는 등록 종목까지 포함해 전체 관심종목을 최대 4열의 compact 카드 보드로 먼저 표시
    - 종목명, 종목코드, 최신 기준일, 최종 의견, 추세를 카드에 노출
    - 카드별 `상세 보기` 버튼으로 기존 단일 리포트 본문과 부드러운 스크롤 이동 경로 연결
    - 검색과 정렬은 전체 목록 아래의 상세 선택 보조 도구로 재배치
  - `streamlit_styles.py`
    - 관심종목 카드와 선택 상태 강조 스타일 추가
  - `DESIGN.md` / `README.md` / `docs/tasks/04_dashboard.md`
    - 드롭다운 비의존 전체 관심종목 확인 원칙과 실제 동작 반영
- 검증
  - `PYTHONPATH=. .venv/bin/pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `99 passed`
  - `PYTHONPATH=. .venv/bin/pytest -q`
  - 결과: `267 passed`

### 2026-08-12 / Home-entry watchlist refresh

- 목표
  - 홈 화면 진입 시 관심종목의 기준일, 추세, 신호, 리포트가 최신 데이터에 맞게 자동 갱신되도록 연결
- 변경 사항
  - `streamlit_dashboard.py`
    - 홈 브리핑 렌더링 전에 DB 관심종목 목록을 로드
    - 기존 관심종목 최신 여부 검사 경로를 재사용해 부족한 가격·수급 데이터만 수집
    - 갱신 대상에 대해 지표 → 신호 → 리포트 파이프라인을 실행하고 snapshot 재구성
    - 관심종목이 이미 최신이면 기존 snapshot을 재사용
    - 검사·갱신 중 등록 종목 수와 처리 내용을 Streamlit status로 표시
  - `DESIGN.md` / `README.md` / `docs/tasks/04_dashboard.md`
    - 홈 진입 자동 최신화와 조건부 수집 원칙 반영
- 검증
  - `PYTHONPATH=. .venv/bin/pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `101 passed`
  - `PYTHONPATH=. .venv/bin/pytest -q`
  - 결과: `267 passed`

### 2026-08-15 / Optional stock-info failure isolation

- 증상
  - 홈 관심종목 최신화 중 KIS 모의투자 `search-stock-info` 요청이 HTTP 500을 반환하면 관심종목 전체 갱신이 중단됨
- 원인
  - 가격 데이터 저장 후 수행하는 선택적 종목 기본정보 조회 예외가 수급 수집과 후속 지표·신호·리포트 단계까지 전파됨
- 변경 사항
  - `streamlit_watchlist.py`
    - 종목 기본정보 조회/저장만 독립 예외 경계로 분리
    - 실패 내용을 warning log로 남기고 투자자 수급 수집과 후속 파이프라인은 계속 실행
  - `tests/test_streamlit_dashboard.py`
    - 종목정보 API 500 상황에서도 수급 저장까지 완료되는 회귀 테스트 추가
- 검증
  - `PYTHONPATH=. .venv/bin/pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `102 passed`
  - `PYTHONPATH=. .venv/bin/pytest -q`
  - 결과: `267 passed`

### 2026-08-15 / Streamlit status icon-font guard

- 증상
  - `관심종목 최신 데이터를 확인하고 있습니다` status의 펼침 화살표가 아이콘이 아니라 Material 아이콘 이름 텍스트로 표시됨
- 원인
  - 앱 전역 `span` 글꼴 규칙이 Streamlit expander 내부 `stIconMaterial`의 ligature 아이콘 글꼴을 덮어쓸 수 있었음
- 변경 사항
  - `streamlit_styles.py`
    - 모든 `[data-testid="stIconMaterial"]`에 Material Symbols 폰트와 `liga` 기능을 우선 적용
    - status/expander 조합에 대한 명시적 보호 selector와 재발 방지 주석 추가
  - `DESIGN.md`
    - 전역 폰트 CSS 변경 시 아이콘 폰트 보존과 텍스트 노출 회귀 테스트를 필수 내부 지침으로 추가
  - `tests/test_streamlit_dashboard.py`
    - `stIconMaterial`, expander 보호 selector, ligature 설정 존재 여부 검증 추가

### 2026-08-17 / Read-only Home trust state and report interpretation

- 배경
  - 홈 진입 중 외부 API 오류와 파이프라인 실행이 발생하면 조회 화면의 상태를 즉시 신뢰하기 어렵고, 사용자가 의도하지 않은 데이터 변경으로 이어질 수 있었음
- 변경 사항
  - `streamlit_dashboard.py` / `streamlit_overview.py`
    - 홈을 저장된 snapshot만 읽는 브리핑 화면으로 전환
    - 리포트·신호 기준일, 데이터 상태, 시스템 검증 실패를 신뢰 상태로 표시
    - 다음 행동 카드에서 `데이터 갱신`, `투자 리포트`, `백테스트`, `시스템 검증`으로 직접 이동
  - `streamlit_reports.py`
    - 후보 카드에 한글 요약, 검색 결과 수, 기준일을 표시
    - 최종 의견과 골든크로스·RSI·추세·평균회귀 전략 신호가 엇갈리면 단독 매매 판단을 피하도록 주의 문구 표시
  - `streamlit_styles.py`
    - status/expander 아이콘 이름 텍스트 노출 방지 범위를 보강하고 키보드 `:focus-visible` 표시 추가
  - `streamlit_overview.py` / `streamlit_reports.py` / `streamlit_watchlist.py` / `streamlit_backtest.py`
    - 여러 `st.markdown()` 호출에 걸쳐 HTML wrapper를 열고 닫던 구조를 제거
    - 위젯을 포함하는 섹션은 Streamlit container로 묶고, 카드 grid는 완결된 HTML 한 번으로 렌더링해 빈 카드·여백을 방지
  - `README.md` / `DESIGN.md` / `docs/tasks/04_dashboard.md` / `docs/analysis/market_report_guide.md`
    - 읽기 전용 홈 정책, 신뢰 상태, 신호 충돌 해석 원칙을 현재 구현과 일치하도록 갱신
- 검증
  - `PYTHONPATH=. .venv/bin/pytest -q`
  - 결과: `278 passed`

### 2026-08-20 / Report decision context and numeric readability

- 변경 사항
  - `streamlit_reports.py`
    - `최종 의견`을 `종합 신호`로 표현하고, 골든크로스·RSI·추세 필터·평균회귀 전략의 매수/관망/매도 건수를 합의도로 표시
    - 핵심 지표 4개와 수급 데이터의 표시 충족 상태를 수익 가능성과 분리해 안내
    - 상승 근거, 위험 요인, 재평가 기준을 전략별 판단 앞에 배치
  - `streamlit_styles.py`
    - 보조 라벨 크기를 높이고 가격·비율·날짜 카드에 tabular 숫자 정렬 적용
    - 리포트 판단 요약을 작은 화면에서도 한 열로 읽을 수 있게 구성
  - `tests/test_streamlit_dashboard.py`
    - 전략 합의도·데이터 충족 상태·상승/위험/재평가 근거 분리 회귀 테스트 추가
- 검증
  - `PYTHONPATH=. .venv/bin/pytest -q`
  - 결과: `281 passed`

### 2026-08-22 / Watchlist data freshness state

- 배경
  - 관심종목을 조회하는 순간 자동 수집·분석·리포트 생성까지 실행하면, 조회와 데이터 변경의 경계가 불명확하고 외부 API 오류가 화면 진입 경험을 방해할 수 있었음
- 변경 사항
  - `streamlit_watchlist.py`
    - 관심종목을 저장된 snapshot 조회 화면으로 전환하고 자동 최신화 호출 제거
    - 가격·수급·분석·신호·리포트의 최신 저장 기준일을 종목별로 비교해 `최신`, `분석 갱신 필요`, `데이터 갱신 필요` 상태와 사유를 표시
    - 갱신 필요 종목을 선택한 채 `데이터 갱신` 탭으로 이동하도록 연결
  - `streamlit_styles.py`
    - 상태별 대비와 기준일을 함께 읽을 수 있는 관심종목 상태 카드 스타일 추가
  - `DESIGN.md` / `docs/tasks/04_dashboard.md`
    - 관심종목 읽기 전용 정책과 명시적 갱신 흐름을 현재 구현에 맞게 갱신
- 검증
  - `PYTHONPATH=. .venv/bin/pytest -q`
  - 결과: `283 passed`
