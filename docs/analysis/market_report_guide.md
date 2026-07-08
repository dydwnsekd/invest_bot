# Market Report Guide

## 목적

이 문서는 `현재 장 상황 요약 리포트`에 어떤 항목이 들어가는지, 각 값이 무엇을 뜻하는지 정리한 가이드입니다.

현재 리포트는 종목 1개 기준 최신 상태를 한 줄로 정리하는 형태입니다.

## Discord 전달(2026-07-06 추가)

시장 리포트는 생성/저장 후 선택적으로 Discord에 전송할 수 있습니다.

- 1차 범위는 **배치 실행 / 전체 파이프라인** 경로만 포함합니다.
- 수동 단건 CLI 기본 경로는 Discord를 보내지 않습니다.
- Discord payload는 리포트 CSV row를 그대로 source of truth로 사용합니다.
- 전송 형식은 rich embed가 아니라 plain-text `content` 1건입니다.
- 전송 결과는 아래 3가지 상태를 사용합니다.
  - `sent`: 전송 성공
  - `skipped`: 웹훅 미설정 등으로 의도적으로 미전송
  - `failed`: HTTP 오류 등 전송 실패
- `skipped` / `failed`여도 리포트 저장 자체는 성공으로 유지됩니다.

## 리포트 위치

기본 저장 경로:

- [market_reports](/C:/Users/user/PycharmProjects/invest_bot/data/processed/domestic_stock/market_reports)

## 리포트에 포함되는 주요 항목

| 항목 | 의미 | 예시 |
|---|---|---|
| `symbol` | 종목 코드 | `005930` |
| `symbol_name` | 종목명 | `삼성전자` |
| `date` | 리포트 기준 날짜 | `2026-05-14` |
| `close` | 종가 | `72000` |
| `ma_5` | 5일 이동평균 | `71500` |
| `ma_20` | 20일 이동평균 | `70200` |
| `ma_60` | 60일 이동평균 | `68900` |
| `rsi_14` | RSI 14 값 | `58.4` |
| `volume` | 거래량 | `1523400` |
| `volume_ma_5` | 5일 평균 거래량 | `1230000` |
| `golden_cross_signal` | 골든크로스 기준 신호 | `buy` |
| `golden_cross_reason` | 골든크로스 판단 이유 | `ma_5 crossed above ma_20.` |
| `rsi_strategy_signal` | RSI 전략의 직접 판단 | `hold` |
| `rsi_strategy_reason` | RSI 전략 판단 이유 | `rsi_14 is 58.00, between buy threshold 30.00 and sell threshold 70.00.` |
| `trend_filter_signal` | 추세 필터 전략의 직접 판단 | `buy` |
| `trend_filter_reason` | 추세 필터 전략 판단 이유 | `close is 72000.00, above ma_60 68900.00 and above prev_close 71500.00.` |
| `mean_reversion_signal` | 평균회귀 전략의 직접 판단 | `hold` |
| `mean_reversion_reason` | 평균회귀 전략 판단 이유 | `close is 72000.00, at 1.0256 of ma_20 70200.00, inside the mean-reversion band.` |
| `trend_state` | 추세 상태 | `bullish` |
| `rsi_state` | RSI 해석 상태 | `strong` |
| `volume_state` | 거래량 해석 상태 | `active` |
| `investor_flow` | 투자자 수급 해석 상태 | `supportive` |
| `foreign_net` | 외국인 순매수 수량 | `120` |
| `institutional_net` | 기관 순매수 수량 | `80` |
| `personal_net` | 개인 순매수 수량 | `-200` |
| `summary` | 한 줄 요약 문장 | `Trend is bullish, golden cross signal is buy...` |
| `final_opinion` | 최종 판단 | `buy` |

## 상태값 설명

### 1. golden_cross_signal

골든크로스 전략이 내린 직접 신호입니다.

| 값 | 의미 |
|---|---|
| `buy` | 5일선이 20일선을 아래에서 위로 돌파한 매수 신호 |
| `sell` | 5일선이 20일선을 위에서 아래로 이탈한 매도 신호 |
| `hold` | 뚜렷한 교차가 없어 관망하는 상태 |

