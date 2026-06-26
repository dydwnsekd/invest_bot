# Task 04. Dashboard

## 목표

수집, 분석, 신호, 리포트, 테스트 상태를 브라우저에서 빠르게 확인하고 필요한 작업을 직접 실행할 수 있는 대시보드를 제공한다.

## 완료된 항목

- [x] Streamlit 기반 대시보드 구현
- [x] raw/processed 데이터 미리보기 구현
- [x] 골든크로스 신호 및 시장 리포트 표시
- [x] 리포트 해석 탭에서 선택된 1건 중심 본문 표시
- [x] 리포트 카드 내 전략별 판단 요약 표시
- [x] 테스트 결과 표시
- [x] 데이터 수집 실행
- [x] 지표 계산 실행
- [x] 골든크로스 신호 생성 실행
- [x] 시장 리포트 생성 실행
- [x] 전체 파이프라인 실행
- [x] 정기 수집 상태와 최근 실행 로그 표시

## 남은 항목

- [ ] 리포트 즐겨찾기 저장
- [ ] 종목 비교 차트
- [ ] 최신 수집/분석 시각 강조
- [ ] 백테스트 결과 시각화
- [ ] 대시보드 설정 저장 고도화

## 현재 리포트 해석 탭 동작

- 상단 선택 컨트롤로 종목/리포트를 고른 뒤 본문에는 선택된 1건만 표시
- 선택된 리포트 아래에서 차트와 상세 데이터 표를 계속 확인 가능
- `final_opinion`과 별도로 RSI / Trend Filter / Mean Reversion 전략의 직접 판단과 이유를 함께 표시
- 즐겨찾기 저장 기능은 아직 구현되지 않음

## 접속 정보

대시보드:

```text
http://127.0.0.1:8000
```

## 관련 파일

- [`service.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/service.py)
- [`streamlit_dashboard.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/streamlit_dashboard.py)
- [`streamlit_reports.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/streamlit_reports.py)
- [`run_dashboard.py`](/C:/Users/user/PycharmProjects/invest_bot/scripts/run_dashboard.py)
- [`run_streamlit_dashboard.py`](/C:/Users/user/PycharmProjects/invest_bot/scripts/run_streamlit_dashboard.py)
