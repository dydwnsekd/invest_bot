# invest_bot

국내주식 데이터를 수집하고, 지표를 계산하고, 전략 신호와 시장 리포트를 생성해 확인할 수 있는 Python 기반 자동매매 연구 프로젝트입니다.

현재는 실거래 자동화보다 아래 흐름을 안정적으로 만드는 데 초점을 두고 있습니다.

1. 데이터 수집
2. CSV 저장
3. 지표 계산
4. 전략 신호 생성
5. 시장 리포트 생성
6. 대시보드 확인
7. 테스트 기반 검증

## 현재 구현 범위

### 데이터 수집

- 국내주식 일봉 데이터 수집
- 종목 기본정보 수집
- 투자자 수급 일별 데이터 수집
- 다중 종목 배치 수집
- 정기 다중 종목 수집 스케줄링 초안

### 분석

- 일봉 CSV 로드 및 컬럼 정규화
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
- 골든크로스 신호 생성
- 현재 장 상황 요약 리포트 생성
- 골든크로스 백테스트 초안

### 대시보드

- HTML 기반 로컬 대시보드
- Streamlit 기반 대시보드 초안
- 원본/분석/신호/리포트 데이터 조회
- 시장 리포트 생성 실행
- 데이터 수집 실행
- 지표 계산 실행
- 골든크로스 신호 생성 실행
- 전체 파이프라인 실행
- 정기 수집 상태와 최근 로그 표시

### 테스트

- `pytest` 기반 테스트
- 수집, 분석, 전략, 리포트, 대시보드, 스케줄링, 백테스트 테스트 포함

### DB 마이그레이션 초안

- Postgres 기반 docker-compose 초안 포함
- `.env` / 환경변수 기반 DB 설정 로드 지원
- 저장소(Repository) 계약과 ERD/마이그레이션 계획 문서화 완료
- 실제 Alembic/SQLAlchemy 마이그레이션은 아직 미구현이며, 현재 `migrate` 컨테이너는 준비 상태 점검만 수행

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
    kis_credentials.yaml.example
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
- [`config/kis_credentials.yaml.example`](/C:/Users/user/PycharmProjects/invest_bot/config/kis_credentials.yaml.example) -> `config/kis_credentials.yaml`
- [`config/collection_schedule.yaml.example`](/C:/Users/user/PycharmProjects/invest_bot/config/collection_schedule.yaml.example) -> `config/collection_schedule.yaml`

실제 설정 파일은 `.gitignore`에 포함되어 있습니다.

## 설치

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```

## 실행 방법

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

### 3. 다중 종목 배치 수집

```powershell
python scripts/run_collection.py 005930 000660 035420
```

종목 파일 사용:

```powershell
python scripts/run_collection.py --symbols-file symbols.txt --days 60
```

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

### 8. 백테스트 초안 실행

```powershell
python scripts/run_backtest.py 005930
```

기본 규칙:

- `buy` 신호 발생 시 다음 거래일 종가 진입
- `sell` 신호 발생 시 다음 거래일 종가 청산
- 미청산 포지션은 마지막 거래일 종가로 강제 종료

### 9. HTML 대시보드 실행

```powershell
python scripts/run_dashboard.py
```

브라우저:

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 10. Streamlit 대시보드 실행

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

현재 저장소의 실행 경로는 아직 CSV 기반입니다. 다만 Postgres 전환을 위한 설계 초안은 아래 문서로 정리되어 있습니다.

- [`docs/operations/db_migration_plan.md`](docs/operations/db_migration_plan.md)

이 문서에는 다음 내용이 포함됩니다.

- 현재 CSV 저장 구조 기준 1차 ERD
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
- [`server.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/server.py)
- [`streamlit_dashboard.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/streamlit_dashboard.py)

## 현재 진행 상태

- [x] KIS 연동 기반 수집 구조
- [x] CSV 저장 구조
- [x] 기본 지표 계산
- [x] 골든크로스 전략 구현
- [x] 골든크로스 신호 생성
- [x] 시장 리포트 생성
- [x] 골든크로스 백테스트 초안
- [x] HTML 대시보드
- [x] Streamlit 대시보드 초안
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

git 연동 test