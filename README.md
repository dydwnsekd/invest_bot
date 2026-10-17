# invest_bot

국내주식 데이터를 수집하고, 지표를 계산하고, 전략 신호와 시장 리포트를 생성해 확인할 수 있는 Python 기반 자동매매 연구 프로젝트입니다.

프로젝트 지식은 [OKF 규약](OKF.md)에 따라 관리합니다. [지식 홈](docs/README.md)에서 현재 기준 문서·개념·작업 상태·과거 기록을 구분해 찾아볼 수 있습니다.

현재는 실거래 자동화보다 아래 흐름을 안정적으로 만드는 데 초점을 두고 있습니다.

1. 데이터 수집
2. DB snapshot 저장
3. 지표 계산
4. 전략 신호 생성
5. 시장 리포트 생성
6. 대시보드 확인
7. 테스트 기반 검증

## 현재 구현 범위

### 차트 summary 수급 연결 (2026-10-13 구현)

날짜별 상세 수급을 사용할 수 없으면 저장된 summary의 실제 관측일·순매수로 차트를 표시합니다. 누락이나 날짜 불일치는 값을 만들지 않고 이유를 안내하며, 주·월봉에서도 미관측과 실제 0을 구분합니다. 관련199개·기본832개와 가상 데이터 실제 브라우저를 검증했습니다. QA 세션은 사용량 제한으로 중단돼 메인이 경계 검증을 보완했으며 별도 독립 판정은 미완료입니다. [검증 기록](docs/tasks/04_dashboard.md#차트-summary-수급-연결-2026-10-13), [현재 개선 순서](docs/operations/improvements/README.md)를 참고하세요.

2026-10-14 G05a의 코드·회귀·관련 문서를 기능 단위로 main에 반영했습니다. 커밋 범위만 격리한 재검증에서도 관련199개·기본832개가 통과했습니다.

9월 snapshot 재조회 축소·frame 재사용·백테스트 이력 분리·수집 실패 표시 개선은 이후 main에 반영됐습니다. 당시 `390 passed, 1 deselected`는 해당 변경의 과거 증거이며 [9월 검증 기록](docs/operations/session_reports/2026-09-19_dashboard.md)에 남아 있습니다.

### 개선 작업 통합 진행 중 (2026-09-15)

- 수급의 유효한 여러 거래일과 기존 종목 메타데이터를 보존하고, 실패 시 이미 저장한 결과를 보고
- 백테스트 요약의 최대 낙폭·최종자산·총수익률을 일별 평가금액 곡선 기준으로 통일
- 시장 리포트 공통 기준일 도입 및 CSV 숫자형 날짜·주말 수급 관측일 처리 보완
- DB migration과 외부 종목 마스터 초기화를 분리하고 scheduler/web 로그 경로를 공유
- 기본 테스트를 임시 설정·DB로 격리하고 Python 3.13 CI 및 별도 PostgreSQL 검증 추가
- 역할별 범위와 통합 검증 기록: [개선 작업 계획](docs/operations/improvement_sessions_2026-09-13.md)

### 이번 세션 업데이트 (2026-09-13)

- 대시보드 실행 계획의 0~7단계 완료
  - 종목 비교 차트, 일별 평가금액 곡선, 저장된 백테스트 이력 재불러오기
  - 제한된 전략 실험 설정, 복수 전략 조합(AND / OR / 가중치), 다종목 포트폴리오 집계
  - 현재 브라우저 세션 한정 화면 설정 저장·적용·초기화
- 탭 왕복 중 Streamlit 위젯 상태가 정리돼도, 현재 탭의 누락된 설정만 안전하게 복원
- 관련 검증 완료
  - `PYTHONPATH=. .venv/bin/pytest -q` (`342 passed`)

### 이번 세션 업데이트 (2026-08-20)

- 투자 리포트의 의견 해석을 단일 매수/매도 결론에서 판단 상태 중심으로 보강
  - 종합 신호 옆에 전략 합의도(매수·관망·매도 건수)와 핵심 지표·수급 데이터 충족 상태를 표시
  - 상승 근거, 위험 요인, 재평가 기준을 분리해 전략 신호의 방향과 한계를 함께 확인
  - 수익 가능성의 신뢰도를 추정하지 않고, 실제 표시 데이터와 전략 신호만 설명
- 숫자·날짜 카드에 tabular 숫자 정렬을 적용하고 보조 글자 크기를 높여 스캔 가독성 개선
- 관련 검증 완료
  - `PYTHONPATH=. .venv/bin/pytest -q` (`281 passed`)

### 이번 세션 업데이트 (2026-08-17)

- 홈을 저장된 snapshot을 읽는 브리핑 화면으로 전환
  - 홈 진입 시 외부 API 호출이나 데이터 수집·지표·신호·리포트 생성을 실행하지 않음
  - 리포트·신호 기준일, 데이터 상태, 시스템 검증 실패 여부를 함께 표시하고 필요한 경우 `데이터 갱신`으로 안내
  - 다음 행동 카드를 실제 `데이터 갱신`, `투자 리포트`, `시스템 검증`, `백테스트` 화면 이동 버튼으로 연결
- 투자 리포트 해석 보강
  - 후보 카드에 한글 요약, 결과 수, 날짜만 표시해 읽기 흐름을 단순화
  - 최종 의견과 골든크로스·RSI·추세·평균회귀 전략 신호가 엇갈리면 단독 매매 판단을 피하도록 경고
- Streamlit status/expander 아이콘 이름 텍스트 노출 방지와 키보드 포커스 표시 보강
- 분리된 HTML 카드 wrapper로 생기던 빈 테두리·여백 영역 제거
- 관련 검증 완료
  - `PYTHONPATH=. .venv/bin/pytest -q` (`278 passed`)

### 이번 세션 업데이트 (2026-08-01)

- 대시보드 1차 UI 구조를 사용자 여정 중심으로 재정리
  - 우측 홈 본문을 `오늘의 투자 브리핑`, `오늘 볼 만한 종목`, `다음 행동` 중심으로 재배치
  - 투자 리포트·관심종목·백테스트 우측 본문도 후보/선택/준비/결과 카드 중심으로 재구성
  - 탭 새로고침 유지, 후보 카드 선택 후 상세 영역 스크롤, 작업 실행 중 진행 상태 표시 추가
  - 좌측 메뉴명을 `홈`, `데이터 갱신`, `투자 리포트`, `데이터 보기`, `시스템 검증`처럼 사용 목적이 드러나는 이름으로 변경
  - 기존 세션/테스트 호환을 위해 예전 메뉴명(`상태판`, `작업 실행`, `리포트 해석`, `데이터 탐색`, `검증`)은 내부 alias로 계속 처리
  - 선택한 메뉴에 따라 상단 hero 문구가 바뀌도록 개선
  - 홈의 추천 순서를 번호 카드형 quick-start로 바꿔 처음 보는 사용자가 다음 행동을 바로 고를 수 있게 정리
- UI 개편 기준 문서 `DESIGN.md` 추가
  - 정보 구조, 디자인 원칙, 접근성, Streamlit 구현 제약을 source of truth로 기록
- 관련 검증 완료
  - `PYTHONPATH=. .venv/bin/pytest -q` (`267 passed`)

### 이번 세션 업데이트 (2026-07-25)

- `용어 해설` 탭 추가
  - 리포트, 전략, 지표, 수급, 데이터 용어를 한 화면에서 검색하고 분류별로 확인
  - `DashboardDataService.COLUMN_META`의 컬럼 설명도 용어집에 자동 포함
  - 처음 볼 때 추천 순서는 화살표/아이콘 없이 안내 카드로 표시
- `해석 모아보기`는 독립 메뉴가 아니라 현재 `투자 리포트` 탭 상단 토글로 제공
  - 현재 리포트 검색 조건에 맞는 종목들의 최종 의견과 전략별 판단을 카드형으로 비교
  - 긴 해석 문장과 전략 판단 근거는 줄바꿈 가능한 카드 UI로 표시해 텍스트 겹침 방지
  - expander 화살표 아이콘이 텍스트처럼 보이지 않도록 상단 토글 방식 사용

### 이번 세션 업데이트 (2026-07-20)

- 대시보드에 전용 `백테스트` 탭 추가
  - `준비 확인 -> 준비 실행 -> 백테스트 실행 -> 결과 확인` 흐름으로 분리
  - 준비 상태 panel이 선택한 종목/전략 조합별 실행 가능 여부와 차단 사유를 바로 표시
  - 실행 결과는 전략 요약 카드, 비교표, 거래 순서 누적 수익률 차트, 거래 로그로 확인
- 백테스트 전략 adapter/registry를 7개 전략 기준으로 고정
  - `golden-cross`
  - `rsi`
  - `trend-filter`
  - `mean-reversion`
  - `disparity`
  - `momentum`
  - `investor-flow-custom`
- 백테스트 persistence identity 정리
  - 산출물 파일명은 `symbol` 우선 규칙으로 저장
  - 공통 실행 식별자는 `run_group_id`, `run_id`
  - summary에는 input provenance 필드와 `input_sources_json`을 함께 기록
- `데이터 탐색` 탭은 구조를 바꾸지 않음
  - generic Data tab은 종목별 최신 artifact 1건만 보일 수 있음
  - 같은 세션 안 여러 전략 비교는 `백테스트` 탭 결과를 source of truth로 사용

### 이번 세션 업데이트 (2026-07-19)

- `리포트 해석` 탭의 전략별 판단 표시를 한글 중심으로 정리
  - `RSI 전략`, `추세 필터 전략`, `평균회귀 전략`으로 표시
  - 전략별 판단 근거 문장의 가격/이동평균 값은 천 단위 쉼표 형식으로 표시
- 공용 차트 조회 기간 UX 보강
  - `조회 기간 방식`에서 빠른 선택과 직접 지정을 명확히 분리
  - 빠른 선택 기간과 직접 조회 기간 표시가 같은 유효 기간을 보도록 동기화
  - Streamlit date widget state 충돌을 피하도록 조회 기간별 widget key를 분리
- 전문가형 Plotly 차트 가독성 조정
  - 차트 최소 높이와 패널 간격 확대
  - 가격 y축과 캔들/가격 hover 값은 `1,000` 형식으로 표시
  - 구분선/가로 y축 범례 실험은 제거하고 기본 y축 제목 방식을 유지
- 관련 검증 완료
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_charts.py src/invest_bot/dashboard/streamlit_formatters.py src/invest_bot/dashboard/streamlit_reports.py tests/test_streamlit_dashboard.py`
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_streamlit_dashboard.py -q` (`80 passed`)

### 이전 세션 업데이트 (2026-07-14)

- `리포트 해석` / `데이터 탐색` 공용 주가 차트가 stock dataset에서 전문가용 차트 경로를 사용
  - 캔들 + 이동평균선, 거래량, RSI 14, 선택적 투자자 수급 panel을 함께 표시
  - `일봉` / `주봉` / `월봉` 전환과 shared x-axis hover / zoom을 지원
  - 기존 저장 데이터(`daily_prices_indicators` / `daily_prices` / `investor_daily`)만 사용하며 새 수집/API 호출은 추가하지 않음
  - 수급 데이터가 없으면 차트는 계속 표시되고 `수급 데이터 없음`만 안내
- `관심종목` 탭도 기존 리포트 카드 경로를 그대로 사용해 같은 전문가용 차트를 상속
- 관련 검증 명령 기준
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_charts.py src/invest_bot/dashboard/streamlit_state.py src/invest_bot/dashboard/streamlit_reports.py src/invest_bot/dashboard/streamlit_data.py src/invest_bot/dashboard/streamlit_watchlist.py tests/test_streamlit_dashboard.py`
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_streamlit_dashboard.py -q`

### 이전 세션 업데이트 (2026-07-06)

- 시장 리포트 생성 후 Discord 전송 경로 1차 구현
  - 대상은 **배치 실행 / 전체 파이프라인** 경로만 포함
  - 수동 단건 CLI 기본 실행은 계속 Discord를 보내지 않음
- Discord 전송은 시장 리포트 row를 source of truth로 사용
  - 포함 내용: `final_opinion`, `summary`, 전략별 신호/이유, 핵심 지표, 투자자 수급
  - 형식은 plain-text only (`content`)로 고정
- 전송 결과 계약 추가
  - `sent`
  - `skipped` (예: 웹훅 미설정)
  - `failed` (예: HTTP 오류)
- Discord 전송 실패는 리포트 저장 실패로 승격하지 않음
- Streamlit `작업 실행` 탭에서 report/full-pipeline partial delivery를 `warning`으로 분리 노출
- 대시보드 app entry는 `AppSettings.from_file()`를 1회만 생성해 데이터 서비스와 action layer에 함께 주입
- `config/app.yaml`의 tracked credential-like 값 제거
- 관련 검증 완료
  - `pytest` targeted suites `76 passed`
  - post-review config delta rerun `73 passed`

### 이전 세션 업데이트 (2026-07-05)

- `리포트 해석` / `데이터 탐색` 탭 공통 차트 렌더러를 Plotly 우선 경로로 확장
  - hover 시 날짜 기준으로 모든 visible series 값을 함께 확인 가능
  - 세로 crosshair(spike line) 기반으로 특정 시점 해석 강화
  - Plotly 미사용 환경에서는 기존 Altair fallback 유지
- 조회 기간 조절 기능 추가
  - 빠른 기간 선택: `1개월`, `3개월`, `6개월`, `1년`, `전체`
  - 직접 시작일/종료일 선택 지원
  - preset 변경과 직접 날짜 변경 모두 Streamlit rerun 이후 일관되게 유지되도록 session state 동기화 보강
- 선택된 조회 기간이 차트 빌더 내부에서 다시 축소되지 않도록 range helper path 정리
- 관련 회귀 테스트 보강
  - 기간 상태 초기화 / preset sync / custom range authority
  - 긴 조회 기간 보존
  - preset 변경 시 stale date widget state reset
  - Plotly 렌더링 경로 검증
- 관련 검증 완료 (`50 passed in 0.65s`)

### 이전 세션 업데이트 (2026-06-28)

- `작업 실행` 탭을 여러 종목 기준 **배치 실행** 흐름으로 단순화
  - `한 종목` 섹션 제거
  - `데이터 수집`, `지표 계산`, `신호 생성`, `리포트 생성`, `전체 파이프라인`을 모두 선택 종목들에 대해 실행 가능
- `리포트 해석` 탭 상단 metrics strip 제거
- 전략 판단 텍스트에 상태별 색상 적용
  - 긍정: 녹색
  - 부정: 빨간색
  - 중립: 검정색
- `데이터 탐색` 탭을 종목 선택 기반 **summary-first** 흐름으로 재구성
  - `원본 데이터 / 분석 데이터` 진입 탭 제거
  - 요약 카드와 빠른 미리보기를 먼저 표시
  - 차트/상세 표/컬럼 설명은 expander 아래로 이동
- HTML escape 보강 및 관련 회귀 테스트 추가
- 관련 검증 완료 (`39 passed in 0.48s`)

### 데이터 수집

- 국내주식 일봉 데이터 수집
- 종목 기본정보 수집
- 투자자 수급 일별 데이터 수집
- 다중 종목 배치 수집
- 정기 다중 종목 수집 스케줄링 초안

### 분석

- DB snapshot 또는 파일 fallback 기반 일봉 로드 및 컬럼 정규화
- 이동평균 계산
  - `ma_5`
  - `ma_20`
  - `ma_60`
- 거래량 이동평균 계산
  - `volume_ma_5`
- RSI 계산
  - `rsi_14`

### 전략 및 리포트

- 전략 공통 인터페이스
- 샘플 전략
- 골든크로스 전략
- RSI 전략
- Trend Filter 전략
- Mean Reversion 전략
- 골든크로스 신호 생성
- 현재 장 상황 요약 리포트 생성
- 시장 리포트 전략별 직접 판단 필드 생성
- 백테스트 전략 adapter/registry 7종
  - `golden-cross`, `rsi`, `trend-filter`, `mean-reversion`, `disparity`, `momentum`, `investor-flow-custom`
- 백테스트 readiness gate
- symbol-first 백테스트 산출물 persistence
- 시장 리포트 생성 후 Discord plain-text delivery 지원
  - batch/full-pipeline opt-in only
  - `sent` / `skipped` / `failed` delivery status
  - delivery failure non-blocking
- 골든크로스 단건 CLI 백테스트 초안

### 대시보드

- Streamlit 기반 운영 대시보드
- 사용자 여정 중심 좌측 메뉴: `홈`, `데이터 갱신`, `투자 리포트`, `관심종목`, `백테스트`, `데이터 보기`, `용어 해설`, `시스템 검증`
- 종목 선택 기반 데이터 보기와 요약 우선 미리보기
- 투자 리포트 탭 후보 카드, `이 종목 보기` 직접 선택, 단일 리포트 focus card 표시
- 투자 리포트 탭 상단 `해석 모아보기` 토글로 종목/전략 판단 카드 비교
- `투자 리포트` / `데이터 보기` 탭 공통 인터랙티브 차트
  - stock dataset에서는 Plotly 기반 전문가용 차트 우선 렌더링
  - 캔들 + 이동평균선, 거래량, RSI 14, 선택적 투자자 수급 panel 지원
  - `일봉` / `주봉` / `월봉` selector와 날짜 기준 shared x-axis hover / zoom 지원
  - 빠른 조회 기간과 직접 조회 기간을 같은 유효 기간으로 동기화
  - 가격 y축과 hover 가격은 천 단위 쉼표 형식으로 표시
  - 기존 저장 `daily_prices_indicators` / `daily_prices` / `investor_daily` / `investor_daily_summary`를 사용하며 새 데이터 수집은 하지 않음
  - 유효한 dated detail 우선, 무효 시 summary 자체의 실제 날짜·값 사용. source 사이의 빈 날짜·투자자 값은 섞지 않으며 누락·날짜 불일치 사유 표시
  - Plotly 미사용 환경에서는 Altair fallback 유지
- 전략별 판단 요약 및 상태별 색상 표시
  - 전략명과 주요 판단 근거는 한글 표시
  - 긴 해석 문장과 판단 근거는 줄바꿈 가능한 카드 UI로 표시
- `용어 해설` 탭
  - 리포트/전략/지표/수급/데이터 용어를 검색·분류 조회
  - 처음 볼 때 추천 순서를 안내 카드로 표시
- 리포트 관심종목(즐겨찾기) 저장, 리포트 미생성 종목까지 포함한 전체 카드 보드, 카드별 상세 보기 지원
- 홈은 저장된 snapshot 기준의 읽기 전용 투자 브리핑으로 동작
  - 리포트·신호 기준일, 데이터 상태, 시스템 검증 상태를 확인하고 최신화가 필요하면 `데이터 갱신`에서 명시적으로 실행
  - 데이터 갱신 중 선택적 종목 기본정보 API가 실패해도 가격·수급·지표·신호·리포트 갱신은 계속 진행
- 관심종목 탭도 리포트 카드와 동일한 전문가용 주가 차트 경로 사용
- 여러 종목 기준 배치 실행
  - 데이터 수집
  - 지표 계산
  - 골든크로스 신호 생성
  - 시장 리포트 생성
  - 전체 파이프라인 실행
- 전용 `백테스트` 탭
  - 준비 상태 확인 -> `준비 실행` -> `백테스트 실행` -> 결과 확인
  - 선택한 미준비 전략은 차단 사유와 함께 실행이 막힘
  - 결과는 전략 요약 카드, 종목/전략별 결과 카드, 해석 문장, 비교표, 거래 순서 누적 수익률 차트, 거래 로그로 표시
  - `데이터 보기` 탭은 generic preview를 유지하며, 세션 내 비교 기준은 `백테스트` 탭 결과를 우선 사용
- 리포트/전체 파이프라인 Discord delivery warning 노출
- 정기 수집 상태와 최근 로그 표시

### 테스트

- `pytest` 기반 테스트
- 수집, 분석, 전략, 리포트, 대시보드, 스케줄링, 백테스트 테스트 포함

### DB 저장 및 마이그레이션

- Postgres 기반 `docker-compose` 실행 경로 포함
- `config/app.yaml` 기반 DB 설정 로드 지원
- Alembic migration과 `scripts/init_db.py` 기반 초기화 경로 구현
- raw/processed snapshot의 기본 저장 경로는 `dataset_frames`
- 정규화 테이블 write는 `enable_db_write` 설정으로 제어

## 프로젝트 구조

```text
invest_bot/
  agent.md
  README.md
  docs/
    analysis/
    tasks/
    strategies/
  config/
    app.yaml.example
    collection_schedule.yaml.example
  scripts/
    run_collection.py
    run_scheduled_collection.py
    run_daily_analysis.py
    run_golden_cross_signals.py
    run_backtest.py
    run_market_report.py
    run_dashboard.py
    run_streamlit_dashboard.py
    run_tests.py
  src/
    invest_bot/
      clients/
      config/
      dashboard/
      jobs/
      market/
      strategy/
  tests/
```

## 설정 파일

실제 실행 전 아래 예시 파일을 복사해서 사용합니다.

- [`config/app.yaml.example`](config/app.yaml.example) -> `config/app.yaml`
- [`config/collection_schedule.yaml.example`](config/collection_schedule.yaml.example) -> `config/collection_schedule.yaml`

실제 설정 파일은 `.gitignore`에 포함되어 있습니다.

Git 제외 규칙은 `.env` 변형·실행 설정의 로컬 복사본, 인증 토큰 캐시·Streamlit secrets·개인 키, 로컬 DB·덤프·백업, 실행 기록·로그와 캡처 이미지를 포함합니다. `data/` 아래 원본 데이터·백테스트 CSV/JSON·생성 HTML도 제외합니다. 소스·테스트·설정 예시와 `.streamlit/config.toml`은 계속 관리합니다.

캐시나 결과의 저장 경로를 변경하면 `git check-ignore -v --no-index <파일 경로>`로 제외 여부를 확인합니다. `.gitignore`는 이미 추적 중인 파일이나 과거 커밋을 제거하지 않습니다.

DB 접근 정보와 KIS API 키/시크릿은 `config/app.yaml` 또는 런타임 환경변수로 관리합니다.
같은 항목이 둘 다 있으면 `INVEST_BOT_*` 환경변수가 `config/app.yaml`보다 우선합니다.
Docker Compose는 로컬 `config/` 디렉터리를 컨테이너에 read-only로 마운트합니다. `.dockerignore`는 `.env`, 실제 `config/app.yaml`, `config/kis_credentials.yaml`, `config/collection_schedule.yaml`을 빌드에서 제외하고 예시 설정 파일은 포함합니다. 제외 규칙 변경은 다음 이미지 빌드부터 적용됩니다.
기본 예시값은 로컬 실행 시 `db_host: localhost`, Docker Compose 내부 실행 시 `db_host_docker: db`를 자동 사용하도록 맞춰져 있습니다.
`config/kis_credentials.yaml`은 더 이상 읽지 않습니다.

주요 환경변수:

- `INVEST_BOT_KIS_APP_KEY`, `INVEST_BOT_KIS_APP_SECRET`: mock/live 공통 KIS 키 fallback
- `INVEST_BOT_KIS_MOCK_APP_KEY`, `INVEST_BOT_KIS_MOCK_APP_SECRET`: mock 모드 전용 KIS 키
- `INVEST_BOT_KIS_LIVE_APP_KEY`, `INVEST_BOT_KIS_LIVE_APP_SECRET`: live 모드 전용 KIS 키
- `INVEST_BOT_DB_HOST`, `INVEST_BOT_DB_PORT`, `INVEST_BOT_DB_NAME`, `INVEST_BOT_DB_USER`, `INVEST_BOT_DB_PASSWORD`: DB 접속 정보
- `INVEST_BOT_ENABLE_DB_WRITE`: 수집 데이터를 DB fact table에도 기록할지 여부
- `INVEST_BOT_KIS_TOKEN_CACHE`: KIS access token 캐시 파일 경로. 미설정 시 `/tmp/invest_bot/` 아래에 자동 저장

KIS access token은 프로세스 간 재발급을 줄이기 위해 파일 캐시를 사용합니다. 이는 Streamlit 버튼 실행이나 CLI 실행이 반복될 때 `tokenP` 발급 제한으로 수집이 실패하는 것을 줄이기 위한 운영 캐시입니다.

## 설치

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```

## 실행 방법

### Docker Compose로 실행

대시보드를 포함한 기본 서비스는 `docker-compose.yml` 기준으로 아래 순서로 실행합니다.

현재 기본 설정(`config/app.yaml.example`)은 같은 파일로 두 실행 경로를 모두 지원합니다. Compose 실행 전에는 로컬 `config/app.yaml`을 준비해 두고, Compose가 이를 런타임에 마운트해 사용합니다.

- 호스트 Python 실행: `db_host: localhost`
- Docker Compose 내부 실행: `db_host_docker: db`

전체 서비스는 프로젝트 루트의 스크립트로 관리합니다. 스크립트는 다른 디렉터리에서 호출해도 해당 프로젝트를 대상으로 실행합니다.

```bash
./start.sh
./restart.sh
./stop.sh
```

`start.sh`와 `restart.sh`는 Compose 설정 확인 → 이미지 빌드 → scheduler 컨테이너의 스케줄 설정 검사 순으로 진행합니다. 모두 통과하면 `db`, `migrate`, `scheduler`, `web`을 시작합니다. `restart.sh`는 검사 통과 후 기존 서비스를 내립니다. 설정·빌드·검사 실패 시 비정상 종료하며 서비스 중단·시작 명령으로 넘어가지 않습니다. `start.sh`도 매번 빌드를 확인하므로 첫 실행이나 변경 후 실행에는 시간이 필요할 수 있습니다. `stop.sh`는 컨테이너를 보존하고 전체 서비스를 정지합니다. 설정 타입과 검사의 범위는 [운영 가이드](docs/tasks/07_operations_docs.md#시작재시작-사전검증-2026-10-10)를 참고하세요.

Compose 명령을 직접 실행하는 경우 아래 순서를 사용할 수 있습니다. 사전검증을 포함하려면 위 스크립트를 사용합니다.

전체 이미지 빌드:

```bash
docker compose build
```

기본 실행 경로에는 `db`, `migrate`, `web`, `scheduler`가 포함됩니다.
`migrate`는 별도 프로필 없이 함께 평가되며, `web`과 `scheduler`는 마이그레이션 성공 후 시작됩니다.
Compose의 `migrate`는 `migrate-only` 모드이므로 외부 종목 마스터 다운로드 없이 스키마를 적용합니다. 전체 초기화가 필요하면 `python scripts/init_db.py --mode full`을 명시적으로 실행합니다. 로컬 기본 모드는 기존과 같은 `full`이며, 선택 우선순위는 `--mode` 인자 → `INVEST_BOT_INIT_MODE` 환경변수 → `full`입니다.

스케줄 예시의 `log_path: ../.runtime/logs/collection_scheduler.log`는 config 파일 기준 상대경로입니다. Compose에서는 호스트 `${INVEST_BOT_RUNTIME_DIR:-./.docker/runtime}`를 scheduler에 쓰기 가능, web에 읽기 전용으로 마운트합니다. 기존 스케줄 설정에 `logs/collection_scheduler.log`가 남아 있다면 예시의 경로로 갱신해야 읽기 전용 config 밖에 로그가 기록됩니다. 상세 확인 방법은 [운영 가이드](docs/tasks/07_operations_docs.md)를 참고하세요.

백그라운드 실행:

```bash
docker compose up -d
```

대시보드만 빠르게 띄우려면:

```bash
docker compose up -d db migrate web
```

실행 상태 확인:

```bash
docker compose ps
```

대시보드 로그 확인:

```bash
docker compose logs -f web
```

`web` 서비스만 다시 빌드하고 실행:

```bash
docker compose up -d --build web
```

대시보드 접속 확인:

```bash
curl -I --max-time 5 http://127.0.0.1:8000
```

접속 주소:

```text
http://127.0.0.1:8000
```

전체 종료:

```bash
docker compose down
```

볼륨까지 함께 정리:

```bash
docker compose down -v
```

### 1. 테스트

전체 테스트:

```powershell
python -m pytest
```

대시보드용 테스트 결과 저장까지 함께 하려면:

```powershell
python scripts/run_tests.py
```

기본 suite는 실제 네트워크와 PostgreSQL 검증을 제외하며, 기존 설정 파일을 덮어쓰지 않습니다. `python scripts/run_tests.py --suite default -q`로 같은 범위를 실행할 수 있습니다. 초기화 테스트는 현재 Python과 임시 SQLite·종목 마스터 fixture를 사용합니다.

PostgreSQL 검증은 운영 DB와 분리된 로컬 테스트 DB에 `QA_POSTGRESQL_URL`을 지정한 뒤 `python scripts/run_tests.py --suite postgresql tests/integration/test_postgresql_migrations.py -q`로 실행합니다. DB 이름은 `_test`로 끝나야 합니다. CI는 별도 `postgres:17` 서비스를 사용합니다.

### 2. 단일 종목 수집

```powershell
python scripts/run_collection.py 005930
```

기본 저장은 DB snapshot이다. 로컬 파일 기반 산출물이 함께 필요하면 코드에서 다른 storage 구현을 주입하거나 별도 export 스크립트를 사용한다.

### 3. 다중 종목 배치 수집

```powershell
python scripts/run_collection.py 005930 000660 035420
```

종목 파일 사용:

```powershell
python scripts/run_collection.py --symbols-file symbols.txt --days 365
```

현재 전략 세트를 안정적으로 돌리려면 최소 60거래일이 필요합니다.  
기본 수집값은 이를 확보하기 쉽도록 365일 조회 기준으로 맞춰져 있습니다. 대시보드의 데이터 갱신과 백테스트 준비 화면에서는 날짜 범위를 클릭해 캘린더로 시작일과 종료일을 선택할 수 있습니다.

### 명시적 기간 보충 수집

KIS 기간별 일봉 API는 한 번에 최대 100행을 반환합니다. 긴 기간은 별도 보충 수집 CLI로 각 응답의 가장 과거 관측일 이전을 반복 조회합니다. 일봉과 투자자 일별 수급을 새 `_history.csv` DB snapshot에 저장하고 지표·신호·시장 리포트를 갱신합니다.

```bash
.venv/bin/python scripts/run_historical_collection.py --start 2024-10-13 --end 2026-10-13
.venv/bin/python scripts/run_historical_collection.py 005930 000660 --start 2024-10-13 --end 2026-10-13
```

종목을 생략하면 저장된 시장 리포트의 종목을 사용합니다. 당일 가격은 장중 관측값일 수 있고, 종료일이 오늘이면 수급은 전날까지 요청합니다. 결과의 실제 시작·종료일, 행 수, 가격일 대비 누락 수급일을 확인합니다. API 오류·잘못된 날짜·무진행·상충하는 중복·페이지 한도 초과는 실패로 처리합니다. 이전의 짧은 원본 snapshot은 보존하며 Discord를 보내지 않습니다.

이 경로는 기존 `run_collection.py`, 대시보드 기본 수집, 정기 수집의 기간 확보 정책을 변경하지 않습니다. 기본 경로의 개선 상태는 [G08a](docs/operations/improvements/data.md#g08a)를 따릅니다.

2026-10-15 이 전용 CLI의 코드·회귀·문서를 기능 단위로 main에 반영했습니다. 커밋 후보만 격리한 새 검증에서 전용26개·기본858개가 통과했습니다.

사용 방법과 검증 범위는 [장기 보충 수집](docs/tasks/02_data_collection.md#장기-보충-수집-2026-10-13)을 참고하세요.

### 4. 정기 다중 종목 수집

수집 없이 설정만 검사:

```powershell
python scripts/run_scheduled_collection.py --validate-config
```

다른 설정 파일은 `--config 경로`로 지정합니다. 검사는 수집·마스터 동기화·DB 연결·수집 로그 기록을 실행하지 않습니다.

1회 실행:

```powershell
python scripts/run_scheduled_collection.py --once
```

주기 실행:

```powershell
python scripts/run_scheduled_collection.py
```

테스트용 제한 실행:

```powershell
python scripts/run_scheduled_collection.py --max-runs 2
```

### 5. 지표 계산

```powershell
python scripts/run_daily_analysis.py 005930
```

### 6. 골든크로스 신호 생성

```powershell
python scripts/run_golden_cross_signals.py 005930
```

### 7. 시장 리포트 생성

```powershell
python scripts/run_market_report.py 005930
```

생성된 리포트에는 종합 의견(`final_opinion`)과 별도로 아래 전략별 판단 필드가 함께 포함됩니다.

리포트의 `date`와 `reference_date`는 지표·신호·수급의 최신 유효일 중 가장 이른 날짜입니다. 각 입력에서는 이 공통 기준일 이하의 최신 행만 사용합니다. `indicator_date`, `signal_date`, `investor_date`와 각 `*_data_status`로 실제 사용한 날짜와 지연 여부를 확인할 수 있습니다. 필수 입력이 없거나 기준일 이전 행을 선택할 수 없으면 리포트 생성을 실패로 처리합니다.

CSV의 `20260410` 같은 숫자형 날짜도 실제 거래일로 해석합니다. 날짜 없는 상세 수급은 같은 파일명의 `investor_daily_summary`에서 관측일과 수급값을 읽습니다. summary에 날짜만 있는 경우에는 단일 상세 행만 최신 관측일에 연결하며, 정렬 근거가 없는 다중 상세 행은 오류로 처리합니다. 파일명의 수집 요청일을 거래일로 추정하지 않으므로 주말 요청도 실제 관측일을 기준으로 처리합니다.

대시보드에서 최신 수집분까지 반영하려면 `전체 파이프라인`을 실행하거나 `데이터 수집 -> 지표 계산 -> 신호 생성 -> 리포트 생성` 순서로 실행합니다. 데이터 수집이 모두 실패하면 전체 파이프라인은 리포트를 갱신하지 않고 실패 메시지를 표시합니다.

- `rsi_strategy_signal`, `rsi_strategy_reason`
- `trend_filter_signal`, `trend_filter_reason`
- `mean_reversion_signal`, `mean_reversion_reason`

필수 지표가 부족하면 각 전략 필드는 `hold`와 `Missing indicators: ...` 형식으로 기록됩니다.

### 8. 백테스트 실행

```powershell
python scripts/run_backtest.py 005930
```

빠른 단건 CLI 확인 경로는 유지되지만, 여러 전략 비교와 현재 운영 흐름의 기준 화면은 대시보드 `백테스트` 탭입니다.

대시보드 `백테스트` 탭 흐름:

- 준비 확인
  - 종목과 전략을 고른 뒤 준비 상태 panel에서 실행 가능 여부를 먼저 확인
  - 미준비 전략은 종목별/전략별 차단 사유와 함께 표시
- 준비 실행
  - 버튼을 눌렀을 때만 `데이터 수집 -> 지표 계산 -> 골든크로스 신호 생성`을 수행
  - 자동 background 실행은 하지 않음
- 백테스트 실행
  - 준비 완료된 조합만 실행
  - 세션 안 비교 결과는 `백테스트` 탭에 유지
- 결과 확인
  - 전략 요약 카드
  - 전략 비교표
  - 거래 순서 누적 수익률 차트
  - 일별 평가금액 곡선
  - 거래 로그
  - 저장된 실행 이력 재불러오기
  - 복수 전략 조합 결과와 다종목 포트폴리오 집계

포함 전략 adapter/registry 7종:

- `golden-cross`
- `rsi`
- `trend-filter`
- `mean-reversion`
- `disparity`
- `momentum`
- `investor-flow-custom`

현재 체결/청산 규칙:

- `buy` 신호 발생 시 다음 거래일 종가 진입
- `sell` 신호 발생 시 다음 거래일 종가 청산
- 미청산 포지션은 마지막 거래일 종가로 강제 종료

일별 백테스트 입력은 **종목별·전략별로 거래일당 한 행**이어야 합니다. 같은 날짜의 중복은 종가·신호가 같아도 차단하며, 문자열과 Timestamp가 같은 날이거나 하루 안의 시각만 다른 경우도 중복입니다. 준비 확인·신호 생성·직접 실행·일별 평가곡선·전략 조합에서 임의로 마지막 행을 선택하지 않습니다. 차단 사유에는 데이터셋과 예시 날짜가 표시됩니다. 여러 종목이나 여러 전략의 개별 입력에 같은 거래일이 있는 것은 정상입니다. 자세한 기준은 [백테스트 날짜 유일성 규칙](docs/tasks/05_strategy_backtest.md#일별-입력의-날짜-유일성-2026-10-11)을 참고하세요.

기본 골든크로스 저장 신호는 실행 시 현재 지표의 거래일·종가와 대조하고, 불일치하면 이유를 표시하고 실행을 차단합니다. 대시보드에서는 `준비 실행`으로 신호를 다시 생성한 뒤 실행합니다. CLI도 명시한 지표 또는 해당 종목의 최신 지표를 실제로 읽어 대조하며, 지표가 없는 기존 저장 신호 단독 실행은 현재 지표와의 정합성 검증 범위에 포함되지 않습니다. 사용자 지정 MA 설정과 상세 호환 범위는 [저장 신호 정합성 규칙](docs/tasks/05_strategy_backtest.md#저장-신호의-날짜가격-정합성-2026-10-12)을 참고하세요.

산출물 persistence identity:

- 파일명은 `symbol` 우선 규칙으로 저장
  - `005930_golden-cross_20260720T010203Z_backtest_trades.csv`
  - `005930_golden-cross_20260720T010203Z_backtest_summary.csv`
- 공통 실행 식별자
  - `run_group_id`: `backtest_group_<UTC timestamp>`
  - `run_id`: `<symbol>_<strategy_id>_<UTC timestamp>`
- summary provenance
  - `indicator_source_*`
  - `signal_source_*`
  - `investor_source_*`
  - `price_source_*`
  - `input_sources_json`

주의:

- `데이터 보기` 탭은 generic preview를 유지하므로 종목별 최신 artifact 1건만 보일 수 있습니다.
- 같은 세션 안 여러 전략 비교는 `백테스트` 탭 결과를 source of truth로 봅니다.
- 이번 범위는 실거래/주문/리스크 관리, 새 DB schema, 새 dependency 추가를 포함하지 않습니다.

후속 후보:

- 고급 전략 파라미터 튜닝(자동 탐색·최적값 추천 등)
- 브라우저 세션을 넘어서는 사용자별 화면 설정 저장 정책

### 고정 2년 snapshot의 전략·가격 수익률 비교

2026-10-13에 수집한 기존16종목 history snapshot을 대상으로 7종 기본 전략을 실행하고, 같은 기간 수정종가 매수 후 보유와 비교합니다. 일반 백테스트·수집 설정은 변경하지 않습니다.

```bash
python scripts/run_backtest_comparison.py --as-of 2026-10-12 --output data/backtests/2026-10-13
python scripts/render_backtest_comparison.py
```

첫 명령은 DB 접속이 필요하며 기존 `backtest_summaries`·`backtest_trades`에 결과를 저장합니다. 입력 파일은 `<종목>_20241013_20261013_history.csv` 지표/골든크로스, `<종목>_20241013_20261012_history.csv` 수급 summary로 고정합니다. 평가기간별 run ID·파일명은 구분하고 하나의 비교 배치 ID로 묶습니다. 전체485거래일112회와 지표 준비 이후426거래일112회를 별도 현금 시작으로 계산합니다. 두 번째 명령은 JSON·CSV를 이용해 외부 자원 없는 HTML을 생성합니다.

2026-10-16 이 비교 기능의 코드·회귀·문서를 기능 단위로 main에 반영했습니다. 커밋 후보만 격리한 새 검증에서 전용11개·기본869개가 통과했고 기존 로컬 결과의 HTML 생성과 CSV 링크 대상898개를 정적으로 확인했습니다.

HTML은 `data/reports/backtest-comparison-2026-10-13.html`, 거래·신호·평가금액·요약 CSV는 `data/backtests/2026-10-13/`에 생성됩니다. 같은 상대 경로 구조를 유지하면 CSV 링크가 동작합니다. 현재 결과·가정·실제 DB 실행 검증은 [비교 리포트의 검증 범위](docs/tasks/05_strategy_backtest.md#비교-리포트-검증-범위)를 참고하세요. 비용·배당0, 소수점 주식 허용이며 실제 계좌 수익률이나 배당 포함 총수익률을 비교한 것은 아닙니다.

### 슬라이딩 윈도우·다중 전략 연구

고정16종목의 최신10/13 가격·수급과 KODEX200의2년 가격 CSV를 이용합니다. 기본7전략, 신호 혼합7종, 독립 자금배분3종을 같은 입력·체결·비용 기준으로 비교합니다.

```bash
python scripts/run_rolling_backtest_research.py --cost-rate 0.001
python scripts/render_rolling_backtest_report.py
```

기본 입력은 `data/weekly-trend/2026-10-13/`, `data/history/2026-10-13/`, 별도 `--benchmark-input data/rolling-inputs/2026-10-13/069500_prices.csv`입니다. 출력 폴더에 입력 파일을 미리 넣을 필요가 없습니다. `--output <새 폴더> --validate-inputs-only`로 날짜·관측일·중복 수급 정합성을 먼저 확인할 수 있습니다. 실제 계산은 DB/API를 호출하지 않으며, 운영 백테스트나 조합 이력 계약을 변경하지 않습니다.

준비 이후427거래일에서20·60·120·240행 창을20행씩 이동합니다. 66개 창과 전체/최근5일을 별도 현금 시작으로 평가합니다. 비용은 매수·매도 각각0.10%이며 세율이 아닙니다. 겹친 창의 수익률을 연결하지 않고 길이별 분포를 제공합니다. 120행 훈련/20행 테스트의15개 비중복 테스트 블록은 선택 규칙과 블록 재시작 가정을 별도로 표시합니다.

산출물은 `data/reports/rolling-mixed-backtest-2026-10-13.html`, 근거는 `data/rolling-backtests/2026-10-13/`입니다. HTML의 모든 표 제목으로 열별 오름차순·내림차순 정렬이 가능합니다. `기간별 종목 한눈에 보기`에서 기간 길이·평가 날짜·전략을 선택하고 종목명/코드를 검색하면, 같은 조건의 16종목 수익률·MDD·보유/ETF 대비 차이를 비교할 수 있습니다. 기본은 최신20거래일·모멘텀 단독이며, 종목명을 누르면 검색 가능한 종목별 상세로 이동합니다. 외부 자원 없이 HTML만 열어도 탐색 기능이 작동합니다. 전체 입력 snapshot·신호·거래·주요 구간 일별 평가금액을 함께 보존합니다. [실행 검증과 한계](docs/tasks/05_strategy_backtest.md#슬라이딩-연구-검증-범위)를 참고하세요. G08c 대시보드 조합 설정 저장·재로드는 이 별도 CSV 연구와 구분하며 대기 상태를 유지합니다.

### 9. 대시보드 실행

```powershell
python scripts/run_dashboard.py
```

브라우저:

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

직접 Streamlit 런처를 써도 됩니다:

```powershell
python scripts/run_streamlit_dashboard.py
```

또는:

```powershell
streamlit run streamlit_app.py
```

## 데이터 저장 경로

### 수집 결과

```text
data/raw/domestic_stock/
  daily_prices/
  daily_prices_summary/
  stock_info/
  investor_daily/
  investor_daily_summary/
```

### 분석 및 전략 결과

```text
data/processed/domestic_stock/
  daily_prices_indicators/
  golden_cross_signals/
  market_reports/
  backtest_trades/
  backtest_summaries/
```

### 테스트 결과

```text
data/processed/test_reports/
```

## DB 마이그레이션 준비 문서

현재 저장소의 기본 실행 경로는 DB-first 기준이며, 관련 설계/운영 문서는 아래에 정리되어 있습니다.

- [`docs/operations/db_migration_plan.md`](docs/operations/db_migration_plan.md)

이 문서에는 다음 내용이 포함됩니다.

- 현재 DB snapshot + 정규화 테이블 기준 ERD
- `docker-compose.yml` 초안 검토 결과
- Repository 인터페이스 경계 제안
- DB 마이그레이션 구현 순서와 위험요인

## 현재 주요 파일

### 데이터 수집

- [`kis_client.py`](src/invest_bot/clients/kis_client.py)
- [`domestic_stock.py`](src/invest_bot/market/domestic_stock.py)
- [`collector.py`](src/invest_bot/market/collector.py)
- [`collect_market_data.py`](src/invest_bot/jobs/collect_market_data.py)
- [`scheduled_collection.py`](src/invest_bot/jobs/scheduled_collection.py)

### 분석 및 전략

- [`analysis.py`](src/invest_bot/market/analysis.py)
- [`analyze_daily_prices.py`](src/invest_bot/jobs/analyze_daily_prices.py)
- [`golden_cross.py`](src/invest_bot/strategy/golden_cross.py)
- [`generate_golden_cross_signals.py`](src/invest_bot/jobs/generate_golden_cross_signals.py)
- [`generate_market_report.py`](src/invest_bot/jobs/generate_market_report.py)
- [`generate_backtest.py`](src/invest_bot/jobs/generate_backtest.py)

### 대시보드

- [`service.py`](src/invest_bot/dashboard/service.py)
- [`streamlit_dashboard.py`](src/invest_bot/dashboard/streamlit_dashboard.py)
- [`streamlit_charts.py`](src/invest_bot/dashboard/streamlit_charts.py)
- [`streamlit_reports.py`](src/invest_bot/dashboard/streamlit_reports.py)
- [`streamlit_watchlist.py`](src/invest_bot/dashboard/streamlit_watchlist.py)
- [`report_favorites.py`](src/invest_bot/dashboard/report_favorites.py)

## 현재 진행 상태

- [x] KIS 연동 기반 수집 구조
- [x] DB snapshot 저장 구조
- [x] 기본 지표 계산
- [x] 골든크로스 전략 구현
- [x] 골든크로스 신호 생성
- [x] 시장 리포트 생성
- [x] 백테스트 전략 adapter/registry 7종
- [x] 전용 `백테스트` 탭과 in-session 비교 결과 표시
- [x] Streamlit 대시보드
- [x] 투자 리포트 탭 단일 리포트 본문 표시
- [x] 투자 리포트 탭 전략별 판단 요약 표시
- [x] 투자 리포트 탭 상단 해석 모아보기 토글
- [x] 용어 해설 탭
- [x] 투자 리포트 / 데이터 보기 탭 공통 인터랙티브 차트와 조회 기간 조절
- [x] 리포트 관심종목(즐겨찾기) 저장 및 관심종목 탭
- [x] 다중 종목 배치 수집
- [x] 정기 수집 스케줄링 초안
- [x] 일별 mark-to-market equity curve
- [x] 백테스트 artifact history / reload
- [x] 복수 전략 조합(AND / OR / 가중치)
- [ ] 고급 전략 파라미터 튜닝
- [x] 포트폴리오 / multi-symbol aggregation
- [x] 현재 브라우저 세션 한정 화면 설정 저장
- [ ] 모의투자 주문 실행
- [ ] 실거래 주문 실행
- [ ] 리스크 관리 정책 자동화

전체 작업 현황은 아래 문서를 참고합니다.

- [`docs/tasks/00_summary.md`](docs/tasks/00_summary.md)
- [`docs/strategies/00_summary.md`](docs/strategies/00_summary.md)

## 참고 자산

초기 구현과 구조 설계 시 아래 reference를 참고합니다.

- `reference/open-trading-api/`

다만 현재 프로젝트는 reference를 그대로 복사하지 않고, 필요한 기능을 분리해서 독립 프로젝트 구조로 정리하는 방향을 따릅니다.

commit error test