### 2. rsi_strategy_signal / rsi_strategy_reason

RSI 전략이 `rsi_14` 기준으로 직접 내린 판단과 이유입니다.

| 값 | 의미 |
|---|---|
| `buy` | RSI가 과매도 구간이라 반등 관점의 매수 신호 |
| `sell` | RSI가 과열 구간이라 차익 실현/매도 관점 |
| `hold` | 중간 구간이거나 필요한 값이 부족해 관망 |

이유(`rsi_strategy_reason`)에는 현재 RSI 값과 기준 임계값 비교가 들어갑니다.

### 3. trend_filter_signal / trend_filter_reason

추세 필터 전략이 `close`, `ma_60`, `prev_close`를 비교해 내린 직접 판단입니다.

| 값 | 의미 |
|---|---|
| `buy` | 종가가 장기 기준선과 직전 종가보다 모두 위 |
| `sell` | 종가가 장기 기준선과 직전 종가보다 모두 아래 |
| `hold` | 방향이 섞였거나 필요한 값이 부족함 |

이유(`trend_filter_reason`)에는 `close`, `ma_60`, `prev_close` 비교 결과가 들어갑니다.

### 4. mean_reversion_signal / mean_reversion_reason

평균회귀 전략이 `close`와 `ma_20` 비율을 비교해 내린 직접 판단입니다.

| 값 | 의미 |
|---|---|
| `buy` | 현재 가격이 기준선보다 충분히 낮아 평균회귀 매수 구간 |
| `sell` | 현재 가격이 기준선보다 충분히 높아 평균회귀 매도 구간 |
| `hold` | 밴드 안이거나 필요한 값이 부족함 |

이유(`mean_reversion_reason`)에는 `close`, `ma_20`, 비율 또는 부족한 indicator가 들어갑니다.

### 5. trend_state

현재 가격과 이동평균 관계를 기준으로 해석한 추세 상태입니다.

| 값 | 의미 |
|---|---|
| `bullish` | 가격과 단기선이 장기선 위에 있어 상승 쪽 해석이 쉬운 상태 |
| `bearish` | 가격과 단기선이 장기선 아래에 있어 약세로 해석하기 쉬운 상태 |
| `neutral` | 상승/하락 어느 쪽도 강하게 보기 어려운 상태 |
| `unknown` | 필요한 값이 부족해 판단하지 못한 상태 |

### 6. rsi_state

RSI를 해석한 결과입니다.

| 값 | 의미 |
|---|---|
| `overbought` | 과열 가능성이 있는 높은 RSI 구간 |
| `oversold` | 과매도 가능성이 있는 낮은 RSI 구간 |
| `strong` | 비교적 강한 흐름 |
| `weak` | 비교적 약한 흐름 |
| `neutral` | 중립 구간 |
| `unknown` | RSI 값이 없어 판단 불가 |

### 7. volume_state

현재 거래량과 5일 평균 거래량을 비교한 상태입니다.

| 값 | 의미 |
|---|---|
| `active` | 평소보다 거래량이 활발한 상태 |
| `normal` | 평소와 비슷한 거래량 상태 |
| `quiet` | 평소보다 거래량이 적은 상태 |
| `unknown` | 거래량 비교에 필요한 값이 부족한 상태 |

### 8. investor_flow

외국인, 기관, 개인 순매수 상태를 요약한 값입니다.

| 값 | 의미 |
|---|---|
| `supportive` | 외국인과 기관이 함께 순매수라 비교적 우호적 |
| `weak` | 외국인과 기관이 함께 순매도라 약한 흐름으로 볼 수 있음 |
| `mixed` | 수급 방향이 섞여 있어 해석이 애매함 |
| `unknown` | 수급 데이터가 없거나 비어 있음 |

### 9. final_opinion

리포트가 여러 항목을 종합해 내린 최종 의견입니다.

| 값 | 의미 |
|---|---|
| `buy` | 비교적 매수 쪽으로 해석하기 쉬운 상태 |
| `sell` | 비교적 매도 또는 회피 쪽으로 해석하기 쉬운 상태 |
| `hold` | 아직 관망이 자연스러운 상태 |
| `watch` | 당장 매수는 아니지만 계속 지켜볼 만한 상태 |

