# invest_bot agent guide

## 1. 프로젝트 목적

이 프로젝트의 목표는 국내주식 시장을 대상으로, 데이터를 수집하고 전략을 검증한 뒤 모의투자와 실거래로 확장 가능한 자동매매 연구/운영 도구를 만드는 것입니다.

현재는 아래 흐름을 안정적으로 연결하는 데 우선순위를 둡니다.

1. 데이터 수집
2. 지표 계산
3. 전략 신호 생성
4. 백테스트
5. 시장 리포트 생성
6. 대시보드 확인
7. 모의투자/실거래 준비

## 2. 현재 확정 요구사항

- 대상 시장은 국내주식입니다.
- 모의투자와 실거래를 모두 염두에 두되, 현재는 검증 가능한 구조를 우선합니다.
- 초기 전략은 `reference/` 기반 아이디어와 예시를 참고해 구현합니다.
- 전략 검증을 위한 데이터 수집 기능이 필요합니다.
- Python 3.13 기준으로 개발합니다.
- 패키지 관리는 `pip` 기준입니다.
- 테스트 도구는 `pytest`입니다.
- 구조나 실행 흐름이 바뀌면 `README.md`와 관련 문서를 함께 갱신합니다.

## 3. 에이전트 역할

이 프로젝트에서 에이전트는 `국내주식 자동매매 전략 분석·설계·구현 에이전트`로 동작합니다.

주요 책임 범위:

- reference guide 및 예제 분석
- 거래 데이터 수집 구조 설계
- 기술적 지표 계산 및 신호 해석
- 전략 설계 및 전략 인터페이스 표준화
- 백테스트 구현 및 결과 분석
- 모의투자와 실거래 흐름 분리
- 주문/리스크 관리 안전장치 설계
- Python 코드 구현, `pytest` 작성, 문서 갱신

기본 작업 순서:

1. reference 확인
2. 전략/지표 규칙 정리
3. 구현
4. 테스트
5. 백테스트 또는 검증
6. README 및 관련 문서 반영

## 4. 개발 원칙

- 실거래 기능보다 검증 가능한 구조를 우선합니다.
- 데이터 수집, 분석, 전략, 대시보드, 주문 로직은 최대한 분리합니다.
- 민감한 정보는 코드에 하드코딩하지 않고 설정 파일로 관리합니다.
- reference 예제를 그대로 복사하지 말고 프로젝트 구조에 맞게 재구성합니다.
- 문서와 실제 코드 상태가 어긋나지 않도록 작업 마무리 시 문서 갱신 여부를 확인합니다.

## 5. 참고 자산 사용 원칙

우선 참고 경로:

- `reference/open-trading-api/README.md`
- `reference/open-trading-api/docs/`
- `reference/open-trading-api/examples_llm/`
- `reference/open-trading-api/examples_user/`
- `reference/open-trading-api/backtester/`
- `reference/open-trading-api/strategy_builder/`

사용 규칙:

- API 인증, 시세 조회, 주문, 데이터 예제는 먼저 reference에서 확인합니다.
- reference 코드는 바로 복사하지 말고 현재 프로젝트 구조에 맞는 래퍼와 모듈로 분리합니다.
- reference와 현재 코드가 충돌하면 현재 프로젝트의 테스트 가능성과 구조 일관성을 우선합니다.

## 6. 의존성 관리 원칙

- 초기 구현 단계에서는 reference의 requirements 및 pyproject를 참고할 수 있습니다.
- 이후에는 독립 프로젝트 기준으로 판단합니다.
- 런타임 의존성은 `requirements.txt`, 개발/테스트 의존성은 `requirements-dev.txt`에 둡니다.
- GUI, 웹 서버, 시각화 패키지는 실제 기능 범위가 확정될 때 추가합니다.
- 의존성 변경 시 `README.md`를 함께 갱신합니다.

## 7. 권장 프로젝트 구조

```text
invest_bot/
  agent.md
  README.md
  docs/
    analysis/
    tasks/
    strategies/
  config/
  scripts/
  src/
    invest_bot/
      clients/
      config/
      dashboard/
      jobs/
      market/
      strategy/
      trading/
      risk/
      utils/
  tests/
```

## 8. 세션 분리 원칙

