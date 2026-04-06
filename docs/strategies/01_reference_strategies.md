# Reference Strategies

## 개요

`reference/open-trading-api/strategy_builder`에는 기본 전략 10개가 포함되어 있다.
현재 `invest_bot`에서는 이 전략들을 그대로 복사하기보다, 각 전략의 아이디어를 현재 수집/분석 구조에 맞게 다시 구현하는 방식이 적합하다.

## 전략 목록

### 1. 골든크로스

- 분류: 추세 추종
- 핵심 아이디어: 단기 이동평균이 장기 이동평균을 상향 돌파하면 매수, 하향 돌파하면 매도
- 필요한 데이터: 일봉 종가
- 필요한 지표: `ma_5`, `ma_20`
- 현재 구현 난이도: 낮음
- 비고: 가장 먼저 구현하기 좋은 전략

### 2. 모멘텀

- 분류: 추세 추종
- 핵심 아이디어: 최근 N일 수익률이 충분히 강하면 매수, 약하면 매도
- 필요한 데이터: 일봉 종가
- 필요한 지표: 기간 수익률
- 현재 구현 난이도: 낮음
- 비고: 추가 지표 없이도 구현 가능

### 3. 52주 신고가

- 분류: 돌파 매매
- 핵심 아이디어: 현재가가 52주 최고가를 돌파하면 매수
- 필요한 데이터:
  - 현재가 API 또는
  - 250거래일 이상 일봉 데이터
- 현재 구현 난이도: 중간
- 비고: 현재 데이터 범위가 충분하지 않을 수 있어 보류 추천

### 4. 연속 상승/하락

- 분류: 패턴
- 핵심 아이디어: N일 연속 상승이면 매수, N일 연속 하락이면 매도
- 필요한 데이터: 일봉 종가
- 현재 구현 난이도: 낮음
- 비고: 직관적이지만 신호가 단순해 필터 전략과 같이 쓰는 편이 좋음

### 5. 이격도

- 분류: 평균 회귀
- 핵심 아이디어: 가격이 이동평균보다 너무 낮으면 매수, 너무 높으면 매도
- 필요한 데이터: 일봉 종가
- 필요한 지표: 이동평균, 이격도
- 현재 구현 난이도: 낮음
- 비고: 임계값을 백분율로 설명하기 쉬움

### 6. 돌파 실패

- 분류: 실패 패턴 / 청산 보조
- 핵심 아이디어: 최근 고점을 돌파한 뒤 짧은 기간 안에 크게 밀리면 매도
- 필요한 데이터: 일봉 고가, 종가
- 현재 구현 난이도: 중간
- 비고: 단독 전략보다 손절 또는 청산 규칙에 가깝다

### 7. 강한 종가

- 분류: 모멘텀
- 핵심 아이디어: 종가가 당일 고가 근처에서 마감되면 매수
- 필요한 데이터: 일봉 고가, 저가, 종가
- 현재 구현 난이도: 낮음
- 비고: 장 마감 이후 신호 생성용으로 적합

### 8. 변동성 확장

- 분류: 변동성 돌파
- 핵심 아이디어: 최근 변동성이 낮은 상태에서 큰 상승이 나오면 매수
- 필요한 데이터: 일봉 시가, 고가, 저가, 종가
- 현재 구현 난이도: 중간
- 비고: 신호는 강하지만 과최적화 주의 필요

### 9. 평균 회귀

- 분류: 평균 회귀
- 핵심 아이디어: 가격이 단기 평균보다 너무 낮으면 매수, 너무 높으면 매도
- 필요한 데이터: 일봉 종가
- 필요한 지표: 이동평균
- 현재 구현 난이도: 낮음
- 비고: 초보자에게 설명하기 쉬운 전략

### 10. 추세 필터

- 분류: 추세 추종
- 핵심 아이디어: 종가가 장기 이동평균 위에 있고 전일 대비 상승이면 매수, 반대면 매도
- 필요한 데이터: 일봉 종가
- 필요한 지표: `ma_60`
- 현재 구현 난이도: 낮음
- 비고: 골든크로스보다 보수적인 방향의 기본 전략

## 우리 프로젝트에 맞는 전략 그룹

### 1차 구현 추천

- 골든크로스
- 추세 필터
- 평균 회귀
- 이격도
- 모멘텀

### 2차 구현 추천

- 연속 상승/하락
- 강한 종가
- 변동성 확장

### 3차 구현 추천

- 돌파 실패
- 52주 신고가
- 투자자 수급 기반 전략

## 투자자 수급 기반 확장 아이디어

reference 기본 전략 10개와 별개로, 현재 프로젝트는 투자자 수급 데이터를 이미 수집하고 있으므로 아래 같은 확장이 가능하다.

- 외국인 순매수 3일 연속 + 종가가 20일선 위면 매수 후보
- 기관 순매수 전환 + RSI 과매도 구간 탈출 시 매수 후보
- 개인 순매수 과열 + 종가가 5일선 아래 이탈 시 관망 또는 매도 후보

## 구현 시 권장 규칙

- 하나의 전략은 `buy/sell/hold`를 명확히 반환한다.
- 이유 문자열에 판단 근거를 함께 남긴다.
- 사용한 지표 값도 같이 저장해 대시보드와 백테스트에서 재사용한다.
- 초반에는 복합 전략보다 단일 전략을 먼저 검증한다.

## 참고 파일

- [strategy_01_golden_cross.py](/C:/Users/user/PycharmProjects/invest_bot/reference/open-trading-api/strategy_builder/strategy/strategy_01_golden_cross.py)
- [strategy_02_momentum.py](/C:/Users/user/PycharmProjects/invest_bot/reference/open-trading-api/strategy_builder/strategy/strategy_02_momentum.py)
- [strategy_03_week52_high.py](/C:/Users/user/PycharmProjects/invest_bot/reference/open-trading-api/strategy_builder/strategy/strategy_03_week52_high.py)
- [strategy_04_consecutive.py](/C:/Users/user/PycharmProjects/invest_bot/reference/open-trading-api/strategy_builder/strategy/strategy_04_consecutive.py)
- [strategy_05_disparity.py](/C:/Users/user/PycharmProjects/invest_bot/reference/open-trading-api/strategy_builder/strategy/strategy_05_disparity.py)
- [strategy_06_breakout_fail.py](/C:/Users/user/PycharmProjects/invest_bot/reference/open-trading-api/strategy_builder/strategy/strategy_06_breakout_fail.py)
- [strategy_07_strong_close.py](/C:/Users/user/PycharmProjects/invest_bot/reference/open-trading-api/strategy_builder/strategy/strategy_07_strong_close.py)
- [strategy_08_volatility.py](/C:/Users/user/PycharmProjects/invest_bot/reference/open-trading-api/strategy_builder/strategy/strategy_08_volatility.py)
- [strategy_09_mean_reversion.py](/C:/Users/user/PycharmProjects/invest_bot/reference/open-trading-api/strategy_builder/strategy/strategy_09_mean_reversion.py)
- [strategy_10_trend_filter.py](/C:/Users/user/PycharmProjects/invest_bot/reference/open-trading-api/strategy_builder/strategy/strategy_10_trend_filter.py)
