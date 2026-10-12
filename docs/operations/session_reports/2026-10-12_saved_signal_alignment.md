# G04 — 저장 신호 정합성 검증 기록

> OKF 종류: `evidence` · 상태: `historical` · 기록일: 2026-10-12 KST

## 목적과 범위

기본 골든크로스 저장 신호가 현재 지표와 다른 날짜·종가를 사용해 백테스트 성과에 반영되는 문제를 수정하고 검증한 기록이다. 기준은 main `a22254a` + G04 미커밋 작업 트리다. 기존 퀀트 구현→메인 UI 연결→기존 QA 독립 검증→메인 통합·최종 검증을 하나씩 마쳤다. G04 완료이며 커밋 전 검토 상태다. 새 세션·병렬 전문 작업은 생성하지 않았다.

현재 계약은 [백테스트 task](../../tasks/05_strategy_backtest.md#저장-신호의-날짜가격-정합성-2026-10-12), 상태·완료 조건은 [퀀트 작업](../improvements/quant.md#g04)에서 관리한다. 이 기록의 성공 수치를 이후 변경의 검증으로 재사용하지 않는다.

## 수정 전 증거와 선택

메인의 기준본 메모리 재현에서 기간 밖 저장 신호·최신 거래일 누락·같은 날짜의 종가 불일치 세 입력이 모두 adapter와 runner를 통과해 거래 결과를 만들었다. 실제 운영 데이터에서 발생했다고 주장하는 결과는 아니다.

선택 정책은 현재 지표와 실제 사용할 기본 5/20 저장 신호의 거래일 집합·날짜별 종가가 다르면 명시적으로 차단하는 것이다. G03의 중복 검사와 로컬 달력 날짜를 공유한다. 정상 저장 신호·사용자 지정 MA·지표가 없는 기존 단독 실행은 구분한다. 상세 가격 유효성·혼합 표현·출처 계약은 task 문서에 있다.

## 변경

| 파일 | 변경 |
| --- | --- |
| [adapter](../../../src/invest_bot/backtest/adapters.py) | 날짜 집합·종가 대조, 무효 입력 차단, 검증된 혼합 날짜 보존 |
| [날짜 판정](../../../src/invest_bot/backtest/dates.py) | G03 판정을 행 순서가 보존되는 함수로 공유 |
| [생성기](../../../src/invest_bot/jobs/generate_backtest.py) | 명시/최신 지표 실제 로드·출처 반영, 선언 신호 컬럼 검사 |
| [대시보드](../../../src/invest_bot/dashboard/streamlit_backtest.py) | 실행 오류 시 이전 결과 삭제·차단 사유, 검사 안내, 실제 선택에 맞는 신호 출처 |
| [저장 신호 회귀](../../../tests/test_backtest_saved_signals.py) | 담당 신규64개: 날짜·가격·설정·생성/저장·시간대·불변성·정상 성과 |
| [대시보드 회귀](../../../tests/test_streamlit_backtest.py) | 메인 신규7개: 실제 action 차단 후 결과 정리·신호 출처 |
| [독립 QA](../../../tests/test_g04_independent_qa.py) | 신규74개: 입력 표현·미세 가격 차이·양쪽 무효값·저장 전 차단·실제 UI 호출 |
| [persistence fixture](../../../tests/test_backtest_persistence.py) · [SQLite 통합 fixture](../../../tests/test_db_frame_storage.py) | 실제 일치 지표를 임시 저장하고 명시 선택하도록 보정 |

원본의 실제 설정·백업·운영 데이터는 격리본에 복사하지 않았다. 기존 관리 worktree를 덮어쓰거나 초기화하지 않았다. 커밋·push·배포는 수행하지 않았다.

## 검증 경과

실패는 결함을 가진 당시 코드의 결과이며 이후 성공과 구분한다. 아래는 각 실행에서 선택한 테스트 수다.

| 실행 | 결과 | 의미 |
| --- | --- | --- |
| 담당 최초 회귀 | 35 failed / 14 passed | 날짜·가격 불일치와 지표 실제 연결을 수정 전 재현 |
| 담당 혼합 날짜 추가 | 3 failed / 50 passed | 대조 후 정규화의 혼합 offset/Timestamp 오류·NaT 손실 |
| 담당 가격 타입 추가 | 4 failed / 19 passed / 39 deselected | bool/complex 가격 진단 보완 전 |
| 담당 선언 신호 컬럼 추가 | 2 failed / 62 deselected | 잘못된 선언 파일의 재계산/빈 결과 우회 보완 전 |
| 담당 통합 smoke | 1 failed / 20 passed | 지표·신호 기간/종가가 상충하던 기존 임시 DB fixture |
| 담당 최종 관련 | 258 passed / 21 warnings | 신규64개와 기존 backtest·G03·UI·SQLite 기능 회귀 |
| 메인 대시보드 연결 수정 전 | 5 failed / 2 passed / 17 deselected | 실행 실패 후 이전 결과와 사용하지 않은 신호 출처 |
| 메인 통합 관련 | 265 passed / 21 warnings | UI 보완 신규7개까지 포함, 1.21s |
| QA 기존 관련 새 실행 | 265 passed / 21 warnings | 대상8파일 해시 일치, 1.59s |
| QA 첫 확대 실행 | 338 passed / 1 failed / 26 warnings | 일반 안내 문구를 결과 제목으로 오인한 신규 QA assertion |
| QA 최종 관련+독립 | 339 passed / 26 warnings | QA 제목 assertion만 보정, 기존265 + 독립74, 1.55s |
| 원본 최종 관련 | 339 passed / 26 warnings | 독립 파일을 원본에 통합한 새 실행, 1.52s |
| 원본 기본 suite | 780 passed / 2 deselected / 32 warnings | 기본 정책으로 외부망·PostgreSQL opt-in 제외, 22.21s |

날짜 helper의 메모리 검사 중앙값은 1,000행 ISO/Timestamp 0.645/0.707ms, 3,650행 1.879/2.176ms다. 각 warmup 1회 후 5회 측정했으며 wall-clock 상한 테스트를 추가하지 않았다. G03의 값별 datetime 파싱 반복은 재도입하지 않았다.

QA의 첫1개 실패는 일반 설명의 `거래 로그` 문구까지 이전 결과로 오인한 assertion이었다. 신규 QA 파일만 실제 결과 제목 `#### 거래 로그`의 표시 여부를 검사하도록 보정했다. 제품 조건을 완화하거나 skip/xfail로 숨기지 않았고 첫 실패 로그는 별도로 보존했다. 반복 실행의 수를 더해 테스트 수를 부풀리지 않는다.

독립 QA는 날짜 집합 전체·한 ULP 가격 차이·양쪽 무효값·7가지 날짜 표현·반복/MultiIndex와 입력 attrs 불변성을 확인했다. 실제 runner의 다음 종가 진입100·최종 신호 청산120·최종자산1.2·일별 단위자산 `[1, 1, 0.5, 1.2]`·MDD50%가 보존됐다. 메모리 단일 입력과 실제 임시 CSV/CLI에서 불일치 시 runner/context/persistence0회, output 디렉터리 미생성, 명시/최신 실제 지표 파일 출처를 확인했다. UI는 실제 action/execute/render를 유지하고 메모리 loader·fake Streamlit·차단 spy로 실패 사유·이전 결과 삭제·정상/custom 성공·복구 안내를 검사했다. 전체 다종목/다전략 batch의 원자성을 보장한 증거는 아니다.

원본 최종 JUnit은 관련339개와 기본780개 각각 failure/error/skip0개다. 외부망·PostgreSQL2개는 실행 선택에서 제외됐다. 기본32개 경고는 Alembic 설정6개, 기존 무효 날짜 소비자의 형식 추론5개, 혼합 offset의 pandas FutureWarning21개이며 억제하지 않았다. Python3.13.13/pandas2.3.3에서 검증했고 pandas3 호환성은 미검증이다.

## 재현 명령과 환경

Python 실행 환경을 비우고 자격증명/DB 환경 및 실제 외부 socket을 차단하는 conftest로 검증한다. 메모리 storage·임시 CSV·임시 SQLite만 사용했다. 원본 통합 관련 명령은 아래와 같다.

```sh
env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp .venv/bin/python -B -m pytest \
  tests/test_backtest_saved_signals.py tests/test_backtest_registry.py \
  tests/test_backtest_adapters_runner.py tests/test_backtest_generator.py \
  tests/test_backtest_persistence.py tests/test_backtest_parameters.py \
  tests/test_backtest_dates.py tests/test_g03_independent_qa.py \
  tests/test_backtest_combination.py tests/test_backtest_portfolio.py \
  tests/test_streamlit_backtest.py tests/test_db_frame_storage.py \
  tests/test_g04_independent_qa.py -q --tb=short

env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  .venv/bin/python -B scripts/run_tests.py --suite default -q --tb=short
```

patch SHA256 `47d027f1d13d8491b1979a7007683e99613288bdfb754623a3ce5a44e8e45110`과 담당6파일 manifest를 통합 전 대조했다. QA 대상8파일은 시작·종료에 일치했고 원본의 독립 파일까지 포함한9파일 SHA256·AST를 최종 실행 전후 확인했다. 원본 설정4개·기존 백업 파일은 시작 시점과 동일하며 HEAD는 `a22254a`다. 원본 적용·공백 검사도 통과했다. 변경 문서10개의 로컬 링크·앵커287개와 등록부 ID 유일성도 통과했고, 예상 변경19파일 외 신규 수정과 staged 파일은 없다. 별도 lint/typecheck 도구는 기준 저장소에 구성되어 있지 않으며 설치하지 않았다.

## 최종 대상 SHA256

아래는 독립 QA·원본 최종 테스트와 일치한 기능/회귀9파일의 해시다. 이후 변경이 있으면 새 검증이 필요하다.

```text
665e843d1e0da1372e946298d0c2a267bf075c7ab2474ce56eaa3abfdda738ff  src/invest_bot/backtest/adapters.py
b6d8cf8110d2b42db35f6be5b0bbc740f9a27abfe08896f356fb7ecb3d414325  src/invest_bot/backtest/dates.py
2f27c032819a3270112dd8ee350d3b1b6079b682eec26a95a4d70dd1fb2bdcc5  src/invest_bot/jobs/generate_backtest.py
2ef91e58fb07b72759b71bad9b0c79fdd6817857d606497ebed7f960e28aa248  tests/test_backtest_saved_signals.py
dae9051964fc660f49404aca63e18fb426198dcf3d7b7cce635dfbe5ea2cc28c  tests/test_backtest_persistence.py
40b7f797061160bcb78528fcbfd0a645fba2624dcb078f231f1400bb73b371db  tests/test_db_frame_storage.py
2fa6bb13e4b057aaf79880a7775ed4e5d5f0303b8ae01ab45b175ee503c6b768  src/invest_bot/dashboard/streamlit_backtest.py
b92b444867c74f5fe8d2d13df9348b943931c119072d290f728fa2c75fbb96fc  tests/test_streamlit_backtest.py
6cde353cb175c51b6bead4c85430e41b77f315b76642d5d8814fc64234227f19  tests/test_g04_independent_qa.py
```

## 관계와 미검증

- [G03](2026-10-10_backtest_duplicate_dates.md)의 날짜 중복 차단을 보존하며 [K-EQUITY](../../knowledge/concepts.md) 입력 정합성을 보완한다.
- 운영 데이터·운영 DB/API·실제 Docker·브라우저·전송·배포·원격 CI는 검증하지 않았다. UI 증거는 fake Streamlit과 실제 생성/action 경계의 메모리 검증이다.
- 현재 지표 없는 단독 실행, 직접 수동 runner 입력은 현재 지표와의 정합성을 증명하지 않는다. 숫자 YYYYMMDD·소비자 전반 시간대 통일·pandas 3 호환성·신호 계산 자체의 정확성/미래 정보 누출·수급/가격 원천 인증은 범위 밖이다.
- G01a·QA01 원격 CI 대기, G05a 이후 화면 연결, G08c 조합 metadata 상태는 이번 성공으로 변경하지 않는다.
