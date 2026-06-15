# UltraQA Report - 2026-06-15

## Goal and success criteria

- Goal: 현재 프로젝트 기능 QA 수행
- Scope adjustment: Chrome plugin 실제 연동 브라우저 테스트는 QA 범위에서 제외
- Stop condition: 로컬 프로젝트 웹과 앱 기능 기준으로 검증 완료
- Safety bounds applied:
  - 실제 데이터 수집 최소화
  - 프로젝트 관련 local web만 접근
  - 외부 생산성/계정/비프로젝트 URL 미접근
  - 강제 reset/삭제 없음

## Scenario matrix

| ID | User/attacker model | Scenario | Command/harness | Expected signal | Actual result | Status | Evidence | Cleanup |
|---|---|---|---|---|---|---|---|---|
| BASE-001 | normal user | baseline 전체 테스트 | `.venv/bin/python -m pytest -q` | green | `81 passed in 1.50s` | passed | fresh local run | n/a |
| ENV-001 | normal user | compose로 web 실행 | `docker compose up -d db migrate web` | web up | `127.0.0.1:8000` `200 OK` | passed | curl HEAD 200, compose status | cleaned |
| UI-001 | normal user | 작업 실행 탭 진입 | Streamlit AppTest in container | widgets visible, no exception | 버튼/선택 위젯 노출, 예외 없음 | passed | AppTest output | n/a |
| UI-002 | normal user | 지표 계산 | AppTest click `지표 계산` | success message | 성공 메시지 표시 | passed | saved path `/virtual/db/...daily_prices_indicators...` | n/a |
| UI-003 | normal user | 신호 생성 | AppTest click `신호 생성` | success message | 성공 메시지 표시 | passed | saved path `/virtual/db/...golden_cross_signals...` | n/a |
| UI-004 | normal user | 리포트 생성 | AppTest click `리포트 생성` | success message | 성공 메시지 표시 | passed | saved path `/virtual/db/...market_reports...` | n/a |
| ADV-001 | malformed/empty input | 빈 멀티선택에서 데이터 수집 | AppTest set multiselect `[]` + click | clear validation error | 올바른 오류 메시지 표시 | passed | `자동완성 목록에서 종목을 하나 이상 선택해 주세요.` | n/a |
| UI-005 | normal user | 리포트/데이터/검증 탭 순회 | AppTest tab clicks | no exception | 예외 없음, 검증 탭 success 표시 | passed | `현재 저장된 테스트 결과에는 실패가 없습니다.` | n/a |
| TEST-001 | misleading success guard | 대시보드 관련 테스트 리포트 생성 | `docker exec invest-bot-web ... run_tests.py ...` | exit 0 + junit | `19 passed` and junit xml | passed | fresh container run | kept as runtime artifact only |
| HTTP-001 | hostile direct caller | 추정 action POST 직접 호출 | `curl -X POST /actions/...` | explicit app behavior | `405 Method Not Allowed` | passed | fresh HTTP responses | n/a |

## Commands run

- `[0] .venv/bin/python -m pytest -q` — baseline regression, `81 passed in 1.50s`
- `[0] docker compose up -d db migrate web` — local app start
- `[0] curl -I --max-time 5 http://127.0.0.1:8000` — web health, `200 OK`
- `[0] docker exec invest-bot-web sh -lc 'python scripts/run_daily_analysis.py 005930 && python scripts/run_golden_cross_signals.py 005930 && python scripts/run_market_report.py 005930'` — non-collection feature generation
- `[0] docker exec invest-bot-web ... AppTest ...` — live UI harness for actions/tabs/validation
- `[0] docker exec invest-bot-web sh -lc 'python scripts/run_tests.py ...'` — dashboard test evidence, `19 passed`
- `[0] docker compose down` — cleanup
- `[0] omx state clear --input '{"mode":"ultraqa"}' --json` — UltraQA state cleanup

## Failures found

- 범위 내 기능 QA에서 확인된 실패 없음

## Fixes applied

- No source-code fixes applied
- Functional verification used safe substitute:
  - live container-side Streamlit AppTest harness
  - local-only HTTP checks
  - compose runtime verification

## Cleanup and rollback

- Generated artifacts removed or intentionally kept:
  - UltraQA state cleared
  - Docker services shut down
  - no temp repo files added by QA
- State/process cleanup performed:
  - `docker compose down` complete
  - final `docker compose ps` empty
- Worktree status before/after:
  - unchanged pre-existing dirty state remained:
    - `M .gitignore`
    - `?? .DS_Store`
    - `?? docs/.DS_Store`
    - `?? migrations/versions/20260612_000002_add_dataset_frames.py`

## Residual risks

- Multi-symbol real collection path was intentionally not exercised to satisfy `실제 데이터 수집 최소화`
- Chrome plugin 실제 연동 브라우저 검증은 이번 QA 범위에서 제외됨

## Evidence

- Web health: `HTTP/1.1 200 OK` from `http://127.0.0.1:8000`
- Baseline: `81 passed in 1.50s`
- Dashboard-focused tests: `19 passed in 0.60s`
- UI harness:
  - `지표 계산 완료`
  - `골든크로스 신호 생성 완료`
  - `시장 리포트 생성 완료`
  - empty selection validation error displayed correctly

## Recommended next steps

1. 현재 앱 기능 QA는 통과로 간주
2. 필요 시 별도 작업으로 Chrome plugin 연동 문제만 분리 진단
3. 실제 데이터 수집 최소화 조건을 유지한 채 다중 종목/장시간 시나리오는 추가 QA 가능
