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

## Snapshot 기준일 날짜 계약 (2026-10-27)

`dataset_frames.as_of_date`는 `date → trade_date → stck_bsop_date` 순서에서 첫 유효 컬럼의 최대 달력 날짜로 저장한다. 한 컬럼의 유효 날짜가 없을 때만 다음 컬럼으로 넘어가며, 모두 무효이거나 빈 프레임이면 NULL이다. KIS 응답이 역순이어도 프레임 행 순서에 의존하지 않는다.

[DB frame 저장](../../src/invest_bot/db/frame_storage.py)은 YYYYMMDD 정수·정수값 실수·문자열과 `.0` 문자열을 같은 날짜로 읽는다. `20261002`, `20261002.0`, `"20261002"`, `"20261002.0"`는 모두 `2026-10-02`다. 잘못된 월·일, 비8자리 숫자, 분수 날짜, bool·결측·무한대와 list/dict/ndarray 등 비스칼라는 날짜로 사용하지 않으며 epoch로 추정하지 않는다. 기존 날짜/시각과 ISO 문자열은 그 값의 현지 달력 날짜를 사용하고 UTC 날짜로 옮기지 않는다. 혼합 표현·nullable dtype·반복 index가 있어도 유효 날짜의 최댓값을 보존한다.

이는 새 `save`의 기준일 metadata 추출 계약이다. 원본 DataFrame·JSON payload·행 수·repository 정렬은 유지하며, 과거 저장된 1970년/NULL 기준일을 자동으로 다시 쓰지 않는다. 실거래·휴장일·미래일 판단 정책도 추가하지 않는다. [G01b 현재 상태·검증](../operations/improvements/data.md#g01b), [기능 회귀](../../tests/test_db_frame_storage.py)를 따른다. 별도 정규화 fact 저장과 CSV/리포트 파서의 계약을 한꺼번에 바꾸는 작업이 아니다.

main `1e73d60` + 미커밋 G01b에서 기존 데이터→QA→데이터 보완→QA를 순차 재사용했다. 기능49개를 추가해 수정 전23 failed / 30 passed, 수정 후53 passed와 기존 소비자188 passed를 확인했다. 별도 [독립 QA40개](../../tests/test_g01b_independent_qa.py)는 실제 SQLite save/load·기준일·컬럼 우선순위·CSV 왕복·NULL/동률 정렬·기존 payload 호환·snapshot 이후 frame consumer의 추가 SELECT0회를 검사한다. 최초30 passed / 10 failed 중2개는 기존 JSON dtype 정규화를 QA가 불변 대상으로 오인한 기대값으로, 기준 코드의 실제 roundtrip과 비교하도록 QA 파일만 보정했다. 나머지8개는 기존 코드에서 저장되던 무효 list/ndarray가 새 guard에서 예외를 내는 실제 회귀였다. 최초 합산273 passed / 8 failed를 보존한 뒤 scalar guard2줄을 추가했다.

보완 후 독립40개 전체와 합산281 passed를 QA가 새 실행·manifest262개 대조로 승인했다. 메인은 동일 제품/기능/독립 테스트의 최종 소스 격리 후보에서 기본1100 passed / 2 deselected / 36 warnings,40.85초를 확인했다. 경고36개에는 기존 pandas/Alembic32개와 이번 QA의 기준 코드 비교/기존 JSON decoder 경계 입력4개가 포함되며 숨기지 않았다. 범용 JSON decoder나 다른 날짜 파서의 향후 버전 대응은 이번 변경에서 개편하지 않았다.

- 최초 기능 명령: `.venv/bin/python -B -m pytest tests/test_db_frame_storage.py -q --tb=short`.
- 보완 후 관련 명령: `.venv/bin/python -B -m pytest tests/test_db_frame_storage.py tests/test_market_report_generator.py tests/test_daily_price_analyzer.py tests/test_csv_storage.py tests/test_db_write_path.py tests/test_dataset_frame_list_latest_batch.py tests/test_watchlist_snapshot_queries.py tests/test_dashboard_snapshot_frame_loader.py tests/test_dashboard_service.py tests/test_streamlit_state.py tests/test_streamlit_dashboard.py tests/test_run_market_report.py tests/test_g01b_independent_qa.py -q --tb=short`.
- 기본 명령: `.venv/bin/python -B scripts/run_tests.py --suite default -q --tb=short`. 실제 실행은 추적 파일만 복사한 격리 cwd에서 `env -i`·`PYTHONDONTWRITEBYTECODE=1`·`TMPDIR=/private/tmp`와 원본 venv의 절대 Python 경로를 사용했다. 기본 suite는 최종 소스에서1회 실행했다.

단계별 RED/GREEN 로그·JUnit·입력/선택 파일 해시는 임시 G01b 증거 디렉터리에 보존했다. 원본·데이터·QA·기본 후보의 제품/테스트 해시를 대조했으며, 전체 기능 suite 이후에는 문서만 갱신·동기화하고 링크/ID를 별도로 검사했다. 실제 설정·백업·관련 없는 추적 파일·HEAD·Git index는 보존했다. Python3파일 AST/컴파일·`git diff --check`와 Markdown57개·로컬 링크723개·문서 ID57개·개념12개/관계14개 검사를 통과했고 누락·중복·미등록은0개다. 독립 SQLite 검증을 실제 PostgreSQL·운영 데이터·원격 CI 통과로 해석하지 않는다. 기존 저장 metadata의 재쓰기·migration·실제 API/DB·서비스·commit·push는 수행하지 않았다.

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
