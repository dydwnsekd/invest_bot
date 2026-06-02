# Task 04. Dashboard

## 목표

수집, 분석, 신호, 리포트, 테스트 상태를 브라우저에서 빠르게 확인하고 필요한 작업을 직접 실행할 수 있는 대시보드를 제공한다.

## 완료된 항목

- [x] HTML 기반 로컬 대시보드 구현
- [x] Streamlit 기반 대시보드 초안 구현
- [x] raw/processed 데이터 미리보기 구현
- [x] 골든크로스 신호 및 시장 리포트 표시
- [x] 테스트 결과 표시
- [x] 데이터 수집 실행
- [x] 지표 계산 실행
- [x] 골든크로스 신호 생성 실행
- [x] 시장 리포트 생성 실행
- [x] 전체 파이프라인 실행
- [x] 정기 수집 상태와 최근 실행 로그 표시

## 남은 항목

- [ ] 종목 비교 차트
- [ ] 최신 수집/분석 시각 강조
- [ ] 백테스트 결과 시각화
- [ ] 대시보드 설정 저장 고도화

## 접속 정보

HTML 대시보드:

```text
http://127.0.0.1:8000
```

Streamlit 대시보드:

```text
http://localhost:8501
```

## 관련 파일

- [`service.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/service.py)
- [`server.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/server.py)
- [`streamlit_dashboard.py`](/C:/Users/user/PycharmProjects/invest_bot/src/invest_bot/dashboard/streamlit_dashboard.py)
- [`run_dashboard.py`](/C:/Users/user/PycharmProjects/invest_bot/scripts/run_dashboard.py)
- [`run_streamlit_dashboard.py`](/C:/Users/user/PycharmProjects/invest_bot/scripts/run_streamlit_dashboard.py)
