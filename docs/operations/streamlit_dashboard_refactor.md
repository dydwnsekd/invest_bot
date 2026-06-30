# Streamlit Dashboard Refactor Tracker

## 목표

`streamlit_dashboard.py`의 책임을 단계적으로 분리해 파일 크기와 변경 충돌을 줄이고, 중간에 작업이 멈춰도 이 문서를 보고 다음 단계부터 바로 이어서 진행할 수 있게 한다.

## 현재 상태

- 기준 파일: `src/invest_bot/dashboard/streamlit_dashboard.py`
- 기준 시점 파일 크기: 약 1,282 lines
- 현재 파일 크기: 72 lines
- 현재 전략: 동작 변경 없이 안전한 분리부터 순차 진행
- 후속 기능 반영: `streamlit_reports.py`가 단일 리포트 본문 흐름과 전략별 판단 요약 렌더링까지 담당

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
  - symbol 기준 local favorites persistence helper 추가
  - selected report 본문에 즐겨찾기 토글 추가
  - favorites-only filter와 즐겨찾기 우선 정렬 추가
  - 별도 `관심종목` 탭을 추가해 저장된 종목만 다시 선택/확인할 수 있게 구성
  - persistence와 session UI state 경계를 분리
- 참고
  - DB-backed shared watchlist는 아직 후속 범위로 남아 있음

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
  - 저장 범위는 로컬 단일 사용자 상태
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
  - `tests/test_streamlit_dashboard.py`의 포맷터 import를 새 모듈 경계에 맞게 정리
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
- 정리 내용
  - `작업 실행` 탭을 여러 종목 기준 배치 실행 구조로 단순화하고 `한 종목` 섹션 제거
  - `리포트 해석` 탭 상단 metrics strip 제거 및 전략 판단 텍스트 색상화 적용
  - `데이터 탐색` 탭을 종목 선택 기반 summary-first 흐름으로 재구성
  - `unsafe_allow_html` 경로에 대한 escaping 보강과 회귀 테스트 추가
- 검증 결과
  - `39 passed in 0.48s`
- 참고
  - 배치 실행 기본 흐름은 `데이터 수집 -> 지표 계산 -> 신호 생성 -> 리포트 생성`을 여러 종목에 대해 반복 수행하는 방향으로 정리됨

## 검증 로그

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
  - DB-backed shared watchlist 필요성 재검토
  - 필요 시 `streamlit_layout.py` 내부 UI 조각을 더 세분화
  - 탭별 시각 회귀 검증을 추가할지 검토
