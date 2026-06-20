# Deferred And Follow-up Strategy Notes

## 목적

이 문서는 phase 1 이후 후속 전략 작업의 상태를 기록한다.

- 2026-06-18 기준 구현 완료:
  - `DisparityStrategy`
  - `MomentumStrategy`
  - `InvestorFlowCustomStrategy`
- 아직 후속 과제로 남는 항목:
  - investor-flow signal job 연결
  - 전략 실행/백테스트 일반화
  - investor-flow 확장 필드(`foreign_net_3d`, `institutional_net_3d`, streak 류)

## 1. Disparity

### 현재 상태

- 전략 클래스 구현 완료
- snapshot-only `evaluate(...)` 계약 유지
- 핵심 입력:
  - `close`
  - `ma_20`
- 핵심 파생값:
  - `disparity_pct = (close / ma_20) * 100`

### 남은 후속 작업

- Mean Reversion과 비교한 실전 성능 확인
- 대시보드/리포트에서 `disparity_pct` 표시 여부 결정
- 백테스트 결과 비교 리포트에 포함

## 2. Momentum

### 현재 상태

- 전략 클래스 구현 완료
- `momentum_20` producer를 indicator pipeline에 추가 완료
- `momentum_20` 의미는 **20거래일 percentage return**으로 고정

### 남은 후속 작업

- momentum 신호를 실제 signal generation/backtest 흐름에 연결
- threshold (`+10 / -10`) 조정 필요성 검토
- neutral band 유지 여부를 실험 기반으로 재검토

## 3. Investor-flow custom

### 현재 상태

- 단일 하우스 룰 전략 클래스 구현 완료
- 현재 rule:
  - 외국인 순매수 > 0
  - 기관 순매수 > 0
  - `close > ma_20` → buy
  - 반대 방향이면 sell
- runtime assembly는 아직 deferred

### 명시적 후속 경계

다음 구현 단계에서 아래 로컬 helper를 signal job 안에 추가한다.

- future job file:
  - `src/invest_bot/jobs/generate_investor_flow_signals.py`
- helper responsibility:
  - indicator row 로드
  - 같은 symbol/date의 `investor_daily` row 로드
  - 하나의 `market_snapshot` dict로 조립

### 남은 후속 작업

- investor-flow signal job 연결
- rolling flow field 도입 검토
  - `foreign_net_3d`
  - `institutional_net_3d`
  - `foreign_streak`
  - `institutional_streak`
- 단일 하우스 룰을 유지할지, 구성형 전략으로 확장할지 결정
