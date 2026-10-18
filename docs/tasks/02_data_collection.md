# Task 02. Data Collection

## 목표

국내주식 자동매매에 필요한 데이터를 안정적으로 수집하고, 여러 종목을 반복적으로 운영할 수 있는 수집 기반을 만든다.

## 완료된 항목

- [x] KIS REST 인증 및 GET 요청 클라이언트 구현
- [x] 국내주식 일봉 데이터 수집 구현
- [x] 종목 기본정보 수집 구현
- [x] 투자자 수급 일별 데이터 수집 구현
- [x] 수집 결과 DB snapshot 저장 구현
- [x] 단일/다중 종목 수집 스크립트 작성
- [x] 파일 기반 정기 다중 종목 수집 스케줄링 초안 구현
- [x] 1회 실행 및 테스트용 제한 실행 지원
- [x] `INVEST_BOT_*` 환경변수 기반 KIS/DB 런타임 설정 지원
- [x] KIS access token 파일 캐시로 반복 실행 시 `tokenP` 재발급 최소화
- [x] 명시적 기간 보충 수집 CLI: 가격·수급의 과거 구간 반복 조회와 별도 history snapshot 저장, 지표·신호·리포트 갱신 ([검증 범위](#보충-수집-검증-범위))

## 남은 항목

- [ ] 종목 리스트 입력 방식 고도화
- [ ] 분봉 데이터 수집
- [ ] 현재가/호가 데이터 수집
- [ ] 공매도/프로그램 매매/뉴스 수집
- [ ] 수집 실패 재시도 및 상세 로그 고도화

## 데이터 구조

### 장기 보충 수집 (2026-10-13)

`scripts/run_historical_collection.py --start YYYY-MM-DD --end YYYY-MM-DD`는 저장된 리포트 종목 또는 명시한 종목의 가격·수급을 날짜별로 추가 조회합니다. 신규 snapshot 이름은 `<symbol>_<start>_<end>_history.csv`이며 이전 짧은 snapshot은 보존합니다. API 오류·유효하지 않은 날짜·무진행·상충하는 중복·페이지 한도 초과를 차단하고, 긴 기간은 최초 31일 구간의 별도 조회를 대조해 시작 부분 누락을 차단합니다. 초기 구간에 데이터가 없는 신규 상장 종목은 이 전용 경로에서 전체 기간 확보를 보장하지 않고 실패 처리할 수 있습니다.

2026-10-13 사용자 요청으로 기존 16개 종목의 2024-10-13~2026-10-13 범위를 수집했습니다. 실제 가격 시작일은 2024-10-14이며, 당시 10월 13일 가격은 장중값입니다. 수급은 2026-10-12까지 요청하고 리포트는 입력 공통 기준일을 사용합니다. 당시 DB 재조회·초기 구간 대조의 상세 기록은 로컬 제외 파일 `docs/operations/session_reports/2026-10-13_history_backfill.md`에 보관하며, 재현 가능한 검증 범위는 아래에 정리합니다.

이 CLI는 기본 단건·배치·대시보드·스케줄러의 수집 경로를 교체하지 않습니다. 따라서 기본 경로의 기간 확보 작업 [G08a](../operations/improvements/data.md#g08a)는 대기를 유지합니다.

### 보충 수집 검증 범위

[전용 회귀](../../tests/test_backfill_history.py)는 가격·수급 요청일 이동, 동일 중복 제거·상충 중복 차단, API 실패·빈 시작/꼬리·무진행·페이지 한도·초기31일 누락 차단, 저장 전 양쪽 수집 완료, 기존 snapshot 이름 보존, 유한 가격·음수 거래량·OHLC·거래정지 입력을 확인합니다. API는 fake client, 저장은 메모리 spy로 대체하며 실제 운영 호출을 하지 않습니다.

2026-10-15 코드·회귀·관련 문서를 `c1c55cd`로 main에 반영했다. 커밋 범위만 격리한 당시 검증은 전용26 passed, 기본858 passed / 2 deselected / 32 warnings다. 실제 CLI help는0, 잘못된 기간은2로 종료했고 실제 API/운영 DB 호출은 하지 않았다. 10월17일 지식 갱신에서 이 커밋의 코드·문서 연결을 대조했으며 수집을 다시 실행한 것은 아니다.

2026-10-13 당시 16종목 운영 수집/DB 재조회는 별도 관측 증거이며 새 코드의 테스트 성공으로 재사용하지 않습니다. 정규 수집 경로의 G08a 완료와 이 전용 CLI의 구현 완료를 구분합니다.

기본 저장 대상은 DB의 `dataset_frames`이며, 아래 경로는 파일 fallback 또는 기존 CSV 기반 호환 경로다.

`dataset_frames.as_of_date`는 날짜 컬럼의 최대 날짜로 저장한다. KIS 일봉 응답은 최신 거래일이 첫 행으로 올 수 있으므로 프레임 행 순서에 의존하지 않는다.

```text
data/raw/domestic_stock/
  daily_prices/
  daily_prices_summary/
  stock_info/
  investor_daily/
  investor_daily_summary/
```

## 스케줄링 관련 파일

- [`scheduled_collection.py`](../../src/invest_bot/jobs/scheduled_collection.py)
- [`run_scheduled_collection.py`](../../scripts/run_scheduled_collection.py)
- [`collection_schedule.yaml.example`](../../config/collection_schedule.yaml.example)

## 관련 파일

- [`kis_client.py`](../../src/invest_bot/clients/kis_client.py)
- [`domestic_stock.py`](../../src/invest_bot/market/domestic_stock.py)
- [`collector.py`](../../src/invest_bot/market/collector.py)
- [`storage.py`](../../src/invest_bot/market/storage.py)
- [`collect_market_data.py`](../../src/invest_bot/jobs/collect_market_data.py)
- [`run_collection.py`](../../scripts/run_collection.py)
