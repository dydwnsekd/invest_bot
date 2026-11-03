# Task 02. Data Collection

## 목표

국내주식 자동매매에 필요한 데이터를 안정적으로 수집하고, 여러 종목을 반복적으로 운영할 수 있는 수집 기반을 만든다.

## 완료된 항목

- [x] KIS REST 인증 및 GET 요청 클라이언트 구현
- [x] 국내주식 일봉 데이터 수집 구현
- [x] G08a 일반 일봉 구간 수집·실제 범위/불확실성·수집 성공과 분석 준비 분리 ([현재 계약](#일반-일봉-요청-범위-2026-11-02))
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

이 CLI는 기본 단건·배치·대시보드·스케줄러의 수집 경로를 교체하지 않습니다. 전용 CLI만 반영한10월13일 시점의 일반 수집 G08a는 대기였으며 현재 범위는 [일반 일봉 계약](#일반-일봉-요청-범위-2026-11-02)을 따릅니다.

### 보충 수집 검증 범위

[전용 회귀](../../tests/test_backfill_history.py)는 가격·수급 요청일 이동, 동일 중복 제거·상충 중복 차단, API 실패·빈 시작/꼬리·무진행·페이지 한도·초기31일 누락 차단, 저장 전 양쪽 수집 완료, 기존 snapshot 이름 보존, 유한 가격·음수 거래량·OHLC·거래정지 입력을 확인합니다. API는 fake client, 저장은 메모리 spy로 대체하며 실제 운영 호출을 하지 않습니다.

2026-10-15 코드·회귀·관련 문서를 `c1c55cd`로 main에 반영했다. 커밋 범위만 격리한 당시 검증은 전용26 passed, 기본858 passed / 2 deselected / 32 warnings다. 실제 CLI help는0, 잘못된 기간은2로 종료했고 실제 API/운영 DB 호출은 하지 않았다. 10월17일 지식 갱신에서 이 커밋의 코드·문서 연결을 대조했으며 수집을 다시 실행한 것은 아니다.

2026-10-13 당시 16종목 운영 수집/DB 재조회는 별도 관측 증거이며 새 코드의 테스트 성공으로 재사용하지 않습니다. 정규 수집 경로의 G08a 완료와 이 전용 CLI의 구현 완료를 구분합니다.

기본 저장 대상은 DB의 `dataset_frames`이며, 아래 경로는 파일 fallback 또는 기존 CSV 기반 호환 경로다.

## 일반 일봉 요청 범위 (2026-11-02)

[G08a](../operations/improvements/data.md#g08a) 코드는 2026-11-03 `c1b7810`에 반영됐고 관련 문서는 검토 작업본이다. 아래 `8d11305` + 당시 미커밋 후보는 구현·검증의 기준이며 현재 HEAD와 구분한다. 기존 데이터 구현 → 메인 UI/스케줄러 연결 → 기존 QA → 데이터 보완 → QA 재검증 → 메인 기본 검증을 순차 수행했다. 실제 설정·운영 데이터·API/토큰·운영 DB·서비스·commit·push는 사용/변경하지 않았다.

일봉의 요청 시작/종료일을 구간별로 정상 처리했는지와 실제 관측 범위·짧은 사유·분석 준비를 구분한다. 요청365일은 달력일이며365행을 요구하지 않는다. 주말/휴일 경계에 행이 없다는 이유만으로 정상 수집을 실패로 보지 않는다. API 구간 요청 완료는 모든 거래일의 존재를 캘린더로 검증했다는 의미가 아니다.

원인이 확인되지 않은 짧은 범위는 신규 상장/휴장으로 단정하지 않는다. 실제 확보 날짜·행수·요청 횟수와 근거/불확실성을 결과에 표시한다. 페이지 오류·유효하지 않은 값·범위밖/무진행·충돌 중복·상한 초과 등 실제 미충족은 완료로 저장하지 않는다. 정상 처리한 유효한 짧은 자료는 보존할 수 있지만 기존 전략의 최소60개 일봉을 충족하지 않으면 분석·신호·리포트 대상으로 넘기지 않는다. 수집 성공과 분석 준비는 별도 결과다.

초기 데이터636개·메인 소비자29개 합산665개 이후 독립 QA에서 상장 설명이 invalid_calendar_evidence의 unknown을 complete로 덮는 실제 결함을 CSV/SQLite로 확인했다(신규4 passed / 2 failed). listing 보강을 request_complete=True인 complete·거래일 미검증 결과로 제한해 거절/검증된 캘린더 진단 전체를 보존했다. 보완 자체8개·초기 독립6개를 포함한650개 통과 후 독립 범위를 재검증했다. 다음 확장 독립68개에서 CSV/SQLite 숫자 날짜를1970년으로 읽는 기존 consumer 결함2개가 드러났다(관련739 passed / 2 failed). 메인은 기존G01b scalar parser를 날짜 조회·관심종목 min/max·누적 unique 준비 판정에 재사용하고 own21개를 추가해787 passed를 확인했다. 최초9 failed / 109 passed와 임시 patch 인용 오류의 부분 적용780 passed / 7 failed도 보존했다. 이후 같은 source의 독립 재검증을 마쳤다. 최종 신규 기능144개·독립82개, 관련801 passed와 최종 소스 격리 후보 기본1819 passed / 2 deselected / 36 warnings다. 각 단계의 초기 실패 로그/XML은 별도 보존했다. 별도 명시적 가격/수급 보충 CLI의 요청/retry/pacing 계약은 유지한다.

### 요청·응답 처리와 판정

일반 facade는100달력일 이하의 겹치지 않는 inclusive 구간을 전부 조회한다. 기본365일 거리는 양끝을 포함하면366개 날짜 위치이며 거래일365행을 뜻하지 않는다. 요청당1회 시도·기본1.1초 pacing·최대100구간이며 상한 초과는 호출 전에 거부한다. 이 대기/상한은 로컬 정책이다. 잘못된 날짜/값·OHLC·무한대 수치·범위밖/무진행·충돌 중복·cap 관련 비정상 응답·API/페이지 오류는 중단하며 실패한 일부 가격을 완료 tuple로 반환하지 않는다.

`status=complete`는 정상 구간 요청을 모두 마친 비어 있지 않은 유효 이력이다. 신뢰 캘린더를 별도로 제공해 관측일 집합이 일치할 때만 `trading_days_verified=True`다. 기본 경로에는 거래일 캘린더를 새로 설치하지 않았다. 전 구간이 빈 결과는 근거 없이 휴장/미상장으로 성공시키지 않으며, 명시적으로 session0개인 신뢰 캘린더만 빈 완료를 증명할 수 있다. 이 경우 snapshot은 저장하지 않고 분석 미준비다.

상장 설명은 같은 종목의 하나의 유효한 공식 listing 날짜와 실제 관측 경계를 대조한다. 복수 시장 상장일·미래/무효/요청종료일 이후 날짜는 신규 상장 근거가 아니며, 무효 metadata는 정상 구간 요청 완료를 임의로 뒤집지 않는다. 실제 관측과 유효 상장일의 모순·캘린더 누락은 실패다. 기존 backfill의 zero-volume/유효 종가 입력 허용은 유지하고 거래정지 여부를 새로 추정하지 않는다.

### 추가 결과 필드와 호환

`BatchCollectionResult`는 기존 생성자·키·success/failed 상태를 유지하고 `price_coverage` dict(기본 빈 dict), `analysis_ready` bool/legacy None(기본 None)을 추가한다. facade의 `(summary, prices)` 반환과 `prices.attrs['price_coverage']`를 함께 사용한다.

| price_coverage 키 | 의미 |
| --- | --- |
| `status`, `reason` | complete/unknown/incomplete/legacy와 API 구간 처리·실패 사유 코드 |
| `requested_start`, `requested_end`, `effective_start` | 원래 요청 inclusive ISO 날짜와 확인된 유효 시작 경계 |
| `observed_start`, `observed_end`, `rows` | 실제 관측 최소/최대 ISO 날짜(없으면 빈 문자열)와 unique 행수 |
| `requests`, `window_count`, `termination` | 시도한 요청 수·예정 구간 수·종료 사유 |
| `request_complete`, `trading_days_verified`, `expected_sessions` | 요청 구간 처리 완료와 캘린더 검증 여부/기대 일수(int 또는 None) |
| `listing_date`, `range_reason` | 확인된 상장 날짜(없으면 빈 문자열)와 경계 설명/불확실성 |

모든 값은 str/int/bool/None이다. job은 기존 `successful_symbols`·`success_count`를 저장/종목 처리 성공으로 유지하고 `analysis_ready_symbols/count`, `analysis_unready_symbols/count`, `coverage_complete_symbols`, `coverage_unknown_symbols`, `coverage_incomplete_symbols`를 추가한다. coverage 목록은 API 조회 축이므로 이후 저장 실패 종목이 complete 목록에도 있을 수 있다. 후속 실행은 종목 처리 성공과 분석 준비를 함께 확인한다.

True만 명시적 준비, None만 기존 생성자 호환 fallback이며 False·문자열·0/1·컨테이너 등 잘못된 타입은 미준비다. 새 준비 목록이 비었거나 잘못됐으면 UI에서 기존 성공 목록으로 되돌리지 않는다. 새 집계 키가 아예 없는 legacy UI 결과만 이전 동작을 유지한다. 가격 attrs가 없는 기존 사용자 주입 tuple은 legacy로 표시하고 기존 최소60행 성공/실패 정책을 보존한다. 이 legacy는 새 API 구간 완료의 증거가 아니다.

### 저장·소비자 경계

페이지 실패는 가격 저장과 후속 stock-info/수급 호출0회이며 이전 성공 종목은 보존한다. 저장 단계 자체의 실패는 기존처럼 일부 `saved_files`를 남길 수 있다. 실패 진단의 관측 날짜/행수는 저장량이 아니므로 상태와 저장 목록을 함께 읽는다.

[일반 수집·전체 파이프라인](../../src/invest_bot/dashboard/streamlit_actions.py)과 [백테스트 준비](../../src/invest_bot/dashboard/streamlit_backtest.py)는 실제 범위/횟수·불확실성을 안내하고 분석 준비 종목만 실행한다. [관심종목](../../src/invest_bot/dashboard/streamlit_watchlist.py)은 완료된 짧은 이력의 저장과 분석을 구분하고, 추가 갱신·오래된 리포트 재생성 모두 누적 유효 일봉 수를 확인한다. 외부 legacy boolean callback은 기존 의미를 유지한다. [스케줄러](../../src/invest_bot/jobs/scheduled_collection.py)는 종목 상태·저장 수·primitive 범위/분석 메타데이터만 새 finished 필드에 기록한다. 원본 응답·오류 문자열·저장 경로를 새 진단에 복사하지 않는다.

범위 metadata는 수집 결과/frame attrs·작업 메시지·로그의 계약이며 DB raw payload에 새 attrs 복원 규격을 추가하지 않는다. 기존 저장 이력을 자동 보충/재작성하지 않으며 명시적으로 요청한 새 구간부터 정책을 적용한다. 이전의 잘린 이력을 증분 갱신했다고 전체 과거 범위가 검증된 것으로 해석하지 않는다. [선택 이유](../decisions/0002-collection-coverage-and-analysis.md), [데이터 회귀](../../tests/test_collection_coverage.py), [소비자 회귀](../../tests/test_collection_coverage_consumers.py)를 따른다.

### 검증과 남은 범위

[독립 QA](../../tests/test_g08a_independent_qa.py)는 실제 일반 facade·root job과 임시 CSV/SQLite를 연결해 구간 합치기·짧은 저장/분석 제외·실패 전 저장0·저장 단계 부분 성공·앞선 성공 종목 보존을 확인했다. UI action·전체 파이프라인·백테스트 준비·관심종목의 누적/오래된 이력·순수 조회와 실제 JSONL logger/status reader도 검증했다. 가상 API/시계/대기로 실행했으며 실제 외부 호출이나 긴 sleep은 없다. 신규 기능144개(데이터94·소비자50)와 독립82개를 추가했다.

- 데이터 보완 명령: `.venv/bin/python -B -m pytest tests/test_collection_coverage.py tests/test_backfill_history.py tests/test_domestic_stock_collector.py tests/test_db_write_path.py tests/test_repository_interfaces.py tests/test_csv_storage.py tests/test_db_frame_storage.py tests/test_scheduled_collection.py tests/test_streamlit_dashboard.py tests/test_streamlit_backtest.py tests/test_dashboard_action_scope.py tests/test_watchlist_snapshot_queries.py tests/test_dashboard_snapshot_frame_loader.py tests/test_dashboard_summary_flow.py tests/test_run_market_report.py tests/test_g08a_independent_qa.py -q --tb=short`. 데이터 격리본의 초기 독립6개를 포함한650 passed다.
- 보완 후 독립 합산: 같은 관련 집합에 `tests/test_collection_coverage_consumers.py`·`tests/test_dashboard_data_status.py`와 확장 독립 QA를 포함해801 passed다. 정확한 최종 명령은 QA 보고서와 아래 보존 증거를 따른다.
- 기본 명령: `.venv/bin/python -B scripts/run_tests.py --suite default -q --tb=short`. 최종 소스 격리 후보에서1회 실행해1819 passed / 2 deselected / 36 warnings, 92.54초다. 경고는 숨기지 않고 로그에 보존했다.

명령은 각 격리 cwd에서 `env -i`·`PYTHONDONTWRITEBYTECODE=1`·`TMPDIR=/private/tmp`, 원본 venv의 절대 Python 실행기를 사용했다. 처음 추적267개만 격리했고 QA는 보완 후271입력을 보존했다. 독립 회귀 통합 후 기본 후보272입력의 실행 전후 불변성과 원본·데이터·QA·기본 후보의 소유 source SHA를 대조했다. 초기 RED·주입 오류·독립 결함·보완·최종 명령/log/JUnit/manifest는 로컬 제외 증거 `/private/tmp/invest-bot-g08a-qepr3po9`에 보존한다. 재현 회귀는 Git 관리 대상이고 임시 증거 경로는 지속 보관을 보장하지 않는다.

실제 설정4개·백업·HEAD·Git index·관련 없는 추적 파일을 보존한다. QA는 승인 보고서·801개 XML/log 저장 후 마지막 응답 전 사용량 제한으로 종료됐다. 보고서에 기재된 최종 audit log/manifest는 미작성 상태였으므로 초기 RED manifest를 승인 근거로 재사용하지 않았다. 메인이 별도 `MAIN-QA-integrity-completion.json`으로271입력 SHA/모드·최종82개 source hash·기존68개 prefix·801개 XML을 새로 대조했다. 최종 Git 후보의 정적 검사도 메인이 완료했다. Python15개 AST/메모리 compile·whitespace와 Markdown58개·로컬 링크793개·문서ID58개·개념14개/관계18개 검사를 통과했고 누락/중복/미등록은0개다. 프로젝트에 별도 lint/typecheck 설정은 없어 해당 도구의 통과를 주장하지 않는다. 원격 CI·실제 KIS/API/토큰·운영 DB/PG·서비스/브라우저·배포는 이번 로컬 검증 범위 밖이며 과거 snapshot을 자동 보충하지 않는다. 기본 캘린더가 없어 구간 완료와 모든 거래일 검증은 다르다. 다음 기능 후보는 G08b이며 commit·push는 수행하지 않았다.

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
