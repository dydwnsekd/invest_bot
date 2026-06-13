# Task 05. Strategy And Backtest

## 목표

수집 및 분석 데이터를 바탕으로 전략 신호를 만들고, 그 신호를 과거 데이터로 검증할 수 있는 구조를 만든다.

## 완료된 항목

- [x] 전략 공통 인터페이스 구현
- [x] 샘플 전략 구현
- [x] 골든크로스 전략 구현
- [x] 골든크로스 신호 생성 잡 구현
- [x] 골든크로스 백테스트 초안 구현

## 현재 백테스트 초안 규칙

- [x] `buy` 신호 발생 시 다음 거래일 종가 진입
- [x] `sell` 신호 발생 시 다음 거래일 종가 청산
- [x] 종료 신호 없이 포지션이 남으면 마지막 거래일 종가로 강제 종료
- [x] 거래 로그 DB snapshot 저장
- [x] 요약 리포트 DB snapshot 저장

## 남은 항목

- [ ] RSI 기반 보조 전략 구현
- [ ] 전략 조합 구조 설계
- [ ] 성능 지표 확장
  - MDD
  - 승률
  - 평균 수익률
  - 손익비
- [ ] 백테스트 결과 비교 리포트 정리
- [ ] Streamlit 대시보드에 백테스트 결과 표시

## 관련 파일

- [`base.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/strategy/base.py)
- [`golden_cross.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/strategy/golden_cross.py)
- [`generate_golden_cross_signals.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/generate_golden_cross_signals.py)
- [`generate_backtest.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/generate_backtest.py)
- [`run_backtest.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/run_backtest.py)
- [`run_backtest.py`](/C:/Users/user/PycharmProjects/invest_bot/scripts/run_backtest.py)
