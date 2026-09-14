# invest_bot 개선 작업 세션

## 공통 기준

- 작성일: 2026-09-13
- 통합 작업: `Agent main`
- 통합 작업 ID: `01a09a75-fc7c-7ec0-8296-aed358d3152c`
- 분석 기준 커밋: `9e54fe6f8a009cdb6adeb3b002d85422e33c1779` (`main`)
- 실행 방식: 역할별 기존 작업 1개와 별도 Codex worktree를 유지한다. 2026-09-15 사용자 요청에 따라 한 번에 작업 하나만 실행하고 검증한다. 병렬 하위 작업·추가 세션 생성은 하지 않는다.
- 실행 모델: 5개 작업 모두 `gpt-5.6-sol`, reasoning effort `medium`. 리셋 크레딧은 사용하지 않는다.
- 이 문서와 공통 README/task 문서의 최종 통합은 통합 작업이 맡는다.
- 각 작업은 자신의 worktree에서만 수정한다. 원본 프로젝트의 설정, 데이터, 미등록 파일을 수정하거나 다른 작업의 변경을 되돌리지 않는다.
- 새 라이브러리 도입, 실제 주문, 운영 DB 마이그레이션, 원격 push/배포는 이번 1차 작업에 포함하지 않는다.
- 각 기능 작업은 해당 기능의 회귀 테스트도 소유한다. QA는 별도의 통합·환경 검증 파일을 소유한다.
- 각 작업은 검증된 변경을 로컬 커밋으로 남기고 커밋 ID, 변경 파일, 검증 결과, 통합 주의점을 최종 보고한다. 다른 작업의 결과를 임의로 merge/cherry-pick하지 않는다.

## 확인한 기준점 이슈

1. 원본에만 미등록 마이그레이션 `migrations/versions/20260703_000003_add_report_favorite_symbols.py`가 존재한다. 데이터 작업이 검토 후 자신의 worktree에 포함한다. revision은 `20260703_000003`, down_revision은 `20260612_000002`이며 `report_favorite_symbols` 테이블을 만든다. 다른 작업은 이 파일을 별도로 구현하지 않는다.
2. 미등록 마이그레이션을 포함한 임시 복사본에서 전체 테스트 결과는 `340 passed, 2 failed`였다. 두 실패는 DB 초기화의 종목 마스터 다운로드가 네트워크 제한으로 실패한 경우다. 임시 종목 마스터 fixture를 제공한 뒤 해당 두 테스트는 통과했다.
3. `tests/test_init_db_script.py`는 현재 프로젝트 설정 파일을 잠시 덮어쓴다. QA 작업이 임시 설정과 현재 Python 실행 파일을 사용하도록 격리한다. 원본 프로젝트에서 이 테스트를 실행하지 않는다.
4. 실제 운영 DB의 데이터 상태, 외부 API 응답, Docker 실행 결과와 사용자 화면의 지연 시간은 이번 분석에서 검증하지 않았다.

## 역할과 파일 소유권

| 작업 | 역할 | 소유 범위 | 1차 목표 |
| --- | --- | --- | --- |
| 데이터 수집·저장 개선 | executor | `src/invest_bot/clients/`, `src/invest_bot/market/`, `src/invest_bot/db/`, `migrations/`, `src/invest_bot/jobs/collect_market_data.py`, 관련 데이터 단위 테스트 | 마이그레이션 누락 해소, 수급 다중 행 보존, 종목 메타데이터 보존, 부분 저장 상태의 정확성 |
| 퀀트·백테스트·리포트 개선 | executor | `src/invest_bot/backtest/`, `src/invest_bot/strategy/`, 지표·신호·백테스트·시장 리포트 job, 관련 단위 테스트 | 일별 평가금액 기준 MDD, 리포트 기준일 일관성 |
| 대시보드 구조·조회 개선 | designer/executor | `src/invest_bot/dashboard/`, `streamlit_app.py`, 대시보드 관련 단위/AppTest 테스트 | 조회 비용 측정과 반복 조회 축소, 동작을 보존하는 책임 분리 |
| 운영·배포 안정화 | executor | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `config/*.example`, `scripts/` 중 `run_tests.py` 제외, `src/invest_bot/jobs/scheduled_collection.py`, 운영 관련 단위 테스트 | 쓰기 가능한 로그 경로, migration과 마스터 초기화 분리, 시작·재시작 검증 |
| QA·독립 검증 체계 개선 | test-engineer/verifier | `tests/conftest.py`, `tests/helpers.py`, `tests/test_init_db_script.py`, 신규 독립 통합 테스트, `pytest.ini`, `scripts/run_tests.py`, `.github/workflows/` | 설정·네트워크 격리, 기존 의존성을 이용한 CI와 회귀 검증 |

