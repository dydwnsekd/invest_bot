# invest_bot

국내주식 데이터를 수집하고, 지표를 계산하고, 전략 신호와 시장 리포트를 생성해 확인할 수 있는 Python 기반 자동매매 연구 프로젝트입니다.

현재는 실거래 자동화보다 아래 흐름을 안정적으로 만드는 데 초점을 두고 있습니다.

1. 데이터 수집
2. DB snapshot 저장
3. 지표 계산
4. 전략 신호 생성
5. 시장 리포트 생성
6. 대시보드 확인
7. 테스트 기반 검증

## 현재 구현 범위

### 이번 세션 업데이트 (2026-06-28)

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
- 골든크로스 백테스트 초안

### 대시보드

- Streamlit 기반 운영 대시보드
- 종목 선택 기반 데이터 탐색과 요약 우선 미리보기
- 리포트 해석 탭 단일 리포트 본문 표시
- 전략별 판단 요약 및 상태별 색상 표시
- 리포트 관심종목(즐겨찾기) 저장 및 별도 탭 확인
- 여러 종목 기준 배치 실행
  - 데이터 수집
  - 지표 계산
  - 골든크로스 신호 생성
  - 시장 리포트 생성
  - 전체 파이프라인 실행
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

- [`config/app.yaml.example`](/C:/Users/user/PycharmProjects/invest_bot/config/app.yaml.example) -> `config/app.yaml`
- [`config/collection_schedule.yaml.example`](/C:/Users/user/PycharmProjects/invest_bot/config/collection_schedule.yaml.example) -> `config/collection_schedule.yaml`

실제 설정 파일은 `.gitignore`에 포함되어 있습니다.

DB 접근 정보와 KIS API 키/시크릿은 `config/app.yaml` 한 곳에서 관리합니다.
Docker Compose는 로컬 `config/` 디렉터리를 컨테이너에 read-only로 마운트하며, 이미지 빌드 레이어에는 실제 `config/app.yaml`을 포함하지 않습니다.
기본 예시값은 로컬 실행 시 `db_host: localhost`, Docker Compose 내부 실행 시 `db_host_docker: db`를 자동 사용하도록 맞춰져 있습니다.
`config/kis_credentials.yaml`은 더 이상 읽지 않습니다.

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

전체 이미지 빌드:

```bash
docker compose build
```

기본 실행 경로에는 `db`, `migrate`, `web`, `scheduler`가 포함됩니다.
`migrate`는 별도 프로필 없이 함께 평가되며, `web`과 `scheduler`는 마이그레이션 성공 후 시작됩니다.

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
python scripts/run_collection.py --symbols-file symbols.txt --days 90
```

현재 전략 세트를 안정적으로 돌리려면 최소 60거래일이 필요합니다.  
기본 수집값은 이를 확보하기 쉽도록 90일 조회 기준으로 맞춰져 있습니다.

### 4. 정기 다중 종목 수집

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

- `rsi_strategy_signal`, `rsi_strategy_reason`
- `trend_filter_signal`, `trend_filter_reason`
- `mean_reversion_signal`, `mean_reversion_reason`

필수 지표가 부족하면 각 전략 필드는 `hold`와 `Missing indicators: ...` 형식으로 기록됩니다.

### 8. 백테스트 초안 실행

```powershell
python scripts/run_backtest.py 005930
```

기본 규칙:

- `buy` 신호 발생 시 다음 거래일 종가 진입
- `sell` 신호 발생 시 다음 거래일 종가 청산
- 미청산 포지션은 마지막 거래일 종가로 강제 종료

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

- [`kis_client.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/clients/kis_client.py)
- [`domestic_stock.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/market/domestic_stock.py)
- [`collector.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/market/collector.py)
- [`collect_market_data.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/collect_market_data.py)
- [`scheduled_collection.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/scheduled_collection.py)

### 분석 및 전략

- [`analysis.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/market/analysis.py)
- [`analyze_daily_prices.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/analyze_daily_prices.py)
- [`golden_cross.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/strategy/golden_cross.py)
- [`generate_golden_cross_signals.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/generate_golden_cross_signals.py)
- [`generate_market_report.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/generate_market_report.py)
- [`generate_backtest.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/generate_backtest.py)

### 대시보드

- [`service.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/service.py)
- [`streamlit_dashboard.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/streamlit_dashboard.py)
- [`streamlit_reports.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/streamlit_reports.py)
- [`streamlit_watchlist.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/streamlit_watchlist.py)
- [`report_favorites.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/report_favorites.py)

## 현재 진행 상태

- [x] KIS 연동 기반 수집 구조
- [x] DB snapshot 저장 구조
- [x] 기본 지표 계산
- [x] 골든크로스 전략 구현
- [x] 골든크로스 신호 생성
- [x] 시장 리포트 생성
- [x] 골든크로스 백테스트 초안
- [x] Streamlit 대시보드
- [x] 리포트 해석 탭 단일 리포트 본문 표시
- [x] 리포트 해석 탭 전략별 판단 요약 표시
- [x] 리포트 관심종목(즐겨찾기) 저장 및 관심종목 탭
- [x] 다중 종목 배치 수집
- [x] 정기 수집 스케줄링 초안
- [ ] 백테스트 결과 시각화
- [ ] 모의투자 주문 실행
- [ ] 실거래 주문 실행
- [ ] 리스크 관리 정책 자동화

전체 작업 현황은 아래 문서를 참고합니다.

- [`docs/tasks/00_summary.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/00_summary.md)
- [`docs/strategies/00_summary.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/strategies/00_summary.md)

## 참고 자산

초기 구현과 구조 설계 시 아래 reference를 참고합니다.

- `reference/open-trading-api/`

다만 현재 프로젝트는 reference를 그대로 복사하지 않고, 필요한 기능을 분리해서 독립 프로젝트 구조로 정리하는 방향을 따릅니다.
