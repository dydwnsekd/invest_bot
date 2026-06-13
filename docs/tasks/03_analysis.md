# Task 03. Analysis

## 목표

수집된 일봉 snapshot을 기반으로 전략 연구에 필요한 기본 지표를 계산하고 저장한다.

## 완료된 항목

- [x] raw 일봉 snapshot 로더 구현
- [x] 컬럼 기본 정규화 구현
- [x] 이동평균 `ma_5`, `ma_20`, `ma_60` 계산 구현
- [x] 거래량 이동평균 `volume_ma_5` 계산 구현
- [x] `rsi_14` 계산 구현
- [x] 분석 결과 DB snapshot 저장 구현
- [x] 분석 실행 스크립트 작성
- [x] 지표 해석 가이드 문서 작성

## 남은 항목

- [ ] 컬럼명 표준 스키마 확정
- [ ] 추가 지표 확장
  - MACD
  - Bollinger Bands
  - ATR
- [ ] 수급 데이터와 지표 결합 분석
- [ ] 결측치/이상치 처리 정책 정리

## 데이터 구조

기본 저장 대상은 DB의 `dataset_frames`이며, 아래 경로는 파일 fallback 또는 호환 export 경로다.

```text
data/processed/domestic_stock/
  daily_prices_indicators/
```

## 관련 파일

- [`analysis.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/market/analysis.py)
- [`analyze_daily_prices.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/analyze_daily_prices.py)
- [`run_daily_analysis.py`](/C:/Users/user/PycharmProjects/invest_bot/scripts/run_daily_analysis.py)
- [`indicator_guide.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/analysis/indicator_guide.md)