운영 작업은 `tests/test_init_db_script.py`를 수정하지 않고 QA 작업에 필요한 실행 계약을 보고한다. QA 작업은 기능 작업이 소유한 테스트 파일을 변경하지 않는다. 대시보드 작업은 백테스트 수식과 DB repository를 수정하지 않는다. 퀀트 작업은 대시보드 모듈을 수정하지 않고 필요한 연결 변경을 통합 작업에 보고한다.

## 완료 조건

- 데이터: 여러 날짜의 수급이 모두 보존되고 빈 응답이 정상 fact로 생성되지 않는다. 수집으로 기존 종목명·시장 구분이 손상되지 않는다. 일부 저장 후 실패한 경우 실제 저장 상태가 실행 결과에 반영된다. 신규/기존 스키마 마이그레이션을 임시 DB에서 검증한다.
- 퀀트: 보유 중 `100 → 50 → 100`인 사례의 일별 MDD는 50%이며 요약과 일치한다. 첫 손실 거래도 초기자산을 기준으로 낙폭에 포함한다. 리포트에는 선택 기준일보다 미래의 값이 포함되지 않고 역순·결측·서로 다른 날짜의 입력이 명시적으로 처리된다.
- 대시보드: 수정 전후 동일 fixture에서 조회 횟수와 실행 시간을 기록한다. 현재 UX, 홈/관심종목의 조회 전용 동작, 탭 왕복 설정, 기존 저장 이력 해석을 보존한다. 저장 후 갱신된 값이 보이도록 캐시 수명이나 무효화 범위를 명시한다.
- 운영: 기본 예시 설정의 로그가 읽기 전용 config 아래에 쓰이지 않는다. migration만 검증할 수 있고 외부 종목 마스터가 실패해도 스키마 결과를 구분할 수 있다. Docker 검증이 불가능하면 정적 검증과 실행 미검증 범위를 구분한다.
- QA: 기본 테스트가 원본 설정·운영 DB·실제 네트워크에 의존하지 않는다. 실패를 skip/xfail로 숨기지 않는다. 데이터/퀀트의 알려진 결함은 기존 기준점 실패와 기능 변경 후 통과를 구분해 기록한다. PostgreSQL 검증을 실제 실행하지 못하면 통과로 보고하지 않는다.

## 작업 결과 문서

각 작업은 자신의 worktree에 `docs/operations/session_reports/2026-09-13_<data|quant|dashboard|operations|qa>.md` 한 개를 작성한다. 해당 문서는 작업별 전용 파일이며 공통 README·DESIGN·task 요약 변경 제안도 여기에 기록한다.

## 진행 순서

1. 데이터 수집·저장 개선의 남은 수정과 검증을 마친다.
2. 퀀트·백테스트·리포트 개선을 이어서 검증한다.
3. 대시보드 구조·조회 개선을 이어서 검증한다.
4. 완료된 운영 변경의 연결 경계를 확인하고 마지막에 QA 전체 회귀를 실행한다.
5. 동시에 실행하는 전문 작업은 최대 1개다. 이번 진행 단위는 데이터 작업만 마무리하며 다른 역할은 대기한다.

## 생성된 작업

2026-09-14 재개 시 다섯 작업 모두 `active`, 첫 turn `inProgress`와 실제 진행 메시지를 `wait_threads`/`read_thread`로 확인했다. 생성 직후 반환된 임시 client ID 대신 아래 실제 작업 ID를 사용한다. 구현·통합 완료를 뜻하는 상태는 아니다.