> `final_opinion`은 여전히 상위 종합 의견입니다.  
> `rsi_strategy_signal`, `trend_filter_signal`, `mean_reversion_signal`은 각 전략의 직접 판단이며 이를 대체하지 않습니다.

## 어떻게 해석하면 좋을까

### 강한 매수 쪽 해석

아래 조합이면 비교적 강한 상태로 볼 수 있습니다.

- `trend_state = bullish`
- `golden_cross_signal = buy`
- `rsi_state`가 `overbought`가 아님
- `investor_flow = supportive`

### 관망 쪽 해석

아래 조합이면 방향이 모호할 수 있습니다.

- `trend_state = neutral`
- `golden_cross_signal = hold`
- `rsi_state = neutral`
- `volume_state = normal`

### 약한 상태 해석

아래 조합이면 비교적 보수적으로 볼 수 있습니다.

- `trend_state = bearish`
- `golden_cross_signal = sell`
- `investor_flow = weak`

## 한 줄 요약 summary

`summary`는 현재 리포트의 핵심 상태를 문장으로 묶은 값입니다.

예:

```text
Trend is bullish, golden cross signal is buy, RSI state is strong, volume is active, and investor flow is supportive.
```

이 문장은 사람이 빠르게 전체 상태를 읽도록 도와주는 요약입니다.

## Discord 메시지에 포함되는 항목

Discord plain-text 메시지는 아래 그룹을 순서대로 묶어 보냅니다.

1. 종목 / 기준일
2. `final_opinion`
3. `summary`
4. 전략 신호
   - `golden_cross_signal`
   - `rsi_strategy_signal`
   - `trend_filter_signal`
   - `mean_reversion_signal`
5. 전략 이유
   - `golden_cross_reason`
   - `rsi_strategy_reason`
   - `trend_filter_reason`
   - `mean_reversion_reason`
6. 핵심 지표
   - `close`
   - `ma_5`
   - `ma_20`
   - `ma_60`
   - `rsi_14`
   - `volume`
   - `volume_ma_5`
7. 투자자 수급
   - `investor_flow`
   - `foreign_net`
   - `institutional_net`
   - `personal_net`

예시 warning 해석:

```text
시장 리포트 생성 완료(3건). Discord 전송 경고: 삼성전자 skipped(웹훅 미설정)
```

## 예시 리포트

```json
{
  "symbol": "005930",
  "symbol_name": "삼성전자",
  "date": "2026-05-14",
  "close": 72000,
  "ma_5": 71500,
  "ma_20": 70200,
  "ma_60": 68900,
  "rsi_14": 58.4,
  "volume": 1523400,
  "volume_ma_5": 1230000,
  "golden_cross_signal": "buy",
  "golden_cross_reason": "ma_5 crossed above ma_20.",
  "rsi_strategy_signal": "hold",
  "rsi_strategy_reason": "rsi_14 is 58.40, between buy threshold 30.00 and sell threshold 70.00.",
  "trend_filter_signal": "buy",
  "trend_filter_reason": "close is 72000.00, above ma_60 68900.00 and above prev_close 71500.00.",
  "mean_reversion_signal": "hold",
  "mean_reversion_reason": "close is 72000.00, at 1.0256 of ma_20 70200.00, inside the mean-reversion band.",
  "trend_state": "bullish",
  "rsi_state": "strong",
  "volume_state": "active",
  "investor_flow": "supportive",
  "foreign_net": 120,
  "institutional_net": 80,
  "personal_net": -200,
  "summary": "Trend is bullish, golden cross signal is buy, RSI state is strong, volume is active, and investor flow is supportive.",
  "final_opinion": "buy"
}
```

필수 지표가 부족한 경우 새 전략 필드는 공통적으로 다음 형식을 사용합니다.

- signal: `hold`
- reason: `Missing indicators: ...`

## 관련 파일

- [generate_market_report.py](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/generate_market_report.py)
- [run_market_report.py](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/run_market_report.py)
- [discord_report_notifier.py](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/jobs/discord_report_notifier.py)
- [indicator_guide.md](/C:/Users/user/PycharmProjects/invest_bot/docs/analysis/indicator_guide.md)
