# 개념과 구현 근거

최초 기준은 2026-09-17, 제품 커밋 `569cd97`이며 최신 문서 대조는 2026-10-17 main `efdc607` 기준이다. 저장 신호·날짜·차트 수급 계약과 이후 보충 수집·비교·슬라이딩 연구는 각 연결 문서의 기능별 커밋과 검증 범위를 따른다. 이 페이지는 확인한 핵심 개념의 지도이며 모든 소스 코드를 설명하는 명세는 아니다. 세부 사용자 설명은 해당 주제의 가이드에 둔다.

## 개념 사전

| ID | 개념과 의미 | 구현 근거 | 검증 근거 |
| --- | --- | --- | --- |
| K-SYMBOL | 종목코드·종목명·시장 구분. 마스터 메타데이터와 수집 중 placeholder를 구분한다. | [저장소](../../src/invest_bot/db/repositories.py), [마스터 동기화](../../src/invest_bot/market/master_sync.py) | [메타데이터·수급 저장 테스트](../../tests/test_db_write_path.py) |
| K-COLLECTION | 가격·기본정보·수급을 수집하고 snapshot과 선택적 정규화 저장을 수행한다. 실패 결과에도 저장 완료 목록이 남을 수 있다. | [수집기](../../src/invest_bot/market/collector.py), [정규화 저장](../../src/invest_bot/db/write_path.py) | [수집·부분 실패 테스트](../../tests/test_domestic_stock_collector.py) |
| K-SNAPSHOT | `dataset_frames`에 dataset/파일명 단위로 저장하는 raw·가공 DataFrame. CSV 파일 저장 구현과 구분한다. | [DB frame 저장](../../src/invest_bot/db/frame_storage.py) | [frame 저장 테스트](../../tests/test_db_frame_storage.py) |
| K-ASOF | 요청일·실제 관측일·공통 리포트 기준일은 서로 다를 수 있다. 리포트는 공통 기준일 이하의 입력을 선택한다. | [리포트 생성기](../../src/invest_bot/jobs/generate_market_report.py), [리포트 job](../../src/invest_bot/jobs/run_market_report.py) | [기준일 테스트](../../tests/test_market_report_generator.py), [job 테스트](../../tests/test_run_market_report.py) |
| K-STRATEGY | 데이터 준비 조건에 맞춰 신호를 생성하는 전략. 구현된 전략 목록과 후보 아이디어를 구분한다. 현재 지표와 함께 사용하는 기본 골든크로스 저장 신호는 [날짜·가격 정합성 계약](../tasks/05_strategy_backtest.md#저장-신호의-날짜가격-정합성-2026-10-12)을 따른다. | [전략 레지스트리](../../src/invest_bot/backtest/strategy_registry.py), [adapter](../../src/invest_bot/backtest/adapters.py) | [레지스트리 테스트](../../tests/test_backtest_registry.py), [저장 신호 계약](../../tests/test_backtest_saved_signals.py) |
| K-EQUITY | 백테스트의 일별 평가금액. 요약 MDD는 초기자산 peak와 보유 중 손실을 포함한다. 종목별 입력의 같은 거래일 중복은 [날짜 유일성 계약](../tasks/05_strategy_backtest.md#일별-입력의-날짜-유일성-2026-10-11)으로 차단한다. | [백테스트 runner](../../src/invest_bot/backtest/runner.py) | [일별 곡선·낙폭 테스트](../../tests/test_backtest_adapters_runner.py), [날짜 계약](../../tests/test_backtest_dates.py) |
| K-MIGRATION | 스키마 변경은 Alembic으로 적용한다. 초기화의 migrate-only와 full 모드는 외부 마스터 동기화 여부가 다르다. | [초기화](../../scripts/init_db.py), [migration 실행](../../src/invest_bot/db/migrate_runtime.py) | [초기화 모드](../../tests/test_init_db_modes.py), [실제 subprocess](../../tests/test_init_db_script.py) |
| K-DASHBOARD | 조회 화면과 명시적 실행 동작을 구분하는 Streamlit 제품 표면. 미통합 worktree 변경은 현재 기능으로 간주하지 않는다. | [대시보드 진입점](../../src/invest_bot/dashboard/streamlit_dashboard.py) | [대시보드 회귀](../../tests/test_streamlit_dashboard.py) |
| K-CHART-FLOW | 실제 관측일별 차트 수급. 유효 detail 우선, 무효 시 summary 자체의 날짜·값을 사용하며 서로 다른 source의 빈칸을 섞지 않는다. 차트의 미관측과 실제 0, 리포트 생성기의 입력 정책을 구분한다. [현재 차트 계약](../tasks/04_dashboard.md#차트-summary-수급-연결-2026-10-13). | [chart loader](../../src/invest_bot/dashboard/streamlit_state.py), [집계·caption](../../src/invest_bot/dashboard/streamlit_charts.py) | [기능 회귀](../../tests/test_dashboard_summary_flow.py), [메인 경계 검증](../../tests/test_g05a_boundary_qa.py), [화면 검증](../tasks/04_dashboard.md#차트-summary-수급-연결-2026-10-13) |
| K-HISTORY | 명시적 시작일·종료일의 가격·수급을 구간별로 보충하고 별도 history snapshot을 남기는 경로. 일반 수집 G08a의 기간 확보와 신규 상장 처리 완료를 뜻하지 않는다. | [보충 수집 job](../../src/invest_bot/jobs/backfill_history.py), [CLI](../../scripts/run_historical_collection.py) | [전용 회귀](../../tests/test_backfill_history.py), [검증 범위](../tasks/02_data_collection.md#보충-수집-검증-범위) |
| K-COMPARISON | 같은 평가기간과 초기자금에서 전략별 일별 평가금액을 가격 매수 후 보유와 비교한다. 이 리포트의 비용·배당0 가정을 슬라이딩 연구의 비용 시나리오와 구분한다. | [비교 job](../../src/invest_bot/jobs/backtest_comparison.py), [HTML 생성기](../../scripts/render_backtest_comparison.py) | [비교 회귀](../../tests/test_backtest_comparison.py), [검증 범위](../tasks/05_strategy_backtest.md#비교-리포트-검증-범위) |
| K-ROLLING | 고정된 로컬 CSV에서 슬라이딩 창마다 현금으로 다시 시작해 단일 전략·신호 혼합·독립 자금배분을 비교하는 연구. 겹친 창 분포와 비중복 테스트 블록의 시간순 선택을 구분하며, 대시보드 조합 저장·재로드 G08c와는 별도다. | [연구 job](../../src/invest_bot/jobs/rolling_backtest_research.py), [HTML 생성기](../../scripts/render_rolling_backtest_report.py) | [연구 회귀](../../tests/test_rolling_backtest_research.py), [HTML 회귀](../../tests/test_rolling_report_renderer.py), [검증 범위](../tasks/05_strategy_backtest.md#슬라이딩-연구-검증-범위) |

## 관계

| 출발 | 관계 | 도착 | 의미 |
| --- | --- | --- | --- |
| K-COLLECTION | produces | K-SNAPSHOT | 수집 결과를 snapshot으로 저장 |
| K-COLLECTION | consumes | K-SYMBOL | 종목을 식별하고 기존 메타데이터 보존 |
| K-ASOF | consumes | K-SNAPSHOT | 지표·신호·수급의 실제 관측일 선택 |
| K-EQUITY | consumes | K-STRATEGY | 전략 신호를 체결·평가금액으로 해석 |
| K-DASHBOARD | consumes | K-ASOF | 리포트 기준일과 해석을 표시 |
| K-DASHBOARD | consumes | K-EQUITY | 백테스트 결과를 표시 |
| K-CHART-FLOW | consumes | K-SNAPSHOT | 같은 조회 요청의 수급 원본을 재사용 |
| K-DASHBOARD | consumes | K-CHART-FLOW | 가격 차트에 실제 관측일 수급과 누락 사유를 표시 |
| K-HISTORY | consumes | K-SYMBOL | 요청 종목의 명시적 과거 구간을 수집 |
| K-HISTORY | produces | K-SNAPSHOT | 기존 짧은 snapshot을 보존하고 별도 history snapshot 생성 |
| K-COMPARISON | consumes | K-STRATEGY | 같은 입력·기간으로 기본 전략을 비교 |
| K-COMPARISON | consumes | K-EQUITY | 전략과 가격 매수 후 보유의 일별 성과·MDD를 비교 |
| K-ROLLING | consumes | K-STRATEGY | 신호 혼합과 독립 자금배분의 고정 후보를 구성 |
| K-ROLLING | consumes | K-EQUITY | 창별 비용 반영 곡선과 훈련/테스트 성과를 비교 |

각 개념 행의 구현·검증 링크는 각각 `describes`, `verified-by` 관계를 제공한다. 문서의 ID는 [등록부](catalog.md)에서 찾는다.

## 저장 경계와 알려진 문서 차이

- 정규화 fact 저장은 `enable_db_write`로 제어된다. snapshot의 기본 저장과 fact 테이블이 항상 함께 갱신된다고 가정하지 않는다.
- 일반 수집도 미등록 종목의 placeholder를 만들 수 있다. 이미 있는 실제 종목명과 KOSPI/KOSDAQ을 placeholder로 덮어쓰지 않는다. 예전 DB 문서의 “symbols는 마스터만 변경”은 현재 동작 전체를 설명하지 못한다.
- `stock_info_snapshots`는 제거 후보라는 설계안이 있지만, 물리적으로 제거됐다는 뜻은 아니다.
- `report_favorite_symbols`는 [등록된 마이그레이션](../../migrations/versions/20260703_000003_add_report_favorite_symbols.py)에 존재한다. 예전 ERD의 테이블 목록에는 빠져 있다.
- 이 차이 때문에 DB schema·ERD·repository 문서는 등록부에서 `review-required`로 표시한다. 실제 컬럼과 계약은 [모델](../../src/invest_bot/db/models.py), [계약](../../src/invest_bot/db/contracts.py), 마이그레이션을 함께 확인한다. 이번 작업에서 DB 정책이나 제품 코드를 변경하지 않는다.

## 검증 결과를 읽는 법

`379 passed`는 [퀀트 통합 보고](../operations/session_reports/2026-09-13_quant.md)에 기록된 해당 시점의 기본 suite 결과다. PostgreSQL 1건은 기본 suite에서 제외됐다. 오늘의 모든 동작이나 대기 중인 대시보드 변경이 검증됐다는 뜻은 아니다.
