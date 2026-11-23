# QA 개선 작업

> OKF 종류: `plan` · 상태: `proposed` · 기준: 2026-10-05, main `1bd1dfa`

담당 세션은 **QA·독립 검증 체계 개선**이다. 이전 결과는 [9월 보고서](../session_reports/2026-09-13_qa.md), 현재 순서는 [작업 색인](README.md)을 따른다. QA는 기능 구현을 중복 소유하지 않고 검증 공백·환경·CI·독립 완료 판정을 맡는다.

## T06d 모의 주문 독립 검증 (2026-11-22)

[독립 회귀 8개](../../../tests/test_t06d_independent_qa.py)로 가짜 전송과 독립 SQLite 연결의 경계를 검증했다. 기존 어댑터·연결 테스트를 묶어 151개가 경고 없이 통과했다. 두 조회 응답이 엇갈려도 최신 상태·예약이 유지됐으며, 고정 입력 302개의 해시와 권한이 일치했다. 메인 최종 관련 349개와 기본 2350개가 통과했다. 실제 모의 계좌 및 운영 연결은 별도 검증 단계다. [검증 범위](../../tasks/06_trading_risk.md#t06d-kis-모의-주문과-체결-확인)

## T06c 영속 주문 독립 검증 (2026-11-21)

고정 후보에서 [독립 회귀 7개](../../../tests/test_t06c_independent_qa.py)를 수행했다. 기능 54개와 함께 61개가 경고 없이 통과했고 고정 입력 297개의 SHA와 권한이 일치했다. 전체 실행에서 발견한 화면 테스트와의 프로세스 시작 간섭은 신규 테스트의 실행부만 보완했다. 메인 통합 후보에서 관련 196개와 기본 2199개를 확인했다. [Task06](../../tasks/06_trading_risk.md#t06c-주문-원장과-결과-불명-복구)에 검증 범위와 남은 KIS 모의 연결 조건을 정리했다.

## T06b 오프라인 주문 독립 검증 (2026-11-18)

**독립 QA PASS**다. 별도 자료·공개 함수로 작성한 [독립55개](../../../tests/test_t06b_independent_qa.py)와 기존 기능79개를 새로 실행해134 passed/경고0,0.21초를 확인했다. 금액·한도·자료/시간·예약/포함근거·replay/충돌·메타데이터·UNKNOWN 계좌 격리와 공개 상태 불변성, 새 프로세스의 정상 import/검증/가상 접수와 금지 구성/I/O0을 검증했다. 초기128개 뒤6개 경계를 더했으며 제품/새 테스트 실패·제외·assertion 완화는 없었다. 도구의 완료 session 저장/보고서 조립 오류2건은 테스트·제품 실패와 구분해 원문 명세에 남겼다.

검토 입력292개는 시작/종료 SHA·권한 일치, 비소유 변경0이다. 소유권은 신규 독립 회귀1파일과 임시 보고서/명세뿐이고 제품/기존 테스트는 수정하지 않았다. 메인이 독립 파일을 통합해 최종 관련150개/경고0·문서 예제와 전체 기본2138 passed/2 deselected/기존51 warnings,111.76초를 통과시켰다. 원문 `QA-t06b-report.md`/manifest·로그/XML은 로컬 임시 `invest-bot-t06b-sgr6jt0k`에 있다. 이 승인은 유지한 단일 브로커의 순차 메모리 범위이며 실제 KIS/인증·체결·영속/재시작·다중 프로세스·대용량 성능/권한 경계는 검증하지 않았다. 신규 ID 정책/시장 version의 불변성은 신뢰된 구성 책임이다. QA는 종료/idle이며 기존 QA01~QA04·T06a 설계 승인은 유지한다.

## Task06 설계 검토 (2026-11-17)

[T06a 설계](../../tasks/06_trading_risk.md)의 독립 문서 검토를 퀀트 자문·메인 보완 후 완료했다. 설계 SHA `3c65bb5bda566367c5e92d65680a12d8747cbd3b3d9a561f2f3d949c3901b437`의 계약·선행 관계·V01~V15 검증 가능성을 확인해 APPROVE·차단 지적0개로 판정했다. 검토 후보286입력 SHA/권한을 시작/종료에 보존했고 문서 외 변경0개다. 구현·테스트·외부 규격 조회/API/DB·서비스는 수행하지 않았으며 V01~V15는 미래 요구다. T06b의 타입/사유·경계 연산, T06c의 저장/전이/crash 세부 구현은 후속이다. 메인의 최종 문서/HTML 정합성은 별도이며 원문 보고서/명세는 로컬 임시 `invest-bot-task06-plan-t_b22bvl`에 있다. QA01~QA04 완료는 유지한다.

2026-11-16 main `b34219f`의 [원격 run `43776628811`](https://github.com/dydwnsekd/invest_bot/actions/runs/43776628811)는 전체 성공이다. 같은 SHA의 실제 로그에서 기본2004개와 PostgreSQL2개 통과를 확인해 QA04를 완료했다. 직전 실패는 G06c 계측 수정이 빠진 `b7d869c`의 결과로 분리해 남겼다. 오늘은 코드 변경 없이 기존 QA 하나에서 저장 증거를 검토하고 메인이 완료 기록·공유 문서·HTML만 갱신한다. 이번 문서 변경은 커밋 전이며 아래 날짜별 원격 대기/미실행 표시는 당시 기록이다. 상세는 [QA04](#qa04)를 따른다.

2026-11-15 현재 기준은 main `c86b0f6` + QA04 후속 검토 작업본이다. 최초 임시 경로 수정은 `e89c1d2`, 관련 문서는 `c86b0f6`으로 반영됐다. 같은 SHA의 [기본 CI](https://github.com/dydwnsekd/invest_bot/actions/runs/43589614419/job/132431351332)에서 기존27개 경로 실패는 해소됐으나 신규3개의 SQL 계측 누락이 남았다. 기존 QA 세션 하나를 재사용해 URL 표시 문자열과 실제 DB 식별을 분리했고, 메인이 네트워크가 차단된 Linux에서 동일3실패를 재현한 뒤 관련·전체 Linux/Mac 검증을 수행했다. 수정 후 원격 CI는 미실행이다. 현재 상세는 [QA04](#qa04)를 따르며 아래 날짜별 커밋 전/미실행 표시는 당시 기록이다.

2026-11-13 현재 기준은 main `7b42920` + QA04 검토 작업본이다. G08d 코드는 `7b42920`, G06c 문서는 `ef5337e`로 반영됐다. G01a·QA01은 동일 main의 [원격 PostgreSQL 검사](https://github.com/dydwnsekd/invest_bot/actions/runs/43046475982/job/130611635459)2 passed /2 warnings,1.13초와 아래 임시 DB 재검증으로 완료했다. 전체 원격 run의 기본 suite 실패는 별도 QA04로 분리했다. QA04의 신규4개·관련35개와 메인 기본1998개는 로컬 후보의 결과이며, 수정 후 원격 CI 재실행은 미수행이다. 기존 역할 하나만 재사용했고 메인이 공유 문서·원본 통합·임시 DB·GitHub/CUA·최종 검증을 소유했다. 아래 날짜별 대기/커밋 전 표시는 당시 기록이다.

2026-11-10 G08d 독립 검증 완료·커밋 전: 최신283입력을 보존하고 신규 [독립 회귀](../../../tests/test_g08d_independent_qa.py)만 추가했다. 독립12개·관련315개, 메인 최종284입력 기본1994 passed / 2 deselected / 51 warnings, 120.41초다. 데이터/출처/조회·명시 실행 경계와 실제 배치 수행 주체/한계는 [Task04](../../tasks/04_dashboard.md#자동-반응형-차트-2026-11-10)를 따른다. QA01 원격 CI는 대기를 유지하고 공유 문서는 메인 소유다.

2026-11-09 G06c 독립 검증 완료·커밋 전: 기존 대시보드 구현·메인 실제 전후 화면/모바일 보완 종료 후 최신281입력을 고정하고 신규 [독립 회귀](../../../tests/test_g06c_independent_qa.py)만 추가했다. 독립10개·관련390개로 지정 모의 범위를 승인했고 메인 최종282입력 기본1947 passed / 2 deselected / 51 warnings, 106.09초도 통과했다. 수행 주체·실패 분류·조회 예산·실제 화면과 검증 한계는 [Task04](../../tasks/04_dashboard.md#헤더카드필터-배치-2026-11-09)를 따른다. QA01 원격 CI 대기는 유지하며 제품/기존 테스트/공유 문서는 QA 소유가 아니다.

2026-11-08 QA03 완료·커밋 전: 최신278입력의 기존412개는 통과했으나 독립3pass/2fail로 구형 []/null 조합 설정의 전체 renderer 중단(QA03-01)을 확인했다. 메인 제안을 독립 재현한 것이며 초기 report/manifest/RED를 보존하고 제품을 수정하지 않았다. 메인 reader 연결 보완·417GREEN·모바일 재검사 후 같은 QA가 나머지 왕복 검증을 완료했다. 최종 독립19개·관련431개로 지정 synthetic 범위를 승인했고 메인279입력 후보 기본1921 passed / 2 deselected / 47 warnings, 91.49초도 통과했다. [현재 계약·명령·단계별 검증과 한계](../../tasks/05_strategy_backtest.md#조합-설정-저장재로드-2026-11-08)를 따른다.

실제 UI 생성 조합의 CSV/SQLite 저장→새 service/history를 통해 당시 설정·방식/가중치·입력 출처·G08b 범위·거래/성과를 대조했다. 조회/명시 저장 경계·충돌/사전 오류·부분 실패·legacy도 확인했다. 메인의 실제 화면/기하/호출 수와 QA 독립 실행의 수행 주체를 구분하며 QA는 최종 정상/손상 모바일 캡처2장을 직접 검토했으며 브라우저 조작·기하/호출수 실측은 메인 증거다. 다중파일 원자성·동시 외부 writer/자동 rollback·원본 snapshot/곡선 재구성·운영 API/DB·배포·원격 CI·전체 접근성/대규모 성능을 승인한 결과는 아니다. 최종 보고서는 QA03-final-report/manifest이며 full default는 메인이 실행했다. 기존 QA01은 검증 대기를 유지한다.

2026-11-05 G08b 독립 검증 완료: 기존 대시보드·메인 UI 보완 종료 후274입력의 동일 source를 보존하고 신규 [독립20개](../../../tests/test_g08b_independent_qa.py)를 추가했다. 첫 지정 범위 관련286 passed / 기존15 warnings, 2.11초로 지정 모의 범위를 승인했다. 실제 adapter/runner/조합/renderer/history와 임시 CSV/SQLite의9필드 왕복·선택 변경 후 고정·legacy·부분 기록·로컬 날짜·기존8SELECT와 추가 SQL/쓰기/runner0을 검증했다. 초기3차례 실패는 QA 호출·기대값·assertion 작성 오류로 구분해 보존했고 제품/기존 테스트를 수정하거나 실패를 제외하지 않았다. 조합 공통 시작일을 강화한 최종 결과는 QA-confirmed-final.*이며 이전 시도와 합산하지 않는다.

메인의1920×958·390×844 실제 가상 앱 관찰과 수행 주체를 구분한다. QA는 제공된 준비/조합 캡처2장을 직접 열어 줄바꿈을 검토했으나 브라우저를 조작하거나 기하/호출수를 직접 측정한 것은 아니다. 메인은 최종275입력 후보 기본1872 passed / 2 deselected / 36 warnings, 92.20초를 통과했다. [계약·명령·실패/보완·한계](../../tasks/05_strategy_backtest.md#백테스트-입력-범위-2026-11-05)를 따른다. 제품 자동 저장·G08c artifact·QA03·원격 CI·실제 API/운영 데이터·전체 UX/대용량 CPU 성능을 승인한 결과가 아니다. 전체 검증에서 발견한 G03 fake caption 누락은 별도 한 줄 소유권으로 보완했다. 해당1개 RED와 G03 전체63개를 포함한349 passed / 기존21 warnings를 새 QA-G03-followup.* 증거로 남겼으며 제품·기존 차단 assertions는 유지했다. QA와 대시보드 역할은 완료 후 idle이며 공유 문서는 메인이 소유한다.

2026-11-02 G08a 독립 검증 완료·11월3일 메인 통합: 최종 독립82개·관련801 passed로 지정 synthetic 범위를 승인했다. 메인 최종272입력 후보도 기본1819 passed / 2 deselected / 36 warnings다. 초기665개 통과 이후 calendar/listing 판정 승격을 CSV/SQLite의2개로 발견했다(신규4 passed / 2 failed). 데이터 조건 보완 후 확장68개에서 숫자 날짜의 epoch 해석2개가 남은739 passed / 2 failed를 보존했다. 메인이 기존 scalar 날짜 규칙을 재사용하고 own21개를 추가한 뒤, 같은271입력과 새 실행으로 두 결함의 해소를 확인했다. QA가 제품/기존 테스트/공유 문서를 수정하거나 실패를 제외하지 않았으며 초기 주입 오류도 별도로 기록했다. [독립 회귀](../../../tests/test_g08a_independent_qa.py)·[정책·명령·한계](../../tasks/02_data_collection.md#일반-일봉-요청-범위-2026-11-02)를 따른다. 승인 보고서·최종XML 저장 후 마지막 응답 전 사용량 제한으로 종료돼 미작성된 최종 audit/manifest는 메인의 별도 SHA/모드 확인으로 보완했다. 초기 RED manifest를 승인 증거로 재사용하지 않았다. 실제 설정/API/토큰·운영 DB/PG·브라우저·서비스·commit·push는 사용하지 않았고 QA01~03 상태는 유지한다. 아래 날짜별 결과는 당시 기록이다.

2026-10-31 G07b 독립 검증 완료: 기존 운영 종료 후 새 추적 파일 격리본에서 실제 shell/helper·전역 deadline·HTTP·안정 관찰·공개/내부 포트를 검증했다. 독립160개·합산341 passed로 지정 모의 범위를 승인했고 메인 최종 후보 기본1593 passed / 2 deselected / 36 warnings도 통과했다. 기존266입력과 운영 소유6파일을 보존하며 QA 회귀만 추가했다. 실제 Docker·DB/API·host 접속·서비스·commit·push는 사용하지 않았으며 QA01~03 상태는 유지한다. [현재 정책·증거](../../tasks/07_operations_docs.md#시작-후-준비-확인-2026-10-31). 아래 날짜별 결과는 당시 기록이다.

2026-10-29 G07a 독립 검증 완료: 기존 운영 종료 후 새 추적 파일 격리본에서 실제 runner·CLI·JSONL 상태와 오류 경계를 검증했다. 신규68개·합산347 passed로 지정 범위를 승인했고 메인 최종 후보 기본1322 passed / 2 deselected / 36 warnings도 통과했다. 입력263개와 제품/기능 소유 테스트를 보존했다. 실제 설정·API/DB·Docker·서비스·commit·push는 사용하지 않았으며 QA01~03 상태는 유지한다. [정책·검증 기록](../../tasks/07_operations_docs.md#스케줄러-실패-후-대기-2026-10-29). 아래 날짜별 결과는 당시 기록이다.

2026-10-27 현재 G01b의 독립40개·합산281개 검증을 완료했고 메인의 기본1100개도 통과했다. [G01b 정책·단계별 증거](../../tasks/02_data_collection.md#snapshot-기준일-날짜-계약-2026-10-27)를 따르며 QA01 원격 CI·QA03 상태는 바꾸지 않았다. 다음 날짜별 검증은 당시 기록이다.

2026-10-23 QA02 지정 범위는 완료다. 독립290개와 메인의 기본1001개·실제 브라우저 관찰을 연결한 최종 판정은 아래 QA02·실행 기록을 따른다. 다음 날짜별 부분 검증의 미완료 표시는 당시 상태이며 QA01 원격 CI·QA03은 별도 대기다.

G02 기능에 연결한 10월 10일 독립 검증도 수행했다. 아래 QA01~03과 별도로 기존 QA 세션을 재사용했고, G02 상태와 완료 조건은 [운영 역할 문서](operations.md#g02)에서 관리한다.

G03에 연결한 10월 11일 독립 검증은 혼합 Timestamp 판정 결함을 발견한 뒤 보완 코드의 재검증까지 마쳤다. G03 상태와 입력 계약은 [퀀트 역할 문서](quant.md#g03)에서 관리하며 QA01~03의 상태를 바꾸는 결과는 아니다.

G04에 연결한 10월 12일 독립 검증을 완료했다. 담당 구현 종료 후 메인의 UI 연결까지 포함한 기능8파일 해시가 시작·종료에 일치하고 관련339개(기존265 + 독립74)를 새로 통과했다. QA 종료 뒤 메인의 원본 통합 관련339개·기본780개도 통과했다. G04 상태는 [퀀트 역할 문서](quant.md#g04), 증거는 [검증 기록](../session_reports/2026-10-12_saved_signal_alignment.md)에서 관리하며 QA01~03은 재개하지 않았다.

G05a에 연결한 10월 13일 기존 QA 세션은 초기 확인 뒤 사용량 제한으로 중단돼 독립 완료 판정이 없다. 추가 크레딧·세션 없이 메인이 경계10개·실제 앱 검증을 이어갔다. 관련199개·원본 기본832개를 통과했으며 [G05a 검증 기록](../../tasks/04_dashboard.md#차트-summary-수급-연결-2026-10-13)에 수행 주체와 미검증 범위를 구분했다. QA02 전체 완료로 해석하지 않는다.

G05b는 2026-10-18 메인이 실제 renderer·상태 계산·선택 복원과 가상 데이터 브라우저를 검증했다. 기존 대시보드 하위 에이전트의 읽기 전용 리뷰에 차단 결함은 없었으나 별도 QA 세션의 종합 판정은 아니다. 관련220개·최종 격리 후보 기본918개가 통과했으며 아래 QA01~03 상태는 유지한다. [G05b 계약·증거](../../tasks/04_dashboard.md#원본판단-기준일과-다음-행동-2026-10-18).

G06a는 2026-10-19 메인이 실제 실행 renderer의 사전 안내와 선택/기간/설정 변경 작업0회, 5개 버튼의 명시 클릭·수집 부분 실패·전송 skipped/failed를 검증했다. 신규20개를 포함한 관련169개와 최종 격리 후보 기본938개가 통과했다. 실제 전달은 하지 않았으며 별도 독립 판정과 G06b 대비·포커스는 남아 있다. [G06a 검증 기록](../../tasks/04_dashboard.md#생성전송-범위-안내-2026-10-19).

G06b는 2026-10-22 메인이 가상 데이터 실제 renderer의 상태 대비·보조 라벨 크기·키보드 포커스·아이콘을 확인했다. 관련202개·최종 격리 후보 기본970개가 통과했고 기존 대시보드 하위 에이전트 읽기 전용 리뷰에 차단 결함은 없었다. 연결된 네 기능의 메인 검증을 마쳤으며 QA02의 별도 독립 종합 판정은 남아 있으므로 상태는 대기다. [G06b 검증 기록](../../tasks/04_dashboard.md#상태-텍스트-대비와-라벨-크기-2026-10-22).

2026-10-17 지식 갱신에서 최근 기능별 커밋과 [검증 범위](../../tasks/00_summary.md#현재-상태-2026-10-17)를 대조했다. 보충 수집·비교·슬라이딩 연구의 테스트와 HTML 생성 검사는 QA02의 화면 종합 판정이나 QA03의 실제 대시보드 조합 artifact 왕복을 대신하지 않는다. 원격 CI와 별도 독립 판정을 새로 수행하지 않았으므로 아래 QA01~03 상태는 유지한다.

| ID | 우선순위 | 작업 | 상태 |
| --- | --- | --- | --- |
| QA01 | P1 | SQLite·PostgreSQL 최신 정렬과 CI | 완료 (2026-11-13 원격 실행 확인) |
| QA02 | P1 | 실제 renderer 호출 경계·조회·브라우저 | 완료 (main 반영: `6607de7`·`09bfcd7`) |
| QA03 | P2 | 실제 조합 artifact 저장·재로드 | 완료·main 반영 |
| QA04 | P1 | CI 임시 경로·SQL 계측 호환성 | 완료 (main `b34219f` 원격 기본2004개·PostgreSQL2개;2026-11-16 확인) |

<a id="qa01"></a>
## QA01 — SQLite·PostgreSQL 최신 정렬과 CI

- **우선순위:** P1 · **상태:** 완료 (2026-11-13, 원격 실행 확인) · **연결:** [G01a](data.md#g01a)의 완료 판정 전. fixture·기대값은 수정 전 준비할 수 있다.
- **근거:** 10월 5일 검토 당시 [PostgreSQL 테스트:24](../../../tests/integration/test_postgresql_migrations.py)는 migration·테이블·revision만 검사하고 [CI:52](../../../.github/workflows/tests.yml)도 이 파일만 선택한다. [SQLite 회귀](../../../tests/test_dataset_frame_list_latest_batch.py)는 같은 종목의 dated/NULL 경쟁을 다루지 않는다. 따라서 기존 CI 성공은 운영에서 확인한 정렬 결함의 수정 증거가 아니다.
- **작업:** 데이터 담당의 repository 회귀와 격리 PostgreSQL 환경·CI 실행을 연결한다. 기능 테스트 파일의 소유권은 데이터 담당에게 두고 QA의 통합 파일·workflow는 QA가 담당한다.
- **완료 조건:** 같은 fixture로 세 조회 메서드의 dated/NULL·동률 id·NULL fallback 기대값을 양쪽 DB에서 검증한다. PostgreSQL CI가 해당 테스트를 실제 실행한 결과가 있다. 실행하지 못한 DB는 미검증으로 남긴다.
- **증거:** HEAD/작업 트리·임시 DB 종류·선택한 테스트·명령·결과·운영 DB 미사용을 기록한다. skip/xfail로 실패를 숨기지 않는다.

- **완료 근거 (2026-11-13):** 현재 local/main과 remote/main의 SHA가 `7b4292048ecccb8c0652cdf6229c9c22c649db25`로 일치한다. run `43046475982`의 [PostgreSQL job `130611635459`](https://github.com/dydwnsekd/invest_bot/actions/runs/43046475982/job/130611635459)에서 `python scripts/run_tests.py --suite postgresql tests/integration -q`가 실제 실행돼 **2 passed /2 warnings,1.13초**였고 종료 코드0·job success·컨테이너 정리 단계 success를 확인했다. 실행일은2026-11-12 00:15경 KST이며11월13일 조회했다. GitHub 공개 API는 job/step 결과를, 로그인된 기존 Chrome의 읽기 전용 화면은 실제 로그 수치를 증명했다. CLI 미인증·공개 로그 다운로드 API403을 우회 인증이나 토큰 생성으로 해결하지 않았다.
- **독립 임시 DB 재검증:** main284추적 입력만 복사하고 설치된 PostgreSQL17.10 이미지로 별도 이름·임의 loopback 포트·tmpfs를 사용했다. host bind/영속 volume·운영 설정/DB 없이 기존 migration/정렬2개를 실행해 **2 passed /2 warnings,1.44초**였고 컨테이너 삭제를 확인했다. DB 이름 `_test`, 정렬용 UUID schema 생성·정리, 기존 SQLite/PG 공통 기대값을 유지한다. 최초 wrapper는 Docker의 tmpfs 표시 위치를 잘못 가정한 사전검사에서 중단됐고 DB를 정리했다. HostConfig.Tmpfs와 빈 Mounts/Binds를 함께 확인하도록 task-local 검사만 보완했으며 첫 실패를 보존했다. 제품/기존 PG 테스트를 바꾼 결과가 아니다. 두 경고는 기존 Alembic path_separator deprecation이다.
- **경계:** 같은 run의 [기본 suite](https://github.com/dydwnsekd/invest_bot/actions/runs/43046475982/job/130611636031)는27 failed /1967 passed /2 deselected /111 warnings,181.35초였다. 따라서 PostgreSQL 통과를 전체 Actions 성공으로 표현하지 않는다. 원인은 아래 QA04의 테스트 fixture 경로이며 Node/Ubuntu 이동 안내는 원인으로 확정하지 않는다. 운영 데이터·실제 API/키·배포·프로젝트 서비스·원격 재실행·commit/push는 수행하지 않았다. 원문 API/DOM/log/XML과 보호 SHA는 로컬 임시 `invest-bot-qa01-pg-59z1vjsi`에 보존한다.

<a id="qa02"></a>
## QA02 — 실제 renderer 호출 경계·조회·브라우저

- **우선순위:** P1 · **상태:** 완료 (2026-10-23, 지정 범위) · **연결:** [G05a·G05b·G06a·G06b](dashboard.md)의 해당 수정마다 확인.
- **착수 (2026-10-23):** main `036def2`의 추적 파일만 임시 디렉터리에 복사하고 기존 QA 세션을 재사용한다. G06b 코드 `dee88af`·문서 `036def2` 반영을 확인했다. 독립 통합 fixture·조회/호출 경계 검증을 먼저 수행하고 같은 fixture의 실제 브라우저 관찰과 연결한다. 실제 설정·운영 데이터·API·전송·서비스 제어는 사용하지 않으며 commit·push는 수행하지 않는다.
- **근거:** [홈 테스트:3387](../../../tests/test_streamlit_dashboard.py)는 실제 renderer를 교체하고 [AppTest:2988](../../../tests/test_streamlit_dashboard.py)는 차트 loader를 교체한다. [차트 테스트](../../../tests/test_dashboard_snapshot_frame_loader.py)는 summary만 유효한 운영 형태를 다루지 않는다. [조회 회귀:51](../../../tests/test_watchlist_snapshot_queries.py)는 snapshot 생성 후 추가0회만 증명한다.
- **작업:** 실제 홈·리포트·관심종목 renderer를 사용하는 summary-only fixture와 수집·분석·리포트 생성·Discord 경계 spy를 연결한다. 계산·생성 함수는 mock하되 화면 조립은 검증 대상에서 제거하지 않는다. 역할 소유 테스트의 추가는 대시보드 담당과 조정한다.
- **완료 조건:** 검색·선택·탭 왕복에서 실행/전송0회, 실제 관측일 수급 연결, 상태 날짜 구분을 검증한다. 전체 rerun과 snapshot 이후 조회를 별도로 측정하고 후자의 추가 SELECT0회를 유지한다. G06a 클릭 mock의 기존 호출·부분 실패도 확인한다.
- **브라우저 판정:** 대비·390px 겹침·포커스는 AppTest 성공으로 대체하지 않는다. 같은 fixture의 1920×958·390×844 화면을 실제 브라우저에서 확인하고 캡처·관찰을 기록한다.
- **최종 판정 (2026-10-23):** 기존 QA 세션의 독립31개·합산290개 GREEN과 메인의 같은 통합 앱 브라우저 관찰 기록 검토로 지정 범위를 승인했다. 고립 관측값 가시성의 보완 전 실패·보완 후 결과, 전체 기본1001개와 미검증 범위는 아래 실행 기록에 남긴다. 다음 날짜별 부분 증거의 대기 표시는 당시 상태다.
- **G05a 부분 증거 (2026-10-13):** 메인이 실제 리포트·관심종목·데이터 보기 renderer와 Plotly를 사용한 가상 앱에서 summary 수급·누락/날짜 불일치 안내, 검색·선택·탭 왕복의 실행/전송0회·chart 추가 SELECT0회를 확인했다. 리포트/관심종목 전체 SELECT3(snapshot2 + 기존 즐겨찾기1), 데이터 보기2(snapshot2)다. 390px 안내는 줄바꿈되고 수급 panel은 표시되지만 기존 범례/제목 겹침은 G08d 범위다. 별도 QA 세션 최종 판정·G05b 상태 날짜·G06 클릭/대비·포커스의 종합 판정은 남아 있으므로 상태는 대기다.
- **G05b 부분 증거 (2026-10-18):** 실제 renderer 3화면×4상태에서 원본10/02·판단10/01, 원본 누락, 미래 판단일, 최신 상태를 확인했다. 검색·선택·탭 왕복과 분석 갱신 버튼의 화면 이동은 실행·전송0회다. 실제 임시 SQLite snapshot 이후 홈·리포트·관심종목의 상태 계산 추가 SELECT0회를 확인했으며 전체 rerun의 조회0회를 주장하지 않는다. 가상 앱 1920×958·390×844에서 날짜·사유 표시와 줄바꿈을 관찰했다. G06a 클릭·부분 실패, G06b 대비·포커스와 별도 QA 종합 판정은 남아 있어 QA02는 대기다.
- **G06a 부분 증거 (2026-10-19):** 실제 renderer AppTest와 가상 브라우저에서 클릭 전 대상·단계·Discord 설정을 확인했다. 선택·기간·설정 변경 작업0회, 빈 선택의5개 버튼 작업0회, 정상 클릭의 기존 호출 순서·대상·전송 요청, 수집 부분/전체 실패와 전송 skipped/failed 경고를 검증했다. 390px에서 설명 줄바꿈과 페이지 가로 넘침 없음을 확인했지만 G06b 대비·포커스의 종합 판정은 아니다. 실제 Discord 전달·운영 DB/API·배포·원격 CI와 별도 QA 종합 판정은 미검증이다. QA02 전체는 대기를 유지한다.
- **G06b 부분 증거 (2026-10-22):** 실제 리포트 카드·관심종목 상태·해석 renderer의1920×958·390×844를 확인했다. 합성 배경 대비 하한은 전략 상태 최저9.13, 종합 배지 최저7.45이며 보조 라벨은0.8rem 이상이다. 기본 버튼 일반/포커스와 사이드바 글자도 대비4.5:1을 넘고 버튼·입력의 키보드 포커스를 확인했다. 완료 아이콘 `check` 노출을 수정한 뒤 Material font·ligature와 체크/펼침 glyph를 확인했다. 측정은 지정 가상 표본에 한정하며 전체 앱 접근성 인증이나 별도 독립 판정은 아니다. 남은 독립 종합 검증에서 기존 G05a·G05b·G06a 경계와 함께 확인한다.

<a id="qa03"></a>
## QA03 — 실제 조합 artifact 저장·재로드

- **우선순위:** P2 · **상태:** 완료·main 반영 (코드 `8b902e6`·문서 `7c305c6`; 2026-11-08 검증) · **연결:** [G08c](quant.md#g08c)의 완료 판정 전, G03·G04 완료 이후.
- **근거:** [사용자 설정 테스트:448](../../../tests/test_streamlit_backtest.py)는 단일 RSI의 메모리 결과, [이력 테스트:679](../../../tests/test_streamlit_backtest.py)는 수작업한 단일 전략 fixture를 사용한다. 실제 조합 출력→저장→재로드로 설정과 성과 보존을 증명하지 않는다.
- **작업:** RSI40/60을 포함한 실제 조합 출력을 임시 artifact에 저장하고 새 service에서 재로드하는 왕복 회귀를 기능 담당과 연결한다. 운영 artifact를 덮어쓰지 않는다.
- **완료 조건:** 구성 전략 설정·방식·가중치·입력 provenance·거래·최종자산·MDD를 저장 전후 비교한다. 중복 날짜는 G03 정책을 적용하고, 기존 artifact의 호환/미지원 정책도 확인한다.
- **검증 경로:** [persistence 회귀](../../../tests/test_backtest_persistence.py), [조합](../../../tests/test_backtest_combination.py), [대시보드 백테스트](../../../tests/test_streamlit_backtest.py). 실제 생성 결과를 사용했는지 명시한다.

<a id="qa04"></a>
## QA04 — CI 임시 경로 OS 호환성

- **우선순위:** P1 · **상태:** 완료 (2026-11-16 원격 검증 확인) · **선행:** 최초 경로 보완 `e89c1d2` 및 두 observer의 URL 계측 보완이 main `b34219f`에 반영됨.

### 원격 완료 확인 (2026-11-16)

- **대상·전체 판정:** 로컬 main과 원격 run의 SHA는 `b34219faf276e586a4d10b34d968fde8ab399d76`으로 같다. [run `43776628811`](https://github.com/dydwnsekd/invest_bot/actions/runs/43776628811)는 `completed/success`이며 KST11월16일08:46:37에 생성되고08:51:23에 마지막 갱신됐다. 두 job 모두 성공이다. 메인이 읽기 전용 GitHub 메타데이터와 실제 Chrome 로그 화면을 확인했으며 재실행 버튼은 사용하지 않았다.
- **기본 suite:** [pytest job `133004256370`](https://github.com/dydwnsekd/invest_bot/actions/runs/43776628811/job/133004256370)의 `python scripts/run_tests.py --suite default -q`는 **2004 passed / 2 deselected / 111 warnings, 248.27초**, 종료 코드0이다. 실제 Python3.13.18 로그이며 이전 Mac/Linux 로컬 수치와 구분한다. `external_network`·`postgresql` 제외는 기존 기본 suite 선택이다.
- **PostgreSQL suite:** [postgresql-migrations job `133004256238`](https://github.com/dydwnsekd/invest_bot/actions/runs/43776628811/job/133004256238)의 `python scripts/run_tests.py --suite postgresql tests/integration -q`는 **2 passed / 2 warnings, 0.89초**, 종료 코드0이다. 경고는 Alembic의 기존 `path_separator` 안내다. 기본 suite와 별도 job이며 모든 suite의 무경고를 뜻하지 않는다.
- **직전 실패와 커밋 범위:** [run `43706452912`의 기본 job](https://github.com/dydwnsekd/invest_bot/actions/runs/43706452912/job/132788482128)은 `b7d869c2b8e109738354f2bb031e860fa2c47cc8`에서 **4 failed / 2000 passed / 2 deselected / 111 warnings, 145.50초**였다. 실패는 G06c의 같은 DB SELECT 관측, 실제 INSERT/UPDATE 차단2개, 실제 main SELECT 예산이다. `git diff b7d869c b34219f -- tests/g06c_layout_fixture.py`로 첫 커밋에는 파생 observer의 `make_url`/URL 비교 보완이 없고 다음 커밋에 포함됐음을 확인했다. 제목이 문서 반영인 최신 커밋에도 이 테스트 fixture 수정이 들어 있다. 앞선 실패는 검증된3파일 중 하나가 빠진 소스에 해당하며 불안정한 재실행으로 설명하지 않는다.
- **완료 조건·독립 판정:** 두 observer와 신규 SQL 회귀3파일은11월15일 전체 검증된 최종 파일과 SHA가 일치한다. 경로/TMPDIR 우선순위·실제 SQLite 조회/쓰기 차단·기존 assertions를 유지한 상태로 새 SHA의 Ubuntu 기본 suite 성공이 확인됐으므로 QA04를 완료한다. 기존 QA 하나도 고정286입력의 SHA/권한과 메인이 저장한 CI 증거를 대조해 지정 완료 조건 충족으로 판정했다. QA는 외부 조회나 브라우저/테스트를 재실행하지 않았고 역사적 커밋 diff는 메인 확인 근거로 구분했다. 메인이 원본 문서·HTML·정합성을 소유했으며 오늘은 코드/의존성 변경이나 전체 테스트 재실행을 하지 않았다.
- **문서 검증:** Markdown58개·로컬 링크884개·등록ID58개·개념14개/관계18개에서 오류0, HTML12페이지·11섹션·문서58행·고유ID43개·로컬 참조110개·기존7앵커와 외부 자원0개를 확인했다. 기존 Node 모의 DOM의 탐색·검색/목록 분할·이력·인쇄/복원·복사19개가 통과했고 JavaScript는 기준본과 같다. HTML 실제 브라우저 배치는 기존 로컬 파일 접근 제한으로 검사하지 않았다. 오늘 새로 수행한 GitHub 로그 화면 확인과 구분한다.
- **경계·보존:** CI 성공은 실제 KIS 인증/주문·운영 DB/데이터·배포·서비스 재시작·대용량 성능 검증을 뜻하지 않는다. 실제 설정/backup/index/HEAD/branch/모드와 baseline286입력을 보존하고, 이번 공유 문서9개는 커밋 전이다. stage/commit/push·원격 job 재실행은 하지 않았다. 원문 메타데이터·화면 로그·입력 SHA와 판정은 로컬 임시 `invest-bot-qa04-close-g22g6aft`에 보존한다. 아래11월15일·13일의 미커밋/원격 대기는 각 날짜 당시 상태다.

### URL 표시·SQL 계측 후속 (2026-11-15)

- **현재 증거:** main `c86b0f6`과 일치하는 [run `43589614419`/job `132431351332`](https://github.com/dydwnsekd/invest_bot/actions/runs/43589614419/job/132431351332)는 **3 failed /1995 passed /2 deselected /111 warnings,241.80초**였다. 실패는 QA04의 TMPDIR-reset-cache, configured-cache, actual-app 세 사례에서 기대한 snapshot/SELECT2회가0회로 집계된 것이다. 원래27개 부모 디렉터리 실패와 구분한다. 메인의 로그인된 기존 Chrome 읽기 전용 화면에서 실제 로그를 확인했으며 원격 job 재실행/설정·계정 변경은 하지 않았다.
- **재현·원인:** 설치된 캐시 이미지를 네트워크 없이 실행한 Linux에서 수정 전 **3 failed /1 passed,1.11초**를 재현했다. 임시 폴더·SQLite·원본 값은 생성됐지만 `str(conn.engine.url)`과 원문 DB URL의 비교가 공백/한글 경로를 동일 DB로 식별하지 못했다. [SQLAlchemy2.1 공식 변경](https://docs.sqlalchemy.org/en/21/changelog/migration_21.html#url-stringify-and-parse-now-supports-url-escaping-for-the-database-portion)은 database 부분의 URL 문자열 escaping을 설명한다. 실제 로컬은 SQLAlchemy2.0.50, 사용한 Linux 이미지는2.1.4이며 OS 자체만의 차이로 단정하지 않는다.
- **최소 수정:** 기존 QA02와 파생 G06c의 계측/쓰기 차단에서 표시 문자열 대신 공개 `make_url`/`URL` 연결 정보로 같은 DB를 판별한다. 실제 데이터·서비스·loader·seed·snapshot2/frame0·SQL 분류와 G06c 쓰기 차단 의미는 유지한다. 제품 source/의존성·버전 pin·운영 설정/DB는 변경하지 않았다.
- **회귀·역할 검증:** 기존 QA는 두 fixture와 신규 [SQL 관측 회귀](../../../tests/test_qa04_sql_observation.py)만 소유했다. macOS에서 URL의 표시 전용 escaping만 제어한 신규6개가 수정 전 모두 실패했다. 실제 조회 계측4개와 실제 INSERT/UPDATE 차단2개의 누락이며, 두 observer만 보완한 뒤 기존 관련 assertions를 유지해 통과했다. 신규 테스트 작성 오류나 실패 제외는 없었다. 최종 신규6개를 포함한 관련50개가 통과했다. 실제 SQLite·Engine 이벤트/loader 또는 AppTest를 사용하고 표시 전용 차이만 제어하며, 소비자/결과를 성공 fake로 바꾸지 않았다. 다른 DB의 쿼리 제외, 같은 DB 실제 조회, G06c 쓰기 차단을 검증했다. 기존 경로4개/QA02·G06c·G08d assertions는 완화하지 않았다.
- **메인 Linux 검증:** 같은 캐시 이미지/격리 조건에서 관련50개가 통과한 뒤, 최종286입력의 전체 기본 **2004 passed / 2 deselected / 111 warnings, 170.13초**를 확인했다. Linux7/linuxkit ARM64·Python3.13.16·SQLAlchemy2.1.4·Streamlit1.65.0·Plotly6.9.0 환경이며 GitHub Ubuntu/Python3.13.18과 완전히 동일한 환경은 아니다. 기존 이미지에 설치된 라이브러리만 사용했고 네트워크 none·read-only root/source·tmpfs tmp/task/app·작업별 결과 폴더만 허용했다. 앱 entrypoint를 실행하지 않고 소유 임시 컨테이너를 정리했다. 첫 전체의169 failed/1835 passed(55.10초)와 두 번째63 failed/1941 passed(54.08초)는 task-local runner의 산출물 읽기 전용·표준 Python 경로·임시 스크립트 실행권한 조건에서 발생했다. 원문을 보존하고 .tmp 전용 writable tmpfs, 기존 interpreter launcher, 임시 fakes의 exec 조건만 보정했다. 대표 준비 확인2개가 통과한 뒤 동일한 source/선택의 최종 전체가 통과했다. 실제 테스트나 제품 assertions를 바꾸거나 실패를 제외하지 않았다.
- **메인 Mac 검증:** SQLAlchemy2.0.50·Streamlit1.58.0·Plotly6.8.0의 기존 venv, env-i·task-local TMPDIR/cache/basetemp/XML/log·-B에서 전체 기본 **2004 passed / 2 deselected / 51 warnings, 110.39초**를 확인했다. 두 환경의 수치는 별도 검증이며 합산하지 않는다. 전체 통과 후 Python SHA는 고정하고 공유 문서만 갱신했다.
- **완료 조건·경계:** 로컬 source/회귀는 검증됐지만 변경은 미커밋이다. 새 SHA가 반영된 GitHub 기본 suite 성공은 아직 미검증이므로 QA04의 원격 완료는 대기다. 기존 QA 격리본의 비소유283입력·기존 assertions, 메인의 비소유 source·실제 설정/backup/index/HEAD/branch/모드·불변 baseline285개를 확인했다. AST/메모리 compile·공백·MD 링크/ID·HTML12페이지/문서58개·Node 탐색19개로 문서를 검사한다. 린트/타입 검사 도구를 새로 설치하지 않았고 수행했다고 표현하지 않는다. 실제 API/키·운영 데이터/DB·프로젝트 서비스·stage/commit/push·원격 재실행은 사용하지 않았다. 원문 DOM/로그/XML·버전·SHA와 초기 RED는 로컬 임시 `invest-bot-qa04-followup-m7_zy3sk`에 보존한다.

### 최초 임시 경로 보완 기록 (2026-11-13)

- **실제 결함:** main `7b42920`의 [기본 CI](https://github.com/dydwnsekd/invest_bot/actions/runs/43046475982/job/130611636031)27실패 로그는 Ubuntu에서 `/private/tmp/qa02-synthetic-*`를 찾지 못했다. [QA02 fixture](../../../tests/qa02_dashboard_fixture.py)의 기본 directory가 macOS 경로를 고정했다. 기존31개 중 실제 AppTest 경로27개가 이 초기화 실패로 중단됐다.
- **작업·결과:** 고정된 `dir` 인자를 제거해 Python 표준 `tempfile`의 시스템/설정된 임시 루트를 사용한다. 명시적 directory는 계속 우선한다. 데이터 seed/SQLite·loader·snapshot/조회·runner/전송 경계와 기존 assertions는 보존했다. 새 helper/의존성·운영 코드/설정·CI 서버 변경이나 `/private/tmp` 생성 우회는 추가하지 않았다.
- **회귀·검증:** 기존 QA 세션이 소유 fixture1개와 신규 [경로 회귀](../../../tests/test_qa02_temp_directory.py)만 변경했다. 최초 신규4실패는 경로 불일치3건과 신규 날짜 기대값 작성 오류1건이었다. 작성 오류만 보정한 기존 fixture에서3 failed /1 passed를 재확인한 뒤 경로 인자만 제거했다. 최초 RED와 확인 RED 로그/XML을 각각 보존했다. 최종 신규4개·기존 QA02 포함 관련35개가 통과했다. 메인 최종285입력 격리 후보의 기본 **1998 passed / 2 deselected / 51 warnings, 107.28초**도 통과했다. 수치는 포함 관계이며 합산하지 않는다. Python은 깨끗한 환경·기존 venv·-B·task-local TMPDIR/cache/basetemp/XML/log로 실행했다.
- **완료 조건:** 설정된 TMPDIR·tempfile cache와 명시 directory의 우선순위 및 실제 SQLite 데이터/조회 경계가 유지되고 기본 suite가 통과해야 한다. 수정이 반영된 새 SHA의 Ubuntu Actions에서 해당 기본 회귀가 성공한 결과가 있어야 원격 검증까지 완료한다. 현재 변경은 미커밋이므로 그 조건은 미충족이다.
- **소유·한계:** 메인은 원본 통합/공유 문서/전체 검사, QA는 위2파일만 소유했다. QA 격리본의 비소유283입력은 불변이며 메인은 공유 문서11개를 별도로 갱신했다. 기존 테스트·fixture의 나머지 의미·운영 source·실제 설정/backup/index/HEAD/branch/모드는 보존했다. Mac에서 설정된 temp root를 제어하는 회귀와 기존 AppTest를 실행했으며 새 Linux 프로세스/수정 후 원격 CI를 실행했다고 주장하지 않는다. 전체 검사 후 Python SHA를 고정하고 문서·HTML만 갱신했다. AST/메모리 compile·공백·MD 링크/ID·HTML12페이지/문서58개·Node 탐색19개를 검사하며 lint/typecheck 도구를 새로 설치하지 않는다. 커밋·push·원격 재실행은 사용자 명시 요청 전까지 하지 않는다.

## 실행 기록

2026-10-31 G07b: 기존181개를 새로 통과하고 독립154개가 최초 실행에서 통과했다. native ps/inspect/exec hang 등6개 경계를 더한 독립160개·합산341 passed / failure·error·skip0(64.57초)로 최종 승인했다. 실제 전달된 HTTP_PROBE를 fake Docker/HTTP에 연결하고 shell 종료 코드·단일 budget·유한 cleanup·최소 안정 관찰·runtime 확인 응답·포트 우선순위를 검증했다. pytest 실패·제품 보완은 없었고 입력266개와 소유 밖 파일을 보존했다. 메인 최종 후보의 기본1593개도 통과했다. [독립 회귀](../../../tests/test_g07b_independent_qa.py)·[명령·한계](../../tasks/07_operations_docs.md#시작-후-준비-확인-2026-10-31)를 따른다. 실제 Docker/host 접근·운영 DB/API·CI·배포와 실제 Python3.10 실행은 미검증이며 QA01~03 상태는 유지한다.

2026-10-29 G07a: 기존279개를 새로 실행한 뒤 독립68개를 합쳐347 passed / failure·error·skip0이다. 최초 QA의64 passed / 4 failed / 4 teardown errors는 slots 인스턴스 logger patch 주입 오류로, QA 소유 파일에서 클래스 patch로 보정했고 실패 로그/XML을 보존했다. 제품 보완·기존 테스트 수정·skip/xfail은 없었다. 운영의 일반 wrapped SSL RED/GREEN과 인증서 사유의 기존 통과를 구분했다. 입력263개가 시작·종료에 일치하고 메인에 독립 회귀를 통합한 최종 후보 기본1322개도 통과했다. 실제 운영·DB/통신·외부 Compose 재기동·G07b·원격 CI는 미검증이다. [독립 회귀](../../../tests/test_g07a_independent_qa.py)·[검증 기록](../../tasks/07_operations_docs.md#스케줄러-실패-후-대기-2026-10-29)을 따른다.

2026-10-27 G01b 독립 검증 완료: 기존 데이터 종료 후 새 격리본에서 관련241개를 새로 통과했다. 독립40개 중 무효 list/ndarray가 실제 SQLite save를 중단하는 회귀8개를 발견해 합산273 passed / 8 failed로 보완 요청했다. 최초 QA의 JSON dtype 기대값2개는 기준 코드의 실제 serializer/decoder와 비교하도록 QA 파일만 보정했고 최초30 passed / 10 failed 로그도 보존했다. QA 종료 후 데이터 세션의 비스칼라 guard2줄 보완을 받은 뒤 독립40 passed·합산281 passed를 새로 통과해 G01b 지정 범위를 승인했다. 수정 manifest262개가 시작·종료에 일치했고 제품/기존 테스트는 QA가 수정하지 않았다. 메인 최종 후보 기본1100 passed / 2 deselected / 36 warnings도 통과했다. [새 독립 회귀](../../../tests/test_g01b_independent_qa.py)·[입력 정책·명령·미검증 범위](../../tasks/02_data_collection.md#snapshot-기준일-날짜-계약-2026-10-27)를 따른다. 실제 PostgreSQL·운영 DB/API·기존 metadata 수선·CI·배포는 미검증이며 QA01~03 상태는 유지한다.

2026-10-23 QA02 최종 결과: main `036def2`의 격리본에서 기존 QA 세션을 재사용했다. 실제 main·사이드바·홈·리포트·관심종목·실행·차트와 임시 SQLite를 연결한 독립27개/기존259개 통과 후, 메인의 실제 브라우저가 고립된 수급값의 가시성 결함을 발견했다. 양수·음수·실제0 marker3개 실패, null gap1개 통과를 독립 재현하고 전문 차트의 점 표시만 메인이 보완했다. 보완 후 신규31개 전체·합산290개를 독립 통과했고 메인의 격리 후보 기본1001 passed / 2 deselected / 32 warnings도 통과했다. 수정 manifest258개와 제품/fixture 해시를 대조했다. 원본/판단 날짜·source·선택 복원·조회 중 실행0회·명시적5버튼·수집/전송 실패 경계를 확인했다. 완료된 script의 홈/실행 SELECT2·리포트/관심종목3은 snapshot2와 기존 즐겨찾기0/1을 포함하며 프레임/상태/차트 consumer는0회다. 중간 rerun도 별도 attempt로 기록하므로 사용자 클릭 전체 SELECT0회를 주장하지 않는다.

같은 통합 앱의1920×958·390×844에서 메인이 외국인2점·기관1점과 null gap, 대비·0.8rem·키보드 포커스·Material 아이콘을 확인했다. QA는 일치하는 해시와 메인의 브라우저 관찰 기록을 검토해 지정 범위를 승인했으며 직접 브라우저를 조작하거나 캡처 이미지를 본 판정과 구분한다. 캡처는 CUA 도구 관찰에 있고 로컬 이미지 파일은 없다. 기존 G06c 카드 HTML·G08d 범례/도구 모음 혼잡·기존 위젯/deprecation 경고, 운영 API/DB·실제 Discord·배포·원격 CI·앱 전체 접근성은 남은 범위다. QA01·QA03은 상태를 유지한다. [재현 경로·명령·측정·한계](../../tasks/04_dashboard.md#독립-종합-검증과-고립-수급-관측점-2026-10-23). 원본 보완은 커밋 전이며 commit·push는 수행하지 않았다.

2026-10-14 G05a 커밋 전 재검증: 메인이 다른 미커밋 기능을 제외한 동일 커밋 후보를 격리해 관련199개·기본832개/2 deselected/32 warnings를 새로 통과했다. 실제 브라우저 근거는 10월 13일 관측이며 별도 QA 세션 판정과 QA02 전체 완료를 대신하지 않는다.

2026-10-12 G04 최종 결과: 8파일이 manifest와 일치하는 격리본에서 기존265개·독립74개를 검증해339 passed / 26 warnings, 차단 결함 없음이다. 최초 확대 실행338 passed / 1 failed는 일반 안내 문구까지 결과 제목으로 오인한 신규 QA assertion으로, 정확한 결과 제목을 검사하도록 QA 파일만 보정해 별도339개 실행을 통과했다. 실패 로그는 보존했다. 실제 adapter·generator/CLI·임시 CSV 저장·UI action/execute/render를 사용해 날짜 집합·미세 가격 차이·양쪽 무효값·반복/MultiIndex·입력 attrs 보존·정상 체결/MDD·단일 실패의 runner/context/persistence0회·stale 결과 삭제를 확인했다. 원본 최종 관련339 passed, 기본780 passed / 2 deselected이며 기능9파일·설정4개·백업 보존도 확인했다. 실제 브라우저·운영 DB/API·배포·원격 CI·배치 전체 원자성은 미검증이다. QA01~03 상태는 유지한다. [검증 기록](../session_reports/2026-10-12_saved_signal_alignment.md).

2026-10-05: 원본 main과 통합 계획을 독립적으로 읽어 세 검증 공백을 확인했다. QA 세션의 이번 검토에서는 파일 변경·테스트 실행·운영 호출을 수행하지 않았다. 세 작업은 완료된 QA 결과가 아니라 앞으로 보완할 항목이다. 진행 시 [색인의 갱신 규칙](README.md)을 따른다.


2026-10-09 최종 결과: QA01의 독립 코드 리뷰·로컬 DB 검증을 완료했다. [신규 PostgreSQL 정렬 테스트](../../../tests/integration/test_postgresql_dataset_frame_ordering.py)는 localhost/테스트 DB 보호와 UUID 스키마 격리·정리를 적용한다. CI 실행 대상을 tests/integration으로 연결했고 같은 실행 명령이 2개를 선택·통과했다. 수정 전 HEAD repository를 복원하면 같은 회귀가 예상한 1 failed이며, 통과·실패 뒤 QA 스키마도 정리됐다. 원본 통합 후 기본 suite 398 passed / 2 deselected, PostgreSQL 2 passed. 원격 GitHub Actions는 커밋 전이라 미실행이며 QA01 상태는 **검증 대기**다. [검증 기록](../session_reports/2026-10-09_latest_snapshot_ordering.md). 임시 DB 제거 확인 완료.

2026-10-10: G01a·QA01 관련 변경이 main `b29c346`으로 커밋된 것을 확인했다. 원격 CI 조회는 로컬 GitHub CLI 미인증으로 실행되지 않아 성공 여부 미확인이다. 검증 대기 상태를 유지하며 독립적인 G02를 진행한다.

2026-10-10 G02 최종 결과: 기존 운영 세션이 종료된 뒤 QA 세션에서 원본 `b29c346` + G02를 별도 임시 복사해 검증했다. 담당 회귀83 passed와 독립 경계36 passed, 차단 결함 없음이다. 메인이 동작 경계35개를 원본에 통합했고 관련118 passed, 기본508 passed / 2 deselected를 새로 확인했다. 외부 cwd·공백 경로·실패 코드·기본 설정 경로·파일/타입 오류와 검사 전용 CLI의 수집·DB·network·로그0회를 검증했다. 실제 Docker·mount 권한·readiness·원격 CI는 미검증이며 G02는 모의 완료 조건을 충족해 완료다. QA01~03의 상태는 그대로 유지한다. [검증 기록](../session_reports/2026-10-10_start_restart_preflight.md).

2026-10-11 G03 최종 결과: 기존 퀀트 종료 후 격리본에서 관련89개·독립37개를 새로 실행해111 passed / 15 failed를 확인했다. 혼합 Timestamp의 유효 날짜 손실과 Timestamp+문자열 오류를 다섯 경계에서 재현했다. 퀀트 보완 종료 후 새로126개를 통과했고 date/datetime·반복 index26개를 추가한 독립152개도 통과했다. 메인이 독립63개를 원본에 통합한 뒤 관련152 passed, 기본635 passed / 2 deselected를 확인했다. 최초 실패 로그는 보존했고 보완 이후 증거를 구분했다. 메모리 저장 차단·준비표/경고 안내·별칭·불변성·정상 성과 보존을 확인했으며 실제 브라우저·운영 DB/API·배포·원격 CI는 미검증이다. QA01~03 상태는 유지한다. [검증 기록](../session_reports/2026-10-10_backtest_duplicate_dates.md).
