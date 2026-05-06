# invest_bot Task Summary

프로젝트 전체 작업 현황을 요약한 문서입니다.

## 1. 설정 및 개발 환경

- [x] Python 3.13 기준 프로젝트 구조 정리
- [x] `requirements.txt`, `requirements-dev.txt` 분리
- [x] `.venv` 생성 및 의존성 설치 가능 상태 확인
- [x] `pytest` 실행 가능 상태 확인
- [x] 파일 기반 설정 예시 추가
- [x] 비밀 정보 파일 `.gitignore` 처리
- [ ] 개발/운영 설정 분리 정책 고도화
- [ ] 로그 설정 및 로깅 포맷 정리

관련 문서:
- [01_environment.md](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/01_environment.md)

## 2. 국내주식 데이터 수집

- [x] KIS REST 클라이언트 기본 구현
- [x] 일봉 데이터 수집 구현
- [x] 종목 기본정보 수집 구현
- [x] 투자자 수급 일별 데이터 수집 구현
- [x] 수집 결과 CSV 저장 구현
- [ ] 다중 종목 배치 수집
- [ ] 분봉 데이터 수집
- [ ] 현재가/호가 수집
- [ ] 뉴스/공매도/프로그램 매매 수집

관련 문서:
- [02_data_collection.md](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/02_data_collection.md)

## 3. 데이터 분석 및 지표

- [x] 저장된 일봉 CSV 로더 구현
- [x] 이동평균 계산 구현
- [x] RSI 계산 구현
- [x] 분석 결과 CSV 저장 구현
- [ ] 컬럼 표준화 정책 문서화
- [ ] 추가 지표 확장
- [ ] 수급/가격 결합 분석

관련 문서:
- [03_analysis.md](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/03_analysis.md)

## 4. 대시보드 및 가시화

- [x] raw/processed CSV 미리보기용 로컬 대시보드 구현
- [x] 로컬 브라우저 접속 가능 구조 구현
- [ ] 종목 선택 기능
- [ ] 최신 수집 시각 표시
- [ ] 지표 기반 신호 표시
- [ ] 간단한 차트 시각화

관련 문서:
- [04_dashboard.md](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/04_dashboard.md)

## 5. 전략 및 백테스트

- [x] 전략 인터페이스 기본 골격 구현
- [x] 샘플 전략 구현
- [ ] CSV 기반 신호 생성 전략 구현
- [ ] 지표 기반 `buy/sell/hold` 판단 구현
- [ ] 백테스트 엔진 초안 구현
- [ ] 수익률/MDD/승률 계산
- [ ] 전략 비교 리포트

관련 문서:
- [05_strategy_backtest.md](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/05_strategy_backtest.md)

## 6. 주문 및 리스크 관리

- [ ] 모의투자 주문 래퍼 구현
- [ ] 실거래 주문 래퍼 구현
- [ ] 주문 전 체크리스트 구현
- [ ] 손절/익절 규칙 구현
- [ ] 중복 주문 방지
- [ ] 장 시간 필터링

관련 문서:
- [06_trading_risk.md](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/06_trading_risk.md)

## 7. 문서 및 운영

- [x] `README.md` 기본 구조 정리
- [x] `agent.md` 프로젝트 가이드 정리
- [x] 프로젝트 전용 skill 초안 작성
- [ ] task 문서 주기적 갱신 규칙 확정
- [ ] 운영 절차 문서 작성
- [ ] 장애 대응/재실행 가이드 작성

관련 문서:
- [07_operations_docs.md](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/07_operations_docs.md)
