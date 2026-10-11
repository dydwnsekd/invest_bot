# 백테스트 중복 거래일 검증 기록

> OKF 종류: `evidence` · 상태: `historical` · 착수: 2026-10-10 · 통합·검증: 2026-10-11

## 대상과 진행 방식

- 기준: 원본 main `7fb6435` + G03 작업 트리.
- 작업: [G03](../improvements/quant.md#g03).
- 기존 **퀀트·백테스트·리포트 개선** 구현 → 기존 **QA·독립 검증 체계 개선** → 퀀트 보완 → QA 재검증을 하나씩 실행했다. 메인이 원본 통합·최종 검증·공유 문서를 담당했다. 새 세션은 생성하지 않았으며 두 역할은 종료 후 idle이다.
- git archive의 tracked 파일을 임시 복사해 담당 구현·QA를 검증했다. 실제 설정·운영 데이터·과거 worktree는 변경하지 않았다. G03 테스트에서는 운영 DB·API·수집·Discord·Docker·커밋·push를 실행하지 않았다. 별도 사용자 요청에 따른 Docker 읽기 전용 확인은 아래에 구분한다.
- 한 종목의 같은 일별 거래일 중복은 임의 선택하지 않고 차단한다. 입력 검사·adapter·runner·평가곡선·조합의 경계를 확인한다.
- G04 저장 신호의 날짜·가격 정합성, G08c 재현 metadata는 별도 작업이다.

## 수정 전 메인 재현

원본 `7fb6435`에서 메모리 입력4행(4월 1일 buy100, 2일 sell100, 3일 hold100·hold200)을 실행했다. RSI readiness는 준비 완료였고 거래1건의 수익률은0%였으나 요약 총수익률은100%, 일별 곡선 최종자산은 초기1.0 대비2.0이었다. 곡선에는3일의 마지막 종가200만 남았다. 입력 프레임은 변경되지 않았다. 운영 데이터에서 발생했음을 뜻하는 증거는 아니다.

메인 재현 산출물: `/private/tmp/invest-bot-g03-bo8mgzoj/main-baseline.json`.

## 구현과 검증 결과

G03 완료 조건을 충족했다. 원본 최종 관련152개·기본635개를 통과했으며 검증 종료 당시에는 커밋 전 검토 상태였다. 이후 사용자 요청으로 소스·회귀·이 기록과 Docker 설정 제외 보완을 같은 main 커밋에 포함한다. G04·G08c는 진행하지 않았다.

- [공통 날짜 판정](../../../src/invest_bot/backtest/dates.py)은 유효한 같은 로컬 달력 날짜를 차단하고 데이터셋·중복 날짜 최대3개·거래일당 한 행 정책을 오류에 제공한다. 값이 같은 중복도 거부하며 입력을 변경하지 않는다.
- [readiness](../../../src/invest_bot/backtest/readiness.py), [저장 신호 adapter](../../../src/invest_bot/backtest/adapters.py), [runner·평가곡선](../../../src/invest_bot/backtest/runner.py), [전략 조합](../../../src/invest_bot/backtest/combination.py)에 적용했다. 신호 계산·가격 필터·행 선택 전에 검사하며 곡선·조합의 마지막 행 임의 선택을 제거했다.
- 정규화된 수급의 date/trade_date 별칭과 date 우선순위, 부족 컬럼의 기존 차단 사유를 유지한다. 원본 수급 상세 행을 새로 변환하지 않는다.
- 빈 입력·NaT·정렬·다음 종가 체결·마지막 종가 청산·보유 중 MDD50%·첫 손실·무거래·미청산 평가·서로 다른 종목/전략의 개별 입력을 보존했다.
- [담당 회귀](../../../tests/test_backtest_dates.py)64개와 [독립 회귀](../../../tests/test_g03_independent_qa.py)63개를 추가했다. 기존 관련25개를 포함한 최종 관련 수는152개다. 메모리 generator에서 중복 입력의 저장0회와 준비표·경고의 차단 사유 노출도 검증했다.

## 독립 QA 발견과 보완

초기 퀀트 구현은 관련89개·기본572개를 통과했지만 첫 독립 QA에서 혼합 timezone Timestamp가 pandas 일괄 해석 중 NaT로 바뀌어 중복을 놓치는 결함을 발견했다. Timestamp+문자열은 계약 오류 대신 pandas 오류를 냈다. 다섯 입력 경계의 표현별15개 실패가 재현됐으며 해당 시점에는 완료 판정을 보류했다.

보완은 공통 helper 한 파일에 한정했다. 이미 해석된 date/datetime/Timestamp는 원래 로컬 달력 날짜를 사용하고 나머지 값만 일괄 해석한다. UTC 변환 없이 두 집합을 합쳐 날짜를 비교한다. 원래 무효 값과 배치 해석에서 잘못 사라진 유효 날짜를 구분하며 반복 index가 중복을 숨기지 않는다.

처음 실패 로그를 보존하고 보완 후 성공을 별도 기록했다. QA를 종료한 뒤 퀀트가 보완했고 퀀트 종료 뒤 QA가 새로 검증했다.

| 실행 단계 | 대상과 새 결과 |
| --- | --- |
| 최초 독립 QA | 초기 helper, 관련89+독립37: 111 passed / 15 failed |
| 퀀트 보완 | date 객체 분리 후 관련126 passed |
| 독립 재검증 | 보완 코드126 passed; date/datetime·반복 index26개 추가 후152 passed |
| 원본 관련 검증 | 최종 소스·담당64·독립63 회귀: 152 passed, 13 warnings, 1.05s |
| 원본 기본 suite | 635 passed / 2 deselected, 19 warnings, 21.12s |

독립 최종 검사 시점은 2026-10-11 15:57~15:59 KST다. 보완 helper SHA256은 `26e9705a0db0a401ada5c8f6baf4f7ef3a31f37c3da34c3f8cbf1b2b13f74cd5`다. 원본 통합 후 같은 파일과 최종 독립 테스트를 새로 실행했다.

## 원본 검증 명령과 환경

Python3.13.13 / pandas2.3.3. 아래 명령은 저장소 루트에서 실행했다. 기본 suite는 credential/DB 환경변수 제거와 socket.connect 차단 fixture를 사용하며 PostgreSQL·외부 network opt-in 검증을 실행하지 않는다. 기본 정책으로2개가 제외됐고 신규 skip/xfail은 추가하지 않았다.

```sh
env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp .venv/bin/python -B -m pytest tests/test_backtest_registry.py tests/test_backtest_adapters_runner.py tests/test_backtest_combination.py tests/test_backtest_dates.py tests/test_g03_independent_qa.py -q --junitxml=/private/tmp/invest-bot-g03-bo8mgzoj/main-final-targeted.xml
env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp .venv/bin/python -B scripts/run_tests.py --suite default -q
git diff --check
```

기본 suite 보고서는 `data/processed/test_reports/pytest_results.xml`, 명령 기록은 `pytest_command.txt`에 있다. 테스트 전후 실제 설정 네 파일과 기존 `.restart.sh.un~`의 내용이 같음을 확인했다. 실제 설정·키·토큰은 출력하지 않았다.

변경 Python7개 AST 구문 검사와 공백 검사도 통과했다. 별도 lint/typecheck 설정·도구는 프로젝트에 없어 해당 실행 결과를 주장하지 않는다. 최종 변경 문서11개의 로컬 링크·anchor276개와 등록부56개 ID를 검사해 누락·중복0건을 확인했고 독립 QA가 검토한 helper·테스트와 원본 hash도 일치했다. 정적 검사 기록은 담당 임시본의 `main-final-static-docs.json`에 있다.

최종 기본 suite의 경고19개는 기존 Alembic6개, 무효 날짜 소비자의 형식 추론5개, mixed-offset 문자열 파싱의 pandas FutureWarning8개다. 현재 pandas 버전의 동작을 검증했으며 경고를 숨기거나 UTC 날짜로 정책을 바꾸지 않았다.

## 날짜 검사 비용

초기 행별 pd.to_datetime 해석은 메인 리뷰에서1,000행당 약0.75초로 관찰돼 통합 전 보완했다. 최종 독립 측정은 같은 메모리 입력에 warmup1회·반복5회였다.

| 행 수 | ISO 문자열 중앙값(ms) | naive Timestamp 중앙값(ms) |
| --- | ---: | ---: |
| 1,000 | 0.581 | 0.634 |
| 3,650 | 1.681 | 1.975 |

이는 helper의 메모리 검사 관측값이며 브라우저 지연이나 전체 백테스트 성능의 측정은 아니다. 불안정한 시간 상한 테스트는 추가하지 않았다.

## 별도 사용자 요청: 14:47 API·토큰 기록

2026-10-11 사용자 요청에 따라 기존 scheduler 로그와 컨테이너의 토큰 캐시 메타데이터를 읽었다. API 재발급·수집·서비스 변경은 실행하지 않았다.

- scheduler 모의투자 토큰 캐시 저장 시각: **2026-10-11 14:47:39.972 KST**, 토큰 존재 확인.
- scheduler 수집 완료: **14:47:40 KST**, 성공2·실패0. 컨테이너의 UTC 기록05:47:40을 변환했다.
- 실행 중인 KIS client와 저장소 코드의 hash가 같았다. [authenticate](../../../src/invest_bot/clients/kis_client.py)는 발급 응답 성공 처리 뒤 캐시를 저장하므로 그 시점의 발급 성공으로 판단했다.
- 개별 HTTP 요청 로그가 없어 정확한 요청 시작 시각·각 endpoint 호출 내역까지 직접 확인한 것은 아니다. 캐시 시각·코드 흐름에 근거한 판단과 수집 완료 기록을 구분했다. 키·토큰 값은 출력하지 않았다.

이 읽기 전용 조회는 G03의 배포·운영 백테스트 검증을 뜻하지 않는다.

## 증거 파일과 미검증 범위

담당 임시본: `/private/tmp/invest-bot-g03-bo8mgzoj/`.

- `G03.patch`, `G03-report.md`: 최초 구현 기록.
- `G03-timezone-fix.patch`, `G03-timezone-fix-report.md`, `timezone-red.log`, `timezone-green.log`: QA 결함의 보완 기록.
- `main-final-targeted.xml`, `main-final-targeted.log`, `main-final-full.log`: 원본 최종 실행 기록.

독립 임시본: `/private/tmp/invest-bot-g03-qa-20261011.48hBTS/`.

- `artifacts/G03-QA-report.md`, `combined.xml`, `combined-output.txt`: 첫 QA의15개 실패 기록.
- `artifacts/timezone-followup/G03-QA-timezone-followup-report.md`, `final-152.xml`, `final-152.log`, `benchmark.json`: 보완 후 새 독립 검증·성능 기록.

위 임시 파일은 재사용 가능한 코드·테스트의 저장소 경로와 구분한 시점별 증거다. 실제 브라우저·운영 데이터 백테스트·운영 DB/실제 저장·배포·원격 CI는 G03에서 검증하지 않았다. 일반 숫자형 YYYYMMDD·날짜/가격 유효성 확대·소비자의 시간대 통일·향후 pandas 버전 호환·portfolio/chart 정규화는 범위 밖이다. 현재 규칙은 [날짜 유일성 계약](../../tasks/05_strategy_backtest.md#일별-입력의-날짜-유일성-2026-10-11), 후속 작업은 [G04](../improvements/quant.md#g04)·[G08c](../improvements/quant.md#g08c)를 따른다.