공통 시작 커밋은 `c96894e6929d303d90f3b06543db66913e37084a`이며 분석 기준점 이후 이 계획 문서만 추가된 상태다. 각 작업의 실행 기록에서 `gpt-5.6-sol` / `medium`도 확인했다.

| 작업 | 실제 작업 ID | 별도 worktree | 확인 상태 |
| --- | --- | --- | --- |
| 데이터 수집·저장 개선 | `01a09f69-26a0-73a1-a41c-abb29ecb3bb2` | `/Users/yongjun/.codex/worktrees/2ea9/invest_bot` | 완료: 추가 수정까지 통합, 표적 28 passed |
| 퀀트·백테스트·리포트 개선 | `01a09f6c-35f9-7173-a826-9dd3d935e48e` | `/Users/yongjun/.codex/worktrees/e3ce/invest_bot` | 대기: 다음 순차 작업 |
| 대시보드 구조·조회 개선 | `01a09f6c-6be5-7202-b419-e3868064b276` | `/Users/yongjun/.codex/worktrees/201c/invest_bot` | 대기: 미커밋 변경 보존 |
| 운영·배포 안정화 | `01a09f6c-7e19-7590-97db-9a4d00780afc` | `/Users/yongjun/.codex/worktrees/fdb1/invest_bot` | 1차 완료·통합, 최종 연결 검증 대기 |
| QA·독립 검증 체계 개선 | `01a09f6c-9079-7c52-985b-3ed039b3340b` | `/Users/yongjun/.codex/worktrees/cdc4/invest_bot` | 1차 완료·통합, 전체 통합 회귀 대기 |

## 순차 진행 전환 (2026-09-15)

- 이전 생성 요청도 실제 작업으로 남아 있었음을 확인했다. 코드 변경이 없고 사용량 제한으로 실패한 아래 중복 작업 5개는 보관 처리했다. 작업 폴더는 삭제하지 않았다.
  - 데이터: `01a09a81-e321-7c81-9977-41e18694a9fb`
  - 퀀트: `01a09a81-ed23-7d92-8458-7102badc7cfe`
  - 대시보드: `01a09a81-fb1b-7981-a6b9-0ae9a2a25558`
  - 운영: `01a09a82-0e3c-7e33-8aee-aed944b0e532`
  - QA: `01a09a82-1d52-75d2-a1d9-96fc107a2127`
- 위 표의 9월 14일 작업 5개만 정식 역할별 작업으로 유지한다. 데이터·퀀트·대시보드의 실행 중단과 `idle` 상태를 확인한 뒤 순차 진행으로 전환했다.
- 로컬 통합 브랜치: `codex/integrate-improvements-20260915`. 운영·QA 및 데이터·퀀트의 1차 커밋을 반영했으나 최종 통합은 미완료다.
- 원본 관심종목 migration은 데이터 작업 결과와 바이트 단위 일치를 확인한 뒤 내용 변경 없이 등록했다. `.restart.sh.un~`는 그대로 보존한다.
- 확인한 통합 검증: 데이터/퀀트/운영 표적 64 passed, 초기화 모드/실제 subprocess 8 passed, 임시 PostgreSQL 최신 migration 1 passed. QA 임시 컨테이너 `invest-bot-qa-cdc4`는 중지·자동 제거를 확인했다.
- 데이터 작업 완료: 잘못된 수급 행의 개별 처리와 동일 저장 단계 부분 성공 보고를 `dd2dfc8`로 마무리하고 통합 브랜치에 `d9f2eca`로 반영했다. 통합 후 관련 테스트 28 passed를 확인했다.
- 퀀트 대기: 숫자형 날짜 수정 커밋 `2530743` 및 실제 수급 관측일 연결 수정의 최종 검증·통합.
- 대시보드 대기: 조회 재사용·이력 모듈 분리·운영 실패 상태 표시의 미커밋 변경을 보존한다.
