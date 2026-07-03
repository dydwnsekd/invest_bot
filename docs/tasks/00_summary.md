# invest_bot Task Summary

프로젝트 전체 작업 현황을 빠르게 확인하기 위한 요약 문서입니다.

## 최근 세션 업데이트 (2026-06-28)

- [x] `작업 실행` 탭을 여러 종목 기준 배치 실행 구조로 단순화
- [x] `한 종목` 섹션 제거
- [x] `리포트 해석` 탭 상단 metrics strip 제거
- [x] 전략 판단 텍스트에 상태별 green/red/black 색상 적용
- [x] `데이터 탐색` 탭을 종목 선택 기반 summary-first 흐름으로 재구성
- [x] HTML escaping 보강 및 회귀 테스트 추가
- [x] 관련 검증 완료 (`39 passed in 0.48s`)

## 1. 환경 및 설정

- [x] Python 3.13 기반 프로젝트 구조 정리
- [x] `requirements.txt`, `requirements-dev.txt` 분리
- [x] `.venv` 생성 및 패키지 설치 확인
- [x] `pytest` 실행 가능 상태 확인
- [x] 파일 기반 설정 예시 추가
- [x] 민감한 설정 파일 `.gitignore` 처리
- [ ] 개발/운영 설정 분리 고도화
- [ ] 로깅 정책 정리

관련 문서:
- [`01_environment.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/01_environment.md)

## 2. 국내주식 데이터 수집

- [x] KIS REST 클라이언트 기본 구현
- [x] 일봉 데이터 수집 구현
- [x] 종목 기본정보 수집 구현
- [x] 투자자 수급 일별 데이터 수집 구현
- [x] 수집 결과 DB snapshot 저장 구현
- [x] 다중 종목 배치 수집 구현
- [x] 정기 다중 종목 수집 스케줄링 초안 구현
- [ ] 분봉 데이터 수집
- [ ] 현재가/호가 수집
- [ ] 공매도/프로그램 매매/뉴스 수집

관련 문서:
- [`02_data_collection.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/02_data_collection.md)

## 3. 데이터 분석 및 지표

- [x] 저장된 일봉 snapshot 로더 구현
- [x] 이동평균 계산 구현
- [x] RSI 계산 구현
- [x] 모멘텀 지표(`momentum_20`) 계산 구현
- [x] 분석 결과 DB snapshot 저장 구현
- [x] 지표 가이드 문서 추가
- [ ] 추가 지표 확장
- [ ] 수급/가격 결합 분석

관련 문서:
- [`03_analysis.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/03_analysis.md)
- [`indicator_guide.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/analysis/indicator_guide.md)

## 4. 대시보드 및 시각화

- [x] HTML 기반 로컬 대시보드 구현
- [x] Streamlit 기반 대시보드 초안 구현
- [x] 데이터 수집/분석/신호/리포트 조회 구현
- [x] 리포트 해석 탭 단일 리포트 본문 흐름 구현
- [x] 시장 리포트 전략별 판단 요약 및 상태 색상 표시 구현
- [x] 리포트 즐겨찾기 DB 저장 및 관심종목 탭 구현
- [x] 대시보드에서 여러 종목 기준 배치 실행
- [x] 대시보드에서 데이터 수집 실행
- [x] 대시보드에서 지표 계산 실행
- [x] 대시보드에서 골든크로스 신호 생성 실행
- [x] 대시보드에서 시장 리포트 생성 실행
- [x] 대시보드에서 전체 파이프라인 실행
- [x] 정기 수집 상태와 실행 로그 표시
- [ ] 종목 비교 차트
- [ ] 백테스트 결과 시각화

관련 문서:
- [`04_dashboard.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/04_dashboard.md)

## 5. 전략 및 백테스트

- [x] 전략 인터페이스 기본 골격 구현
- [x] 샘플 전략 구현
- [x] 골든크로스 전략 구현
- [x] RSI 전략 구현
- [x] Trend Filter 전략 구현
- [x] Mean Reversion 전략 구현
- [x] Disparity 전략 구현
- [x] Investor-flow custom 전략 구현
- [x] Momentum 전략 구현
- [x] 골든크로스 신호 생성 구현
- [x] 골든크로스 백테스트 초안 구현
- [ ] 전략별 성능 비교
- [ ] 성능 지표 확장
- [ ] 백테스트 결과 대시보드 표시

관련 문서:
- [`05_strategy_backtest.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/05_strategy_backtest.md)

## 6. 주문 및 리스크 관리

- [ ] 모의투자 주문 래퍼 구현
- [ ] 실거래 주문 래퍼 구현
- [ ] 주문 전 체크리스트 구현
- [ ] 손절/익절 규칙 구현
- [ ] 중복 주문 방지
- [ ] 시간 필터링

관련 문서:
- [`06_trading_risk.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/06_trading_risk.md)

## 7. 문서 및 운영

- [x] `README.md` 정리
- [x] `agent.md` 프로젝트 가이드 정리
- [x] 프로젝트용 skill 초안 작성
- [x] 지표 가이드 문서 작성
- [x] 시장 리포트 가이드 문서 작성
- [x] 시장 리포트 전략별 판단 필드 문서화
- [x] DB 마이그레이션 준비 문서 작성 (`ERD`, `docker-compose`, repository interfaces`)
- [ ] 작업 문서 갱신 규칙 정리
- [ ] 운영 로그 확인 가이드

관련 문서:
- [`07_operations_docs.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/07_operations_docs.md)
- [`db_migration_plan.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/operations/db_migration_plan.md)
