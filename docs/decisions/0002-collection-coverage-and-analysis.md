# 0002 — 일봉 요청 범위와 분석 준비 분리

> OKF 종류: `decision` · 상태: `active` · 결정일: 2026-11-02 · 담당: 데이터·통합

## 문제

일반 일봉 수집은 요청 기간을 한 번 조회하고 최소60행만 검사했다. API의 호출당100행 제한으로 긴 요청이 짧아질 수 있으며, 달력365일과 거래일365행은 같은 조건이 아니다. 요청 경계가 주말/휴일이라는 이유로 유효 수집을 실패시키는 판정도 피해야 한다.

## 결정

- 일반 일봉은 inclusive100달력일 이하의 겹치지 않는 구간을 모두 요청하고 검증한다. 한 일봉당 관측일 하나라는 API 계약 안에서 요청 cap에 의한 잘림을 피하고 중복 재조회를 하지 않는다. 날짜·OHLC·수치·중복 검증은 기존 보충 수집과 공유한다.
- `price_coverage.status`의 완료는 bounded API 요청·응답 처리 완료다. 전체 거래일 존재는 별도 `trading_days_verified`, 실제 경계의 설명·불확실성은 `range_reason`으로 남긴다. 신뢰 캘린더나 일치하는 상장 근거가 없으면 휴장/신규상장을 추정하지 않는다.
- 완료된 비어 있지 않은 짧은 자료는 저장하고, 분석 준비는 별도로 판정한다. 현재 일반 분석 연결은 최소60개 유효 일봉을 요구하며 관심종목 추가 갱신은 기존 자료와 합친 누적 이력으로 판단한다. 명시적 미준비 종목은 지표·신호·리포트로 넘기지 않는다.
- 증분 수집의 시작일·합친 snapshot 경계·분석용 unique 날짜는 기존 G01b scalar 달력 날짜 규칙을 재사용한다. 숫자 YYYYMMDD를 epoch로 읽어 요청 상한까지 소모하지 않도록 한다. 저장 자료의 값과 DB metadata를 다시 쓰지 않는다.
- 페이지 실패·잘못된 값·미충족/모순은 부분 가격을 완료로 저장하지 않는다. 저장 단계의 기존 부분 성공 보고와 앞선 성공 종목은 보존한다. 새 분석 필드는 True/False를 엄격히 해석하고 None/필드 부재에 한해 문서화한 legacy 호환을 둔다.

## 근거와 제약

[공식 KIS 일봉 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py)의100행 cap과 요청 파라미터, [종목정보 매핑](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/search_stock_info/chk_search_stock_info.py)의 상장일 필드를 확인했다. 1.1초 pacing/100구간 상한은 로컬 정책이며 모든 KIS 사용 환경의 rate-limit 보증이 아니다.

기본 거래일 캘린더를 새로 설치하지 않았다. API 구간 처리는 실제 휴장일·장중 확정·상장/정지 이력의 인증이 아니다. 별도 보충 CLI는 기존 요청/retry/pacing/수급 계약을 유지한다. 실제 API/토큰·운영 DB·브라우저·배포는 이 결정의 로컬 검증으로 확인되지 않는다.

## 구현과 검증

[기간 수집·검증](../../src/invest_bot/market/price_history.py), [수집/저장 facade](../../src/invest_bot/market/collector.py), [소비자 연결](../../src/invest_bot/dashboard/streamlit_actions.py), [기능 회귀](../../tests/test_collection_coverage.py), [소비자 회귀](../../tests/test_collection_coverage_consumers.py)를 따른다. 현재 상태·추가 결과 필드·검증 명령과 한계는 [일반 일봉 계약](../tasks/02_data_collection.md#일반-일봉-요청-범위-2026-11-02)에서 관리한다.
