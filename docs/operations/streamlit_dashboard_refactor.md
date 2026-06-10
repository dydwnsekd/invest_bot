# Streamlit Dashboard Refactor Tracker

## 목표

`streamlit_dashboard.py`의 책임을 단계적으로 분리해 파일 크기와 변경 충돌을 줄이고, 중간에 작업이 멈춰도 이 문서를 보고 다음 단계부터 바로 이어서 진행할 수 있게 한다.

## 현재 상태

- 기준 파일: `src/invest_bot/dashboard/streamlit_dashboard.py`
- 기준 시점 파일 크기: 약 1,282 lines
- 현재 파일 크기: 72 lines
- 현재 전략: 동작 변경 없이 안전한 분리부터 순차 진행

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
  - 다중 종목/단일 종목 실행 로직 분리
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

## 검증 로그

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
  - 필요 시 `streamlit_layout.py` 내부 UI 조각을 더 세분화
  - 탭별 시각 회귀 검증을 추가할지 검토