새로운 세션에서도 작업을 잘 이어가기 위해, 세션은 기술 스택보다 `작업 책임` 기준으로 나누는 것을 권장합니다.

### 8-1. 백엔드 세션

권장 범위:

- `src/invest_bot/clients/`
- `src/invest_bot/market/`
- `src/invest_bot/jobs/`
- `src/invest_bot/strategy/`
- `src/invest_bot/trading/`
- `src/invest_bot/risk/`
- `tests/`

적합한 작업:

- 데이터 수집
- 지표 계산
- 전략 신호 생성
- 백테스트
- 시장 리포트
- 주문/리스크 로직

### 8-2. 프론트엔드 세션

권장 범위:

- `src/invest_bot/dashboard/`
- `streamlit_app.py`
- 대시보드 관련 테스트
- UI 관련 문서

적합한 작업:

- Streamlit UI 개선
- HTML 대시보드 유지보수
- 데이터 탭/리포트 탭/실행 탭 UX 개선
- 시각화 및 필터링

### 8-3. 전략·백테스트 세션

권장 범위:

- `src/invest_bot/strategy/`
- `src/invest_bot/jobs/generate_*signals.py`
- `src/invest_bot/jobs/*backtest*.py`
- 전략/백테스트 문서

적합한 작업:

- 전략 추가
- 신호 생성 규칙 조정
- 백테스트 지표 고도화
- 전략 간 성능 비교

### 8-4. 운영·수집 세션

권장 범위:

- `src/invest_bot/jobs/collect_*`
- `src/invest_bot/jobs/scheduled_*`
- `config/collection_schedule.yaml*`
- 수집/운영 문서

적합한 작업:

- 다중 종목 수집
- 정기 수집
- 수집 실패 복구
- 운영 로그/상태 확인

### 8-5. 통합 세션

적합한 작업:

- 백엔드 기능을 대시보드에 연결
- 리포트/백테스트 결과를 UI에 반영
- 전체 파이프라인 실행 흐름 점검

## 9. 새 세션 시작 규칙

새 세션에서는 바로 구현에 들어가기 전에 아래를 먼저 확인합니다.

1. `README.md`
2. `agent.md`
3. `docs/tasks/00_summary.md`
4. 자신의 세션 범위와 직접 관련된 task 문서
5. 관련 실행 스크립트와 최근 테스트 파일

세션 시작 시 반드시 확인할 것:

- 현재 구현 완료 범위
- 아직 미완료인 항목
- 관련 디렉터리와 파일 범위
- 실행/검증 명령
- 최근 추가된 문서와 작업 원칙

## 10. 새 세션용 프롬프트 예시

자세한 예시는 [`claude_session_prompts.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/operations/claude_session_prompts.md) 문서를 참고합니다.

짧은 예시:

### 백엔드 세션

```text
현재 저장소의 백엔드 개발 현황을 파악해줘.
특히 데이터 수집, 지표 계산, 전략 신호, 백테스트, 시장 리포트 기준으로
1) 완료된 것
2) 미완료 항목
3) 관련 파일
4) 바로 실행 가능한 검증 명령
을 정리한 뒤, 오늘 이어서 할 수 있는 백엔드 작업 3개를 우선순위와 함께 제안해줘.
문서는 README.md, agent.md, docs/tasks/00_summary.md, 관련 task 문서를 먼저 참고해.
```

### 프론트엔드 세션

```text
현재 저장소의 프론트엔드(Streamlit/대시보드) 개발 현황을 파악해줘.
특히 개요/실행/데이터/리포트/테스트 탭 기준으로
1) 현재 구현 상태
2) 남은 UX 이슈
3) 관련 파일
4) 직접 확인 가능한 실행 명령
을 정리하고, 다음 UI 작업 후보 3개를 제안해줘.
문서는 README.md, agent.md, docs/tasks/00_summary.md, docs/tasks/04_dashboard.md를 먼저 참고해.
```

## 11. 금지 사항

- reference 코드를 검증 없이 실거래에 바로 연결하지 않습니다.
- 민감한 키, 계좌번호, 토큰을 저장소에 커밋하지 않습니다.
- 테스트 없이 주문 로직을 확장하지 않습니다.
- 전략과 주문 로직을 강하게 결합하지 않습니다.
- 모의투자와 실거래 흐름을 섞지 않습니다.
