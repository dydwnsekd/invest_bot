# invest_bot

국내주식 데이터를 수집하고, 지표를 계산하고, 전략 신호를 생성해 확인할 수 있는 Python 기반 자동매매 연구 프로젝트입니다.

현재는 실거래 자동화보다는 아래 흐름을 안정적으로 만드는 데 초점을 두고 있습니다.

1. 데이터 수집
2. CSV 저장
3. 지표 계산
4. 전략 신호 생성
5. 대시보드 확인
6. 테스트 기반 검증

## 현재 구현 범위

### 데이터 수집

- 국내주식 일봉 데이터 수집
- 종목 기본정보 수집
- 투자자 수급 일별 데이터 수집
- CSV 저장
- 다중 종목 배치 수집

### 분석

- 일봉 CSV 로드
- 기본 컬럼 정규화
- 이동평균 계산
  - `ma_5`
  - `ma_20`
  - `ma_60`
- 거래량 이동평균 계산
  - `volume_ma_5`
- RSI 계산
  - `rsi_14`

### 전략

- 전략 공통 인터페이스
- 샘플 전략
- 골든크로스 전략
- 골든크로스 신호 생성 잡

### 대시보드

- raw / processed 데이터 조회
- 컬럼 선택
- 표시 행 수 선택
- 종목명 표시
- 컬럼 설명 표시
- 테스트 결과 표시
- 골든크로스 최신 신호 표시

### 테스트

- `pytest` 기반 테스트
- 전략 테스트
- 수집기 테스트
- 분석 테스트
- 대시보드 테스트
- 테스트 결과를 대시보드에서 확인하는 흐름 지원

## 프로젝트 구조

```text
invest_bot/
  agent.md
  README.md
  docs/
    tasks/
    strategies/
  config/
    app.yaml.example
    kis_credentials.yaml.example
  reference/
    open-trading-api/
  scripts/
    run_collection.py
    run_daily_analysis.py
    run_golden_cross_signals.py
    run_dashboard.py
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

- [`config/app.yaml.example`](./config/app.yaml.example) -> `config/app.yaml`
- [`config/kis_credentials.yaml.example`](./config/kis_credentials.yaml.example) -> `config/kis_credentials.yaml`

실제 키 파일은 `.gitignore`에 포함되어 있어 저장소에 올라가지 않습니다.

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

대시보드에서 테스트 결과까지 보고 싶으면:

```powershell
python scripts/run_tests.py
```

특정 테스트만 실행:

```powershell
python scripts/run_tests.py tests/test_golden_cross_strategy.py tests/test_sample_strategy.py
```

### 2. 단일 종목 수집

```powershell
python scripts/run_collection.py 005930
```

### 3. 다중 종목 배치 수집

```powershell
python scripts/run_collection.py 005930 000660 035420
```

심볼 파일 사용:

```powershell
python scripts/run_collection.py --symbols-file symbols.txt --days 60
```

### 4. 지표 계산

```powershell
python scripts/run_daily_analysis.py
```

### 5. 골든크로스 신호 생성

```powershell
python scripts/run_golden_cross_signals.py
```

### 6. 대시보드 실행

```powershell
python scripts/run_dashboard.py
```

브라우저 접속:

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 7. Streamlit 대시보드 초안 실행

```powershell
streamlit run streamlit_app.py
```

이 버전은 기존 admin 흐름을 유지한 채 Streamlit 스타일의 사이드바, 카드, 탭 구조로 재구성한 초안입니다.

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

### 분석 결과

```text
data/processed/domestic_stock/
  daily_prices_indicators/
  golden_cross_signals/
```

### 테스트 결과

```text
data/processed/test_reports/
```

## 현재 주요 파일

### 데이터 수집

- [`kis_client.py`](./src/invest_bot/clients/kis_client.py)
- [`domestic_stock.py`](./src/invest_bot/market/domestic_stock.py)
- [`collector.py`](./src/invest_bot/market/collector.py)
- [`collect_market_data.py`](./src/invest_bot/jobs/collect_market_data.py)

### 분석

- [`analysis.py`](./src/invest_bot/market/analysis.py)
- [`analyze_daily_prices.py`](./src/invest_bot/jobs/analyze_daily_prices.py)

### 전략

- [`base.py`](./src/invest_bot/strategy/base.py)
- [`sample.py`](./src/invest_bot/strategy/sample.py)
- [`golden_cross.py`](./src/invest_bot/strategy/golden_cross.py)
- [`generate_golden_cross_signals.py`](./src/invest_bot/jobs/generate_golden_cross_signals.py)

### 대시보드

- [`service.py`](./src/invest_bot/dashboard/service.py)
- [`server.py`](./src/invest_bot/dashboard/server.py)

## 현재 진행 상태

현재는 아래 단계까지 구현된 상태입니다.

- [x] KIS 연동 기반 수집 구조
- [x] CSV 저장 구조
- [x] 기본 지표 계산
- [x] 골든크로스 전략 구현
- [x] 골든크로스 신호 생성
- [x] 로컬 대시보드
- [x] 테스트 결과 대시보드 표시
- [x] 다중 종목 배치 수집
- [ ] 백테스트
- [ ] 모의투자 주문 실행
- [ ] 실거래 주문 실행
- [ ] 리스크 관리 정책 자동화

전체 작업 현황은 아래 문서를 참고합니다.

- [`docs/tasks/00_summary.md`](./docs/tasks/00_summary.md)
- [`docs/strategies/00_summary.md`](./docs/strategies/00_summary.md)

## 참고 자산

초기 구현과 구조 설계는 아래 reference를 참고합니다.

- `reference/open-trading-api/`

다만 현재 프로젝트는 reference를 그대로 복사하는 방식이 아니라, 필요한 기능을 분리해 독립 프로젝트 형태로 정리하는 방향을 따릅니다.

## 다음 추천 작업

다음으로 자연스러운 작업은 아래 중 하나입니다.

1. 골든크로스 신호 히스토리를 대시보드에서 더 명확하게 표시
2. 백테스트 초안 추가
3. 추세 필터 전략 추가
4. 투자자 수급 기반 커스텀 전략 추가
5. 모의투자 주문 흐름 연결
