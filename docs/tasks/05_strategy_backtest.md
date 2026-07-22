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
  - 거래 로그

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

## 남은 항목

- [ ] 전략 조합 구조 설계
- [ ] 일별 mark-to-market equity curve
- [ ] 백테스트 artifact history / reload
- [ ] 전략 파라미터 튜닝
- [ ] 포트폴리오 / multi-symbol aggregation

## 이번 범위의 비목표

- 실거래 / 주문 / 리스크 관리 추가
- 새 DB schema 추가
- 새 dependency 추가

## 관련 파일

- [`base.py`](src/invest_bot/strategy/base.py)
- [`golden_cross.py`](src/invest_bot/strategy/golden_cross.py)
- [`strategy_registry.py`](src/invest_bot/backtest/strategy_registry.py)
- [`adapters.py`](src/invest_bot/backtest/adapters.py)
- [`persistence.py`](src/invest_bot/backtest/persistence.py)
- [`generate_golden_cross_signals.py`](src/invest_bot/jobs/generate_golden_cross_signals.py)
- [`generate_backtest.py`](src/invest_bot/jobs/generate_backtest.py)
- [`run_backtest.py`](src/invest_bot/jobs/run_backtest.py)
- [`run_backtest.py`](scripts/run_backtest.py)
- [`streamlit_backtest.py`](src/invest_bot/dashboard/streamlit_backtest.py)
