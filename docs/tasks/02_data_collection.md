# Task 02. Data Collection

## 목표

국내주식 자동매매에 필요한 데이터를 안정적으로 수집하고, 여러 종목을 반복적으로 운영할 수 있는 수집 기반을 만든다.

## 완료된 항목

- [x] KIS REST 인증 및 GET 요청 클라이언트 구현
- [x] 국내주식 일봉 데이터 수집 구현
- [x] 종목 기본정보 수집 구현
- [x] 투자자 수급 일별 데이터 수집 구현
- [x] 수집 결과 CSV 저장 구현
- [x] 단일/다중 종목 수집 스크립트 작성
- [x] 파일 기반 정기 다중 종목 수집 스케줄링 초안 구현
- [x] 1회 실행 및 테스트용 제한 실행 지원

## 남은 항목

- [ ] 종목 리스트 입력 방식 고도화
- [ ] 분봉 데이터 수집
- [ ] 현재가/호가 데이터 수집
- [ ] 공매도/프로그램 매매/뉴스 수집
- [ ] 수집 실패 재시도 및 상세 로그 고도화

## 데이터 구조

```text
data/raw/domestic_stock/
  daily_prices/
  daily_prices_summary/
  stock_info/
  investor_daily/
  investor_daily_summary/
```

## 스케줄링 관련 파일

- [`scheduled_collection.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/scheduled_collection.py)
- [`run_scheduled_collection.py`](/C:/Users/user/PycharmProjects/invest_bot/scripts/run_scheduled_collection.py)
- [`collection_schedule.yaml.example`](/C:/Users/user/PycharmProjects/invest_bot/config/collection_schedule.yaml.example)

## 관련 파일

- [`kis_client.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/clients/kis_client.py)
- [`domestic_stock.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/market/domestic_stock.py)
- [`collector.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/market/collector.py)
- [`storage.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/market/storage.py)
- [`collect_market_data.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/collect_market_data.py)
- [`run_collection.py`](/C:/Users/user/PycharmProjects/invest_bot/scripts/run_collection.py)
