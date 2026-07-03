# Task 04. Dashboard

## 목표

수집, 분석, 신호, 리포트, 테스트 상태를 브라우저에서 빠르게 확인하고 필요한 작업을 직접 실행할 수 있는 대시보드를 제공한다.

## 완료된 항목

- [x] Streamlit 기반 대시보드 구현
- [x] 종목 선택 기반 summary-first 데이터 탐색 구현
- [x] 골든크로스 신호 및 시장 리포트 표시
- [x] 리포트 해석 탭에서 선택된 1건 중심 본문 표시
- [x] 리포트 카드 내 전략별 판단 요약 표시
- [x] 리포트 즐겨찾기 저장
- [x] 관심종목 전용 탭 추가
- [x] 테스트 결과 표시
- [x] 데이터 수집 실행
- [x] 지표 계산 실행
- [x] 골든크로스 신호 생성 실행
- [x] 시장 리포트 생성 실행
- [x] 전체 파이프라인 실행
- [x] 정기 수집 상태와 최근 실행 로그 표시

## 남은 항목

- [ ] 종목 비교 차트
- [ ] 최신 수집/분석 시각 강조
- [ ] 백테스트 결과 시각화
- [ ] 대시보드 설정 저장 고도화

## 현재 작업 실행 탭 동작

- 여러 종목 선택 기반 **배치 실행**만 노출
- `한 종목` 전용 섹션은 제거
- 선택 종목들에 대해 아래 작업을 직접 실행 가능
  - 데이터 수집
  - 지표 계산
  - 신호 생성
  - 리포트 생성
  - 전체 파이프라인
- 종목 1개만 선택해도 동일한 배치 흐름으로 사용 가능

## 현재 리포트 해석 탭 동작

- 상단 선택 컨트롤로 종목/리포트를 고른 뒤 본문에는 선택된 1건만 표시
- 선택된 리포트 아래에서 차트와 상세 데이터 표를 계속 확인 가능
- `final_opinion`과 별도로 RSI / Trend Filter / Mean Reversion 전략의 직접 판단과 이유를 함께 표시
- 선택된 종목을 즐겨찾기로 저장/해제할 수 있음
- 즐겨찾기만 보기와 즐겨찾기 우선 정렬을 지원함
- 별도 `관심종목` 탭에서 저장된 종목만 다시 모아 보고 1건씩 본문으로 확인 가능
- 즐겨찾기는 DB 기반 단일 watchlist 상태로 저장되며 report `entry_key`가 아니라 `symbol` 기준으로 관리됨
- 같은 DB 볼륨을 유지하는 정상적인 app/container 재시작 후에도 관심종목 상태가 유지됨

## 이번 세션 작업 요약 (2026-07-03)

- 관심종목 persistence를 로컬 JSON에서 DB 기반 단일 watchlist로 전환
- `report_favorite_symbols` 테이블과 Alembic migration 추가
- `ReportFavoritesStore`를 DB-backed thin adapter로 전환
- 기존 `ReportFavoritesStore(Path(...))` 호출 형태 호환 유지
- duplicate insert race 시 `IntegrityError` 대신 `False`를 반환하도록 repository 보강
- 자동 JSON backfill/import는 이번 1차 범위에서 제외
- user/account ownership 없는 단일 global symbol watchlist 범위 유지
- 검증
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_report_favorites.py tests/test_init_db_script.py tests/test_streamlit_dashboard.py -q`
  - 결과: `51 passed in 1.64s`
  - `docker compose` 기준 web recreate 이후에도 `['005930']` 유지 확인
  - `curl http://127.0.0.1:8000` → `HTTP/1.1 200 OK`

## 이번 세션 작업 요약 (2026-06-28)

- `streamlit_actions.py` 수정
  - `한 종목` 섹션 제거
  - `작업 실행` 탭을 여러 종목 기준 배치 실행 흐름으로 단순화
  - `데이터 수집`, `지표 계산`, `신호 생성`, `리포트 생성`, `전체 파이프라인`을 모두 선택 종목들에 대해 실행 가능하게 정리
- `streamlit_reports.py`, `streamlit_formatters.py` 수정
  - `리포트 해석` 탭 상단 metrics strip 제거
  - 전략 판단 텍스트에 green/red/black 상태 색상 적용
- `streamlit_data.py` 수정
  - `원본 데이터 / 분석 데이터` 이원 진입 제거
  - 종목 선택 기반 summary-first 데이터 탐색 흐름으로 재구성
  - 차트/전체 표/컬럼 설명은 expander 아래로 이동
- `tests/test_streamlit_dashboard.py` 보강
  - 배치 실행 구조, report top metrics 제거, 색상 contract, symbol-first data flow, HTML escaping 회귀 검증 추가
- 검증
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_actions.py src/invest_bot/dashboard/streamlit_reports.py src/invest_bot/dashboard/streamlit_formatters.py src/invest_bot/dashboard/streamlit_data.py tests/test_streamlit_dashboard.py`
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache .venv/bin/python -m pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `39 passed in 0.48s`

## 현재 잔여 작업

- 사용자/account ownership이 필요한 shared watchlist 확장 여부 결정
- 종목 비교 차트
- 최신 수집/분석 시각 강조
- 백테스트 결과 시각화
- 대시보드 설정 저장 고도화

## 접속 정보

대시보드:

```text
http://127.0.0.1:8000
```

## 관련 파일

- [`service.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/service.py)
- [`streamlit_dashboard.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/streamlit_dashboard.py)
- [`streamlit_reports.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/streamlit_reports.py)
- [`streamlit_watchlist.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/streamlit_watchlist.py)
- [`report_favorites.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/report_favorites.py)
- [`run_dashboard.py`](/C:/Users/user/PycharmProjects/invest_bot/scripts/run_dashboard.py)
- [`run_streamlit_dashboard.py`](/C:/Users/user/PycharmProjects/invest_bot/scripts/run_streamlit_dashboard.py)
