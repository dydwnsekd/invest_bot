# Task 05. Strategy And Backtest

## 목표

수집 및 분석 데이터를 바탕으로 전략 신호를 만들고, 그 신호를 과거 데이터로 검증할 수 있는 구조를 만든다.

## 완료된 항목

- [x] 전략 공통 인터페이스 구현
- [x] 샘플 전략 구현
- [x] 골든크로스 전략 구현
- [x] RSI 전략 구현
- [x] Trend Filter 전략 구현
- [x] Mean Reversion 전략 구현
- [x] Disparity 전략 구현
- [x] Momentum 전략 구현
- [x] Investor-flow custom 전략 구현
- [x] 골든크로스 신호 생성 잡 구현
- [x] 백테스트 전략 adapter/registry 7종 구현
- [x] 전략별 readiness gate 구현
- [x] 전용 `백테스트` 대시보드 탭 연동
- [x] 비교표/누적 수익률 차트/거래 로그 결과 표시
- [x] symbol-first 백테스트 persistence identity 정리

## 현재 백테스트 workflow

- 준비 확인
  - 대시보드 `백테스트` 탭에서 종목/전략 조합별 readiness를 먼저 확인
  - 준비 상태 panel이 미준비 전략을 차단 사유와 함께 표시
- 준비 실행
  - 버튼을 눌렀을 때만 `데이터 수집 -> 지표 계산 -> 골든크로스 신호 생성`을 수행
  - 자동 background 실행은 하지 않음
- 백테스트 실행
  - 준비 완료 조합만 실행
  - 결과는 현재 세션 기준으로 `백테스트` 탭에 유지
- 결과 확인
  - 전략 요약 카드
  - 전략 비교표
  - 거래 순서 누적 수익률 차트
  - 일별 평가금액 곡선
  - 거래 로그
  - 저장 이력 재불러오기

## 현재 포함 전략

- `golden-cross`
- `rsi`
- `trend-filter`
- `mean-reversion`
- `disparity`
- `momentum`
- `investor-flow-custom`

## 현재 체결/청산 규칙

- [x] `buy` 신호 발생 시 다음 거래일 종가 진입
- [x] `sell` 신호 발생 시 다음 거래일 종가 청산
- [x] 종료 신호 없이 포지션이 남으면 마지막 거래일 종가로 강제 종료

## 일별 입력의 날짜 유일성 (2026-10-11)

[G03](../operations/improvements/quant.md#g03)의 날짜 유일성 차단을 원본에 통합했고 독립 QA와 원본 테스트를 통과했습니다. 사용자 요청으로 소스·회귀·검증 문서를 이번 main 커밋에 포함합니다. 운영 배포는 별도입니다.

- 한 종목의 가격·지표·정규화된 수급·전략 신호 입력에서 같은 유효 달력 날짜가 반복되면 계산 전에 차단합니다. 같은 값의 중복도 허용하지 않습니다.
- 날짜 문자열·Timestamp가 같은 날을 가리키거나 같은 날의 시각만 다르면 중복입니다. 검사에 UTC 변환을 적용하지 않고 각 입력 값의 달력 날짜를 비교합니다.
- 준비 확인은 데이터셋·중복 날짜·거래일당 한 행 요구를 차단 사유로 제공합니다. adapter의 저장 신호 전용 경로, 직접 runner, 직접 평가곡선, 각 전략 조합 입력도 같은 판정을 사용합니다.
- 가격이 무효여서 행을 제거할 경우에도 날짜 중복 검사를 먼저 합니다. 곡선·조합에서 `keep='last'`로 임의 선택하던 처리는 제거했습니다.
- 입력을 변경하거나 자동 보정하지 않습니다. 서로 다른 종목의 개별 실행과 서로 다른 전략별 한 행은 같은 날짜여도 허용됩니다. 여러 종목을 한 입력 프레임에 섞는 기능을 추가한 것은 아닙니다.
- `investor_daily`는 기존 백테스트 계약인 순매수 수량 컬럼과 `date`/`trade_date`를 갖춘 정규화된 입력에 적용합니다. 날짜 컬럼은 기존과 같이 `date`를 우선하며 원본 수급 상세 행을 이 검사로 변환하지 않습니다.
- 빈 입력·NaT·기존 정렬·다음 종가 체결·마지막 종가 청산·일별 MDD 계산은 유지합니다. 일반 날짜/가격 유효성 검사, 숫자형 YYYYMMDD 표준화, 입력 간 시간대 통일과 G04 저장 신호의 날짜·가격 비교는 G03 완료 범위에 포함하지 않습니다.

날짜 판정은 [공통 판정 코드](../../src/invest_bot/backtest/dates.py), 회귀는 [날짜 계약 테스트](../../tests/test_backtest_dates.py)와 [독립 경계 테스트](../../tests/test_g03_independent_qa.py), 대상 변경·실행 결과·제약은 [검증 기록](../operations/session_reports/2026-10-10_backtest_duplicate_dates.md)을 따릅니다.

## 저장 신호의 날짜·가격 정합성 (2026-10-12)

[G04](../operations/improvements/quant.md#g04)는 기존 퀀트→QA 순차 구현·독립 검증과 원본 통합을 완료했습니다. 2026-10-12 원본 main `a22254a` + 미커밋 G04에서 관련339개·기본780개를 통과했으며 커밋 전 검토 상태입니다. 아래는 현재 구현 계약이며 상태와 검증 증거는 역할 문서와 [검증 기록](../operations/session_reports/2026-10-12_saved_signal_alignment.md)을 따릅니다.

- 기본 5/20 골든크로스에서 `date/close/signal` 컬럼이 있는 저장 신호를 실제 선택하고 현재 지표도 제공하면, 두 입력의 전체 로컬 거래일 집합과 날짜별 종가를 대조합니다. 최신 거래일 누락·기간 밖 날짜·중간 날짜 누락/추가·같은 날짜의 종가 불일치는 명시적으로 차단합니다. 행 삭제·교집합 선택·자동 재계산으로 불일치를 숨기지 않습니다.
- 날짜 중복 검사는 대조보다 먼저 적용합니다. NaT·해석할 수 없는 날짜가 있으면 정합성을 확인할 수 없으므로 차단합니다. G03의 로컬 달력 판정을 공유하고 반복 인덱스 라벨과 무관하게 원래 행의 날짜·가격 대응을 유지합니다.
- 종가는 양수·유한 실수형 숫자 또는 숫자 문자열이어야 하며 숫자로 변환한 값이 정확히 같아야 합니다. 허용 오차·반올림을 적용하지 않습니다. 무효값끼리의 일치, bool·complex·날짜 객체 가격은 허용하지 않습니다. 이 유효성 계약은 현재 지표와 대조하는 저장 신호 경로에 적용합니다.
- 날짜 대조를 통과했는데 기존 정규화에서 혼합 문자열·Timestamp·offset이 NaT·오류·object 시간대가 되면 검증된 로컬 거래일의 자정으로 정규화합니다. UTC로 날짜를 이동하거나 신호·종가 행을 빠뜨리지 않습니다. 기존 정상 날짜 처리와 지표 없는 단독 경로의 소비자 처리는 유지합니다.
- 사용자 지정 MA 설정은 현재 지표에서 신호를 계산합니다. 사용하지 않는 저장 신호의 날짜·가격·중복·컬럼 오류가 이 경로를 차단하지 않습니다. adapter에서 저장 신호가 없거나 필수 컬럼이 없어 선택하지 않을 때도 기존 지표 계산을 유지합니다.
- 생성기/CLI는 명시한 지표 파일 또는 해당 종목의 최신 지표를 실제로 읽어 같은 검사를 수행하고, 사용한 지표 파일명을 출처에 기록합니다. 명시/선택한 지표 파일의 누락·빈 값·컬럼 오류와 선언한 신호 파일의 필수 컬럼 오류는 저장 전에 차단합니다. 지표가 아예 없고 명시 파일도 없는 기존 저장 신호 단독·빈/zero-byte 신호 입력은 유지하며 지표 출처는 `None`입니다. 이 경우 현재 지표와의 정합성을 검증한 것은 아닙니다.
- 대시보드 준비표는 지표·수급 준비 조건을 판정하며 저장 신호 정합성은 실제 실행 경계에서 검사합니다. 실패하면 이전 결과 bundle을 지우고 차단 사유를 표시하며, `준비 실행`으로 신호를 다시 생성하도록 안내합니다. 저장 신호 출처는 실제 adapter 선택 조건과 일치할 때만 기록합니다.

직접 runner에 주는 수동 프레임의 현재 지표 대조, 신호 계산 자체의 정확성·미래 정보 누출, 수급/raw 가격 파일 검증, 숫자 YYYYMMDD 변환과 소비자 전반 시간대 통일은 별도 범위입니다. 구현은 [adapter](../../src/invest_bot/backtest/adapters.py)·[공통 날짜 판정](../../src/invest_bot/backtest/dates.py)·[생성기](../../src/invest_bot/jobs/generate_backtest.py), 회귀는 [저장 신호 계약](../../tests/test_backtest_saved_signals.py)·[대시보드 실행](../../tests/test_streamlit_backtest.py)에서 확인합니다.

## 결과 정확성 개선 (2026-09-15)

- 요약의 `max_drawdown_pct`, `final_equity`, `total_return_pct`를 일별 mark-to-market 곡선에서 계산합니다.
- 초기자산을 최초 peak로 포함하며 보유 중 `100 → 50 → 100` 사례도 최대 낙폭 50%로 보고합니다.
- 체결·강제 청산 규칙과 거래비용 미반영 가정은 유지합니다.
- 시장 리포트는 지표·신호·수급의 공통 기준일 이하 입력만 사용합니다. 상세 날짜·누락 처리 계약은 [리포트 가이드](../analysis/market_report_guide.md)를 따릅니다.

## 현재 persistence 규칙

- [x] 거래 로그와 요약 결과에 `run_group_id`, `run_id`, `symbol`, `strategy_id`, `strategy_name`, `output_type` 부여
- [x] output filename은 `symbol` 우선 규칙 사용
  - `<symbol>_<strategy_id>_<UTC timestamp>_backtest_trades.csv`
  - `<symbol>_<strategy_id>_<UTC timestamp>_backtest_summary.csv`
- [x] summary에는 provenance 필드 저장
  - `indicator_source_*`
  - `signal_source_*`
  - `investor_source_*`
  - `price_source_*`
  - `input_sources_json`
- [x] generic Data tab은 종목별 최신 artifact 1건만 보일 수 있으므로, in-session 비교 기준은 `백테스트` 탭 결과를 우선 사용

## 확장 완료 항목

- [x] 전략 조합 구조(AND / OR / 가중치)와 개별·조합 결과 비교
- [x] 일별 mark-to-market equity curve
- [x] 백테스트 artifact history / reload
- [x] 전략별 제한된 실험 설정 UX와 기본값 복원
- [x] 포트폴리오 / multi-symbol aggregation

## 남은 항목

- [ ] 고급 전략 파라미터 튜닝(자동 탐색·최적값 추천 등)은 별도 검증 기준을 정한 뒤 진행

## 이번 범위의 비목표

- 실거래 / 주문 / 리스크 관리 추가
- 새 DB schema 추가
- 새 dependency 추가

## 관련 파일

- [`base.py`](../../src/invest_bot/strategy/base.py)
- [`golden_cross.py`](../../src/invest_bot/strategy/golden_cross.py)
- [`strategy_registry.py`](../../src/invest_bot/backtest/strategy_registry.py)
- [`adapters.py`](../../src/invest_bot/backtest/adapters.py)
- [`persistence.py`](../../src/invest_bot/backtest/persistence.py)
- [`generate_golden_cross_signals.py`](../../src/invest_bot/jobs/generate_golden_cross_signals.py)
- [`generate_backtest.py`](../../src/invest_bot/jobs/generate_backtest.py)
- [`run_backtest.py`](../../src/invest_bot/jobs/run_backtest.py)
- [`run_backtest.py`](../../scripts/run_backtest.py)
- [`streamlit_backtest.py`](../../src/invest_bot/dashboard/streamlit_backtest.py)
