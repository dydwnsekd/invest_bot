# Task 04. Dashboard

## 목표

수집, 분석, 신호, 리포트, 테스트 상태를 브라우저에서 빠르게 확인하고 필요한 작업을 직접 실행할 수 있는 대시보드를 제공한다.

## 다음 개선 계획 (2026-10-22 확인)

현재 순서는 [개선 작업 색인](../operations/improvements/README.md)을 따른다. G06a까지 main `bd958d5`에 반영됐고 G06b는 아래 작업 트리에서 구현·검증을 마친 커밋 전 상태다. QA02의 별도 독립 종합 판정과 G01a·QA01 원격 CI 확인은 남아 있다. 다음 기능 구현 후보는 G01b다. G06c 배치와 G08d 모바일 차트 범례는 별도 대기다. [10월 5일 순차 계획](../operations/improvement_plan_2026-10-05.md)은 최초 검토 배경이다.

## 상태 텍스트 대비와 라벨 크기 (2026-10-22)

main `bd958d5` + 미커밋 G06b 기준이다. [DESIGN](../../DESIGN.md)의 네이비/슬레이트 체계 안에서 [상태 formatter](../../src/invest_bot/dashboard/streamlit_formatters.py)의 매수·매도·중립 색을 밝게 조정했다. [CSS](../../src/invest_bot/dashboard/streamlit_styles.py)의 보조 라벨11개 선언을0.8rem으로 올리고 본문 기본 버튼에 어두운 글자를 적용했다. `stAppViewContainer`가 사이드바도 포함하는 것을 실제 DOM에서 확인해 새 규칙은 `stMain`으로 좁혔다. 기존 상태 분류와 판단·라우팅·조회·실행 경계는 보존한다.

[가상 fixture](../../tests/g06b_readability_fixture.py)는 실제 리포트 카드·관심종목 상태·해석 renderer와 제품 CSS를 사용한다. 실제 설정·운영 데이터를 포함하지 않고 backing storage 읽기를 금지했다. [신규17개 회귀](../../tests/test_dashboard_readability.py)는 상태3종×배경3종 대비, 라벨 크기, 실제 renderer 상태와 완료 아이콘 보호를 검증한다. 최초 fixture의 전략 행 개수 기대값을 실제 renderer의3개로 보정한 후 유효 변경 전 회귀13 failed / 3 passed로 대비·크기 문제를 재현했다. 추가 발견한 완료 아이콘 회귀도 수정 전1 failed였다. 최종 관련202 passed, 격리 후보 기본970 passed / 2 deselected / 32 warnings다.

- 관련 명령: `.venv/bin/python -B -m pytest tests/test_dashboard_readability.py tests/test_streamlit_dashboard.py tests/test_dashboard_data_status.py tests/test_dashboard_action_scope.py -q --tb=short`.
- 기본 명령: `.venv/bin/python -B scripts/run_tests.py --suite default -q --tb=short`. 실제 실행은 격리 cwd·정리한 환경 변수에서 원본의 venv Python을 사용했다. 이후 문서 갱신만 후보에 동기화하고 링크·ID를 별도로 검사했다.
- 실제 브라우저:1920×958·390×844에서 계산된 글자색·배경색·투명도·그라데이션 색 범위를 읽었다. 아래 수치는 색 범위를 합성한 보수적인 대비 하한이며 화면 픽셀 전체의 최솟값을 직접 샘플링한 결과와 구분한다.

| 검증 표본 | 대비 하한 | 글자 크기 |
| --- | --- | --- |
| 리포트 전략 매수·매도·중립 | 12.29 / 9.13 / 14.00 | 1rem |
| 종합 신호 매수·매도·중립 배지 | 7.45 / 8.23 / 7.70 | 0.8rem |
| 본문 기본 버튼 일반/포커스 상태 | 9.31 / 6.53 | 0.875rem |
| 사이드바 기본 버튼 | 16.90 | 0.875rem |
| 관심종목 날짜·시각·상태 라벨 | 최소11.44 | 최소0.8rem |
| 해석 모아보기 라벨·배지 | 최소11.72 | 최소0.8rem |

키보드 Shift+Tab으로 본문 버튼의 `focus-visible`·2px 청색 outline·2px offset을 확인했고 Tab으로 입력 필드의 청색 테두리를 확인했다. 모바일의 지정 표본은 줄바꿈됐고 페이지 내용과 viewport 너비가390px로 같았다. 완료 상태 `check`가 일반 글자로 표시되는 기존 누락을 발견해 `stExpanderIconCheck`도 기존 Material font/ligature 보호에 포함했다. 수정 후 체크·펼침 아이콘은 Material 글꼴과 `liga`를 사용하고 glyph 폭15px로 표시됐다. 장식용 아이콘의0 크기 숨김 규칙은 라벨 최소 크기와 별도로 보존한다.

기존 대시보드 하위 에이전트의 순차 읽기 전용 리뷰에 차단 결함은 없었다. 메인이 구현·회귀·브라우저·통합을 수행했으며 별도 QA 세션 종합 판정과 구분한다. 임시 앱·탭을 종료하고 원본 실제 설정·백업·관련 없는 추적 파일·HEAD·Git index를 보존했다. commit·push·운영 서비스 조작은 수행하지 않았다. 운영 API/DB·배포·원격 CI와 앱 전체 접근성 인증은 미검증이다. [G06b 상태](../operations/improvements/dashboard.md#g06b), [QA02 남은 범위](../operations/improvements/qa.md#qa02)를 따른다.

## 생성·전송 범위 안내 (2026-10-19)

main `9867d48` + 당시 미커밋 G06a를 검증했고 이후 코드 `7f99a33`·문서 `bd958d5`로 반영됐다. 아래는 10월19일 증거다. [데이터 갱신 화면](../../src/invest_bot/dashboard/streamlit_actions.py)은 버튼을 누르기 전에 실행 대상 종목명·코드·총 개수, 정규화된 조회 기간, 버튼별 처리 단계와 Discord 전송 설정 여부를 표시한다. 대상은 처음3개와 나머지 개수로 요약하며 선택 위젯에서 전체 목록을 확인할 수 있다. 선택이 없으면 이를 명시한다.

데이터 수집·지표 계산·신호 생성은 해당 단계만 실행하고 Discord로 전송하지 않는다. 전체 파이프라인은 수집 후 성공 종목만 지표·신호·리포트 생성으로 진행한다. 리포트 생성은 저장된 지표·신호·수급을 사용한다. 전체 파이프라인과 리포트 생성은 리포트 저장 후 Discord 전송을 요청한다. 공백을 제거한 기존 `settings.discord_webhook_url`이 비어 있으면 미설정·전송 건너뛰기, 값이 있으면 설정됨·전송 시도를 안내한다. 설정만으로 성공을 보장하지 않고 실행 결과에서 확인하게 한다. 사전 안내에 주소·토큰은 넣지 않는다.

별도 사전 조회·작업 실행을 추가하지 않았고 기존 실행·결과 처리 함수는 기준 코드와 AST가 동일하다. 실제 설정을 복사하지 않은 격리 공간에서 [실제 renderer fixture](../../tests/g06a_action_fixture.py)와 [신규20개 회귀](../../tests/test_dashboard_action_scope.py)를 사용했다. 안내 추가 전에는4 failed / 16 passed였으며 수정 후 관련169 passed, 최종 격리 후보 기본938 passed / 2 deselected / 32 warnings다.

- 관련 명령: `.venv/bin/python -B -m pytest tests/test_dashboard_action_scope.py tests/test_streamlit_dashboard.py tests/test_run_market_report.py tests/test_discord_report_notifier.py -q --tb=short`.
- 기본 명령: `.venv/bin/python -B scripts/run_tests.py --suite default -q --tb=short`. 실제 실행은 격리 후보 cwd·정리한 환경 변수에서 원본의 venv Python을 사용했다.
- 경계: 초기 표시·종목/기간/설정 변경은 작업 호출0회다. 5개 버튼은 명시 클릭 뒤 기존 종목별 호출 횟수·순서·`delivery_target="discord"`를 유지한다. 빈 선택은 모든 버튼에서 작업0회다. 수집 부분 성공은 성공 종목만 후속 처리하고 전체 실패는 후속0회다. 웹훅 미설정 skipped와 HTTP500 failed는 기존 경고를 유지한다. 빈 문자열·공백 설정을 구분해 검사하고 사전 안내의 가상 URL·토큰 노출도 차단했다.
- 실제 브라우저: 같은 가상 fixture·실제 renderer·CSS의 1920×958·390×844에서 설정됨/미설정과 버튼 앞 설명을 확인했다. 좁은 화면에서 설명은 줄바꿈됐고 페이지 가로 너비와 내용 너비가390px로 같았다. 가상 리포트 클릭 전 호출0회, 클릭 후 기록용 리포트1회와 웹훅 미설정 경고를 확인했다. 실제 외부 전송은 하지 않았으며 임시 앱·탭은 종료했다.
- 리뷰·보존: 기존 대시보드 하위 에이전트의 읽기 전용 리뷰에 차단 결함은 없었다. 메인이 구현·회귀·브라우저·통합을 수행했으며 별도 QA 세션 종합 판정은 아니다. 실제 설정·운영 데이터·백업·관련 없는 추적 파일과 HEAD·Git index를 보존하고 commit·push·운영 재시작은 수행하지 않았다.

운영 API/DB·실제 Discord 전달·배포·원격 CI는 미검증이다. 안내만으로 URL 유효성이나 전송 성공을 판단하지 않는다. G06b의 대비·포커스, G06c 배치와 G08d 차트 범례는 별도 대기다. [G06a 상태](../operations/improvements/dashboard.md#g06a), [QA02 남은 범위](../operations/improvements/qa.md#qa02)를 따른다.

## 원본·판단 기준일과 다음 행동 (2026-10-18)

main `63bba25` 기준 작업 트리에 G05b 코드·회귀6파일을 반영했고 이후 `9867d48`로 main에 커밋됐다. 아래 수치·브라우저 결과는 10월18일 검증 기록이다. 홈·투자 리포트·관심종목이 [공통 상태 계산](../../src/invest_bot/dashboard/data_status.py)을 사용한다. 원본 가격·수급 관측일, 분석 지표·전략 신호·판단 리포트 날짜, 수집·분석 저장 시각을 구분한다. 선택한 리포트의 판단일을 최신 원본일로 바꾸지 않으며 홈은 종목별 상태를 집계해 다른 종목의 최신 날짜로 지연을 숨기지 않는다.

원본이 최신이고 분석만 이전이면 분석 갱신을 안내한다. 원본 누락과 지연은 각 사유를 표시하고, 원본이 확인 기준일보다 앞서거나 판단이 해당 원본보다 앞서면 기준일 불일치를 안내한다. 다음 행동 버튼은 필요한 화면으로만 이동한다. 리포트 검색·선택·탭 왕복은 선택 식별자를 세션에 보존하고 현재 위젯 값을 우선하며 수집·분석·생성·전송을 실행하지 않는다. DB snapshot의 `latest_records=()`는 빈 상태 자체를 신뢰하고, `None`인 기존 파일 경로와 구분한다.

검증은 실제 설정·운영 데이터를 포함하지 않은 격리 후보에서 수행했다. 기준 코드 기본893 passed / 2 deselected를 확인한 뒤 신규 초기 회귀는6 failed / 1 passed로 차이를 재현했다. [신규25개 회귀](../../tests/test_dashboard_data_status.py)와 기존 G05a·snapshot·대시보드를 포함한 관련220 passed, 최종 후보 기본918 passed / 2 deselected / 32 warnings다. 경고32개는 기준 코드에도 있던 경고다.

- 관련 명령: `.venv/bin/python -B -m pytest tests/test_dashboard_data_status.py tests/test_streamlit_dashboard.py tests/test_watchlist_snapshot_queries.py tests/test_dashboard_snapshot_frame_loader.py tests/test_dashboard_summary_flow.py tests/test_g05a_boundary_qa.py -q --tb=short`.
- 기본 명령: `.venv/bin/python -B scripts/run_tests.py --suite default -q --tb=short`. 실제 실행은 격리 후보 cwd·정리한 환경 변수에서 원본의 venv Python을 사용했다.
- 실제 renderer: [가상 fixture](../../tests/g05b_dashboard_fixture.py)를 사용해 홈·리포트·관심종목 각각 분석 지연·원본 누락·판단일 불일치·최신의12사례를 AppTest로 확인했다. 검색·선택·탭 왕복에서 발견한 리포트 선택 초기화도 보완해 재검증했다. 실행·전송·backing storage 우회 호출은0회다.
- 조회 경계: 실제 임시 SQLite에서 snapshot을 만든 뒤 세 화면의 상태 계산 추가 SELECT0회를 측정했다. 전체 화면 rerun 조회0회나 기존 파일 경로의 추가 파일 읽기0회를 의미하지 않는다.
- 실제 브라우저: 같은 가상 fixture와 실제 renderer·CSS로 1920×958·390×844를 확인했다. 홈의 판단일10/01·원본10/02, 선택 리포트 날짜 보존, 누락 수급·미래 판단일의 사유가 표시됐다. 좁은 화면의 새 날짜·사유는 줄바꿈됐고 페이지 가로 넘침은 없었다. 임시 앱·브라우저는 검증 후 종료했다.
- 리뷰·보존: 기존 대시보드 하위 에이전트를 순차 재사용한 읽기 전용 리뷰에서 차단 결함은 없었다. 별도 QA 세션 종합 판정과 구분한다. 원본 실제 설정·백업·관련 없는 추적 파일과 HEAD·Git index를 보존했다. commit·push·운영 재시작은 수행하지 않았다.
- 문서: 관리 Markdown57개·로컬 참조649개·문서 ID57개·개념 ID12개·관계14개의 누락·중복·잘못된 연결은0개다. Git index에 추가하지 않은 신규 Python3파일도 이번 작업 트리 후보에 포함해 참조를 검사했다. Python AST와 공백 검사도 통과했다.

운영 DB·실제 API·배포·원격 CI는 미검증이다. 평일을 사용하는 기존 기준일 계산과 날짜 컬럼 우선순위·파일 읽기 정책은 유지했으며 휴장일·장중 정책으로 확대하지 않았다. 가상 홈의 두 번째 후보 카드에서 확인된 기존 HTML 노출은 변경 전 함수와 동일하며 G06c에서 재검토한다. 기존 모바일 차트 범례 문제는 G08d에 남긴다. [G05b 상태](../operations/improvements/dashboard.md#g05b)와 [QA02 잔여 범위](../operations/improvements/qa.md#qa02)를 참고한다.

## 차트 summary 수급 연결 (2026-10-13)

main `b9fd5da` + G05a 변경을 검증했고 2026-10-14 `1e23b95`로 main에 반영했다. 10월17일 지식 갱신에서도 이 코드와 아래 계약을 대조했으며 화면·운영 검증을 새로 실행한 것은 아니다. 현재 리포트·관심종목·데이터 보기의 공용 chart loader가 실제 관측일과 유한 수급값이 있는 detail을 우선한다. detail을 사용할 수 없으면 summary 자체의 날짜·값을 연결한다. 유효 detail의 빈 날짜/투자자 값을 summary로 보충하지 않고, 날짜 없는 상세 값에 가격일이나 파일명 날짜를 붙이지 않는다.

가격 시각·시간대와 OHLCV를 보존하며 관측일별로 연결한다. 같은 날 가격 행이 여러 개면 일별 수급을 복제하지 않는다. 잔여 가격 프레임 수급 alias를 제거하고 관측일 없는 값·null·무효값을 0으로 만들지 않는다. 주·월봉의 모두 미관측인 기간도 null이다. 원본 누락·무효 날짜/값·기간 불일치는 caption으로 안내한다. 명시 snapshot은 누락·빈 payload도 조회의 기준이며 backing DB/CSV 재조회로 대체하지 않는다.

관련199 passed, 원본 기본832 passed / 2 deselected와 실제 가상 앱의 1920×958·390×844를 검증했다. chart 추가 SELECT0회, 검색·선택·탭 왕복 실행/전송0회를 유지한다. QA 세션은 사용량 제한으로 중단돼 메인이 경계10개와 실제 화면을 보완했으며 별도 독립 판정은 미완료다. 운영 데이터·배포·원격 CI는 미검증이며 모바일 범례/제목 겹침은 G08d에 남는다. 상태는 [G05a](../operations/improvements/dashboard.md#g05a), 수행 주체와 검증 한계는 [QA02](../operations/improvements/qa.md#qa02)를 따른다. 상세 검증 보고서는 로컬 제외 파일 `docs/operations/session_reports/2026-10-13_chart_summary_flow.md`에 보관한다.

2026-10-14 커밋 후보만 격리한 새 검증에서도 관련199개·기본832개/2 deselected/32 warnings가 통과했다. 다른 미커밋 기능은 포함하지 않았으며 상세 보고서·실제 산출물은 Git 제외로 보존한다.

## 최신 dataset 목록 단일 조회 (2026-09-30 · 구현·검증 완료)

관심종목 화면의 최신 dataset 목록 조회 10회를 단일 SELECT로 묶었다. 각 dataset의 최신 record 우선순위와 반환 순서를 유지한다. 실제 DB 네 관심종목의 SELECT는 12→3회/rerun, 서버 rerun 중앙값은 183.72→180.51ms였으며 화면·차트 출력과 PostgreSQL의 record 목록이 이전과 같았다. 기본 suite는 397 passed / 1 deselected다. 코드 `4047478`, 문서 `4ec8d3b`로 main에 반영됐다. 10월 3일 조회 관련 파일 네 개의 원본/컨테이너 hash 일치와 web HTTP 200을 확인했다. 이는 당시 배포 확인이며 현재 서비스 상태를 보증하지 않는다. [측정·검증 기록](../operations/session_reports/2026-09-19_dashboard.md)

## 리포트·차트 snapshot 재사용 (2026-09-28 · 당시 검토)

관심종목 리포트와 선택 종목의 차트가 같은 rerun의 최신 DB record를 재사용한다. 파일 저장 방식은 기존 읽기 경로를 유지하며, 다음 rerun에서는 새 snapshot을 만든다. 실제 DB 네 관심종목 측정에서 SELECT 20→12회/rerun, 서버 rerun 중앙값 195.42→187.83ms였다. 전후 화면·차트 출력은 같았고 기본 suite는 396 passed / 1 deselected다. 해당 변경은 코드 `63fdb31`, 문서 `bbcaa17`로 main에 반영됐다. 운영 배포 여부는 확인하지 않았다. [측정·검증 기록](../operations/session_reports/2026-09-19_dashboard.md)

## 관심종목 반복 조회 개선 (2026-09-26 구현 · 09-28 검증 보완)

`ae34fff` 기준 작업 트리에서 관심종목 상태 계산이 snapshot의 최신 DB record를 재사용하도록 개선했다. 같은 snapshot의 값은 유지하고 다음 rerun에서 새 저장값을 읽는다. CSV 읽기와 상태 판정 규칙은 유지한다.

- 실제 DB 네 관심종목: SELECT 60→20회/rerun, 7회 측정 서버 rerun 중앙값 236.78→197.47ms
- 전후 화면 출력·차트 spec 동일, 실제 브라우저의 상태 카드·종목 선택·차트 표시 확인
- 기본 suite 395 passed / 1 deselected. 누락·빈 데이터·날짜 우선순위·다음 snapshot 갱신·CSV 회귀 포함
- 개선 코드는 `00abb2d`, 문서는 `7d1aa33`으로 `main`과 `origin/main`에 반영됐다. 누락됐던 회귀 테스트는 후속 코드 커밋 `63fdb31`에 포함됐다. 운영 배포 여부는 확인하지 않았다.
- 측정 범위와 한계: [9월 26일 검증 기록](../operations/session_reports/2026-09-19_dashboard.md)

## 완료된 항목

### 2026-09-25 당시 main 반영

아래 변경은 `073f2a2` 이후 `main`에 반영되었다. 로컬 `main`과 `origin/main`은 `517e4a9`로 일치한다. 운영 서비스의 최신 코드 배포 여부는 확인하지 않았다.

- snapshot 최신 목록·종목명 map 공유와 frame JSON 재사용으로 중복 읽기 축소
- 리포트·관심종목·데이터 보기의 frame을 rerun 범위에서만 재사용하고 다음 rerun에서 최신값 조회
- 저장 백테스트 이력 UI를 별도 모듈로 분리하고 기존 결과 복원·비실행 계약 보존
- 정기 수집 예외와 종목별 일부 실패를 구분하고 대기·재시작 이후에도 최근 실패 표시 유지
- 관심종목 카드 HTML 노출, 홈의 분석 시각 말줄임, 사이드바의 잘못된 파일 경로 안내 수정
- 날짜별 변경·측정·검증: [대시보드 검증 기록](../operations/session_reports/2026-09-19_dashboard.md)

당시 후속 항목이던 관심종목 반복 조회 개선은 위 9월 26일 작업에서 구현·검증했고 이후 main에 반영했다. 운영 배포 확인은 남아 있다. 측정값은 각 날짜의 데이터·실행 환경에 한정된다.

### 기존 구현

- [x] Streamlit 기반 대시보드 구현
- [x] 사용자 여정 중심 메뉴명과 메뉴별 상단 hero 문구 적용
- [x] 홈 quick-start 카드로 처음 보는 사용자 진행 순서 안내
- [x] 홈 우측 본문을 오늘의 투자 브리핑, 오늘 볼 만한 종목, 다음 행동 카드 중심으로 개편
- [x] 홈을 저장된 snapshot 기준의 읽기 전용 브리핑으로 전환하고, 리포트·신호 기준일/데이터 상태/검증 실패를 신뢰 상태로 표시
- [x] 홈 다음 행동 카드를 데이터 갱신, 투자 리포트, 백테스트, 시스템 검증 화면 이동 버튼으로 연결
- [x] 홈의 신뢰 상태와 다음 행동을 연결해 테스트 실패·데이터 기준일 문제를 리포트 확인보다 먼저 안내
- [x] 홈 신뢰 상태에 시장 기준일, 마지막 수집 완료 시각, 마지막 분석 결과 생성 시각을 분리 표시
- [x] 관심종목 상태 카드에 종목별 마지막 수집 저장·분석 생성 시각 표시
- [x] 최신 수집/분석 시각 강조를 홈·관심종목의 상태 문맥에 맞게 완료하고, 기준일·수집·분석 시간을 혼동 없이 분리
- [x] 분리된 HTML 카드 wrapper를 Streamlit 컨테이너 또는 단일 HTML 렌더링으로 정리해 빈 테두리·여백 영역 제거
- [x] 투자 리포트 / 관심종목 / 백테스트 본문을 종목 중심 카드형으로 보강
- [x] 종목 선택 기반 summary-first 데이터 보기 구현
- [x] 골든크로스 신호 및 시장 리포트 표시
- [x] 투자 리포트 탭에서 선택된 1건 중심 본문 표시
- [x] 투자 리포트 탭 상단 해석 모아보기 토글
- [x] 리포트 카드 내 전략별 판단 요약 표시
- [x] 리포트 후보 카드 한글 요약·날짜·결과 수 표시 및 최종 의견/전략 신호 충돌 주의 문구 추가
- [x] 리포트 종합 신호에 전략 합의도·핵심 지표/수급 충족 상태·상승 근거·위험 요인·재평가 기준을 함께 표시
- [x] 보조 라벨 글자 크기와 가격·날짜·지표 숫자 정렬 가독성 개선
- [x] 해석 모아보기와 전략 판단 근거 카드 UI 줄바꿈 처리
- [x] 투자 리포트 / 데이터 보기 탭 공통 인터랙티브 차트와 조회 기간 조절
- [x] 데이터 보기 탭에서 최대 3개 종목의 공통 거래일 종가를 시작일 100 또는 원가격 기준으로 비교
- [x] stock dataset용 전문가형 주가 차트(일봉/주봉/월봉, 수급 panel fallback 포함)
- [x] 리포트 즐겨찾기 저장
- [x] 관심종목 전용 탭 추가
- [x] 전용 `백테스트` 탭 추가
- [x] `용어 해설` 탭 추가
- [x] `준비 확인 -> 준비 실행 -> 백테스트 실행 -> 결과 확인` 흐름 추가
- [x] 준비 상태 panel과 전략별 차단 사유 표시
- [x] 백테스트 결과 요약 카드 / 비교표 / 거래 순서 누적 수익률 차트 / 거래 로그 표시
- [x] 백테스트 일별 평가금액 곡선과 초기자금·체결 기준·비용 미반영 가정 표시
- [x] 테스트 결과 표시
- [x] 데이터 수집 실행
- [x] 데이터 갱신 / 백테스트 준비 / CLI / 스케줄러 수집 기본일수 365일 통일
- [x] 데이터 갱신 / 백테스트 준비 수집 조회기간 캘린더 선택 추가
- [x] 지표 계산 실행
- [x] 골든크로스 신호 생성 실행
- [x] 시장 리포트 생성 실행
- [x] 전체 파이프라인 실행
- [x] 시장 리포트 Discord warning/success 분리 노출
- [x] 정기 수집 상태와 최근 실행 로그 표시
- [x] A+ dark terminal theme/font 적용 (고대비 팔레트 반영)
- [x] 좌측 메뉴를 박스 없는 텍스트형 내비게이션으로 정리
- [x] 관심종목별 가격·수급·분석·신호·리포트 기준일과 갱신 필요 사유 표시
- [x] 관심종목 조회와 데이터 갱신을 분리하고, 갱신 필요 종목을 데이터 갱신 화면에 미리 선택

## 최근 완료한 확장 항목

- [x] 백테스트 artifact history / reload
- [x] 백테스트 전략별 실험 설정, 기본값 복원, 설정 메타데이터 표시
- [x] 백테스트 복수 전략 조합(AND / OR / 가중치), 개별·조합 결과 비교, 조합 규칙 메타데이터 표시
- [x] 백테스트 다종목 포트폴리오 집계(전략별 동일 비중·리밸런싱 없음·공통 거래일, 비중·기여도·제외 사유 표시)
- [x] 대시보드 설정 저장 고도화 (현재 브라우저 세션 한정)

## 현재 메뉴 구조

- 좌측 메뉴는 사용자 행동 기준으로 `홈`, `데이터 갱신`, `투자 리포트`, `관심종목`, `백테스트`, `데이터 보기`, `용어 해설`, `시스템 검증` 순서로 제공
- 예전 메뉴명(`상태판`, `작업 실행`, `리포트 해석`, `데이터 탐색`, `검증`)은 내부 alias로 해석해 기존 세션 상태와 테스트 호환성을 유지
- 상단 hero 영역은 선택된 메뉴에 맞춰 목적과 다음 행동을 짧게 설명
- 선택 탭은 URL query param에 동기화되어 새로고침해도 기존 탭을 유지
- 홈은 저장된 snapshot 기준으로 오늘의 투자 브리핑, 데이터 신뢰 상태, 오늘 볼 만한 종목, 다음 행동, quick-start 순서의 확인 흐름을 안내

## 현재 데이터 갱신 탭 동작

- 여러 종목 선택 기반 **배치 실행**만 노출
- `한 종목` 전용 섹션은 제거
- 선택 종목들에 대해 아래 작업을 직접 실행 가능
- 데이터 수집, 전체 파이프라인, 지표/신호/리포트 생성 버튼 실행 중에는 진행 상태 메시지를 표시
  - 데이터 수집
  - 지표 계산
  - 신호 생성
  - 리포트 생성
  - 전체 파이프라인
- 종목 1개만 선택해도 동일한 배치 흐름으로 사용 가능
- `수집 조회 기간`은 날짜 범위 캘린더로 시작일과 종료일을 선택하며, 선택한 기간은 내부 수집 일수로 변환해 실행함
- 기본 조회 기간은 최근 365일이며, CLI와 정기 수집 설정의 생략 기본값도 동일하게 365일로 맞춤
- `리포트 생성` / `전체 파이프라인`은 Discord delivery-aware 집계를 사용함
  - all sent -> `success`
  - one or more `skipped` / `failed` -> `warning`
  - report save failure -> `error`
- Discord warning은 unrelated collect/indicator/signal batch semantics로 퍼지지 않음
- `데이터 수집`에서 선택 종목이 모두 실패하면 error로 표시하고 "최신 데이터가 저장되지 않았습니다"를 안내함
- `전체 파이프라인`에서 수집 성공 종목이 0개면 지표/신호/리포트 단계를 실행하지 않고 "리포트를 갱신하지 않았습니다"를 안내함
- 리포트 날짜는 실행일이 아니라 최신 신호/지표 기준 거래일이므로, 최신 수집분 반영은 `전체 파이프라인` 또는 `데이터 수집 -> 지표 계산 -> 신호 생성 -> 리포트 생성` 순서가 필요함

## 현재 투자 리포트 탭 동작

- 상단의 `해석 모아보기 열기` 토글을 켜면 현재 검색 조건에 맞는 리포트들의 최종 의견과 전략별 판단을 카드형으로 비교 가능
- 해석 모아보기는 별도 sidebar 메뉴가 아니라 투자 리포트 탭 내부 기능으로 유지
- 해석 모아보기 카드와 전략 판단 근거는 긴 텍스트가 겹치지 않도록 줄바꿈 가능한 카드 UI를 사용
- 리포트 후보 카드를 먼저 보여주고 카드의 `이 종목 보기` 버튼 또는 선택 컨트롤로 종목/리포트를 고른 뒤, 본문에는 선택된 1건만 focus card로 표시
- 후보 카드의 `이 종목 보기` 버튼을 누르면 선택된 본문 위치로 자동 스크롤
- 선택된 리포트 아래에서 차트와 상세 데이터 표를 계속 확인 가능
- stock dataset 차트는 기존 저장 `daily_prices_indicators` / `daily_prices`와 `investor_daily`를 조합한 전문가형 주가 차트로 우선 표시됨
- 전문가형 차트는 캔들 + 이동평균선, 거래량, RSI 14, 선택적 투자자 수급 panel을 함께 제공함
- 차트는 `일봉` / `주봉` / `월봉` selector, 날짜 기준 shared x-axis hover / zoom, 세로 crosshair를 지원함
- 빠른 기간 선택(`1개월`, `3개월`, `6개월`, `1년`, `전체`)과 직접 시작일/종료일 선택을 지원하며 새 수집/API 호출은 추가하지 않음
- 빠른 선택과 직접 조회 기간 표시는 같은 최종 유효 기간으로 동기화됨
- 전문가형 차트는 확대된 세로 높이/패널 간격을 사용하며 가격 y축과 hover 가격은 천 단위 쉼표 형식으로 표시함
- 투자자 수급 데이터가 없으면 차트는 계속 표시되고 `수급 데이터 없음`을 안내함
- `final_opinion`과 별도로 `RSI 전략` / `추세 필터 전략` / `평균회귀 전략`의 직접 판단과 이유를 한글로 함께 표시
- `final_opinion`과 전략 신호가 엇갈리면 리포트 본문에 단독 매매 판단을 피하도록 주의 문구를 표시
- 후보 카드에 현재 검색 결과 수, 한글 요약, 기준일만 간결하게 표시
- 선택된 종목을 즐겨찾기로 저장/해제할 수 있음
- 즐겨찾기만 보기와 즐겨찾기 우선 정렬을 지원함
- 별도 `관심종목` 탭에서 리포트가 아직 없는 종목까지 포함한 등록 종목 전체를 드롭다운 조작 없이 카드 보드로 먼저 확인하고 1건씩 본문으로 확인 가능하며 동일한 리포트 카드 기반 전문가형 차트 경로를 그대로 상속함
- 관심종목 카드의 종목명, 코드, 최신 판단, 추세를 한 번에 확인하고 `상세 보기` 버튼으로 선택 본문을 바로 전환 가능
- 즐겨찾기는 DB 기반 단일 watchlist 상태로 저장되며 report `entry_key`가 아니라 `symbol` 기준으로 관리됨
- 같은 DB 볼륨을 유지하는 정상적인 app/container 재시작 후에도 관심종목 상태가 유지됨
- 관심종목은 저장된 snapshot만 조회하며 자동 수집·분석·리포트 생성을 실행하지 않음
- 관심종목 상단에서 가격·수급·분석·신호·리포트의 종목별 기준일을 비교해 `최신`, `분석 갱신 필요`, `데이터 갱신 필요` 상태와 사유를 표시함
- 갱신이 필요한 관심종목은 버튼 한 번으로 `데이터 갱신` 탭의 선택 목록에 채워지며, 사용자가 필요한 단계 또는 전체 파이프라인을 명시적으로 실행함
- 홈은 외부 API 호출이나 수집·분석 파이프라인을 실행하지 않으며, 기준일이 오래되었거나 검증에 실패한 경우 `데이터 갱신` 또는 `시스템 검증`으로 이동하도록 안내함
- 데이터 갱신 중 KIS `search-stock-info`처럼 선택적 종목 기본정보 조회가 실패해도 해당 오류를 격리하고 가격·수급·지표·신호·리포트 갱신은 계속 진행함
- 전역 글꼴 스타일을 변경할 때 Streamlit `stIconMaterial`, status, expander의 Material Symbols 폰트와 ligature 설정을 반드시 보존해 아이콘 이름이 일반 텍스트로 노출되지 않도록 함

## 현재 용어 해설 탭 동작

- sidebar 탭 목록에 `용어 해설` 탭이 포함됨
- 리포트, 전략, 지표, 수급, 데이터 용어를 검색어와 분류로 조회 가능
- 기본 용어와 `DashboardDataService.COLUMN_META` 컬럼 설명을 함께 사용해 용어집을 구성
- 처음 볼 때 추천 순서는 expander가 아니라 항상 보이는 안내 카드로 표시
- 화면 내 안내 문구는 화살표/아이콘 문자가 텍스트처럼 노출되지 않도록 일반 문장 중심으로 유지

## 현재 데이터 보기 탭 차트 동작

- 종목 선택 기반 summary-first 흐름은 유지
- 상세 expander 안 차트는 `투자 리포트` 탭과 동일한 공용 렌더러를 사용함
- `daily_prices` / `daily_prices_indicators`는 전문가형 주가 차트로 우선 표시되고, 다른 dataset은 기존 generic 차트 흐름을 유지함
- 전문가형 차트는 캔들 + 이동평균선, 거래량, RSI 14, 선택적 투자자 수급 panel과 `일봉` / `주봉` / `월봉` selector를 제공함
- hover 시 날짜 기준으로 visible series 값을 함께 확인하고 shared x-axis zoom을 사용함
- 빠른 기간 선택과 직접 date range 선택을 모두 지원하고 두 기간 표시는 같은 최종 유효 기간으로 동기화되며, Plotly 사용이 불가능한 환경에서는 Altair fallback으로 표시함
- 가격 y축과 hover 가격은 천 단위 쉼표 형식으로 표시함
- generic Data tab은 종목별 최신 artifact 1건만 보일 수 있으므로, 같은 세션 안 여러 전략 비교 기준 화면은 `백테스트` 탭으로 본다

## 현재 백테스트 탭 동작

- sidebar 탭 목록에 전용 `백테스트` 탭이 포함됨
- 흐름은 `준비 확인 -> 준비 실행 -> 백테스트 실행 -> 결과 확인`으로 고정
- 준비용 수집 조회 기간은 날짜 범위 캘린더로 선택하고, 선택 기간을 수집 일수로 변환해 준비 실행에 사용
- `준비 실행`은 버튼을 눌렀을 때만 아래 순서를 수행함
  - 데이터 수집
  - 지표 계산
  - 골든크로스 신호 생성
- 준비 상태 panel은 선택한 종목/전략 조합별 카드와 표로 아래를 표시함
  - 준비 완료 여부
  - 차단 사유
  - 전체 실행 가능 여부
- 선택한 미준비 전략은 실행 직전 warning과 함께 차단됨
- 전략을 두 개 이상 선택하면 AND(기본), OR, 가중치 조합을 선택해 개별 전략 결과와 조합 결과를 같은 가정으로 함께 비교함
  - AND는 모든 전략이 같은 방향일 때만 신호를 내며, 불일치는 관망으로 처리함
  - OR은 반대 신호가 없고 한 전략이라도 같은 방향일 때만 신호를 내며, 매수·매도 충돌은 관망으로 처리함
  - 가중치는 전략별 0.1~3.0 입력값으로 매수는 더하고 매도는 빼며, 0점은 관망으로 처리함. 초기값 1.0은 성과 예측이 아닌 중립 비교 기준임
- 결과 카드·비교표·거래 로그와 저장 이력에서 적용한 조합 규칙과 가중치를 확인할 수 있음
- 현재 포함된 전략 adapter/registry는 정확히 7개
  - `golden-cross`
  - `rsi`
  - `trend-filter`
  - `mean-reversion`
  - `disparity`
  - `momentum`
  - `investor-flow-custom`
- 결과 화면은 아래 핵심 섹션으로 구성
  - 전략 요약 카드
  - 전략 비교표
  - 거래 순서 누적 수익률 차트
  - 일별 평가금액 곡선
  - 포트폴리오 집계(다종목 실행 시)
  - 거래 로그
- 두 종목 이상을 실행하면 이번 세션 결과에서 전략별 포트폴리오를 별도로 확인할 수 있음
  - 동일 비중으로 최초 배분하고 리밸런싱하지 않으며, 실제 주문 비중 추천은 하지 않음
  - 공통 거래일만 사용하고 첫 공통 거래일에 종목별 평가액을 같은 초기자금 기준으로 재설정함
  - 일별 평가금액이 부족한 종목의 제외 사유, 종목별 비중, 수익 기여도와 포트폴리오 평가금액 곡선을 표시함
  - 저장 이력은 기존 단일 실행 결과 복원 범위를 유지하고, 포트폴리오 집계는 이번 세션 다종목 실행 결과에서 제공함
- 이번 범위는 아래를 포함하지 않음
  - 주문/체결/리스크 관리
  - 새 DB schema
  - 새 dependency 추가

## 현재 대시보드 테마 / 폰트 동작

- 전역 Streamlit 테마는 `.streamlit/config.toml`에서 dark base로 고정
- 현재 팔레트 토큰
  - `primaryColor`: `#38bdf8`
  - `backgroundColor`: `#050816`
  - `secondaryBackgroundColor`: `#111827`
  - `textColor`: `#f8fafc`
  - `borderColor`: `#475569`
- 세부 CSS는 `src/invest_bot/dashboard/streamlit_styles.py`에 중앙화되어 있음
- 좌측 sidebar 메뉴는 둥근 버튼 박스/원형 배경 없이 텍스트만 보이고, 선택된 메뉴는 왼쪽 얇은 강조선으로 표시함
- sidebar의 `화면 이동` 보조 라벨은 제거해 메뉴 텍스트만 남김
  - 기존 warm beige / teal 계열을 제거
  - high-contrast dark navy / slate 기반 terminal-like 대비로 정리
  - sidebar / hero / card / summary box / tabs / semantic badge 명도 대비를 더 강하게 재조정
- 한글 가독성 우선 폰트 스택을 사용함
  - 기본: `Pretendard`, `Noto Sans KR`, `Apple SD Gothic Neo`, `Malgun Gothic`, system sans fallback
  - 보조 label / numeric fallback: `Inter`, `IBM Plex Sans`
- 아이콘 폰트 충돌을 막기 위한 Material Symbols override는 유지함
- 이번 변경 범위
  - presentation / theme / font 정리에 한정
  - 데이터 수집 / 전략 판단 / 리포트 생성 로직은 변경하지 않음
  - 새로운 탭, 컨트롤, 기능은 추가하지 않음

## 이번 세션 작업 요약 (2026-07-14)

- `src/invest_bot/dashboard/streamlit_styles.py` 수정
  - 저대비 teal/navy 중심 스타일을 high-contrast dark navy / slate terminal palette로 교체
  - sidebar / hero / card / summary box / tabs / semantic badge contrast를 더 선명하게 재정리
  - Korean readability-first font stack과 numeric fallback stack을 적용
  - Material Symbols override를 유지
- 문서 동기화
  - 리포트 해석 / 데이터 탐색 / 관심종목의 전문가형 주가 차트 동작을 현재 구현 기준으로 정리
  - 저장 데이터 재사용(`daily_prices_indicators` / `daily_prices` / `investor_daily`)과 `수급 데이터 없음` fallback을 명시
- `.streamlit/config.toml` 수정
  - Streamlit base theme를 dark로 고정
  - `primaryColor`, `backgroundColor`, `secondaryBackgroundColor`, `textColor`, `borderColor` 토큰을 현재 palette로 정리
- `tests/test_streamlit_dashboard.py` 보강
  - 테마 / 폰트 / config 회귀 검증을 추가
- 검증
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_charts.py src/invest_bot/dashboard/streamlit_state.py src/invest_bot/dashboard/streamlit_reports.py src/invest_bot/dashboard/streamlit_data.py src/invest_bot/dashboard/streamlit_watchlist.py tests/test_streamlit_dashboard.py`
  - 결과: `PASS`
  - `PYTHONPATH=src:. .venv/bin/pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `78 passed in 0.70s`
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_styles.py tests/test_streamlit_dashboard.py`
  - 결과: `PASS`
  - `git diff --check -- .streamlit/config.toml src/invest_bot/dashboard/streamlit_styles.py tests/test_streamlit_dashboard.py docs/tasks/04_dashboard.md docs/operations/streamlit_dashboard_refactor.md`
  - 결과: `PASS`


## 이번 세션 작업 요약 (2026-07-05)

- `streamlit_charts.py`를 공통 인터랙티브 차트 경로로 확장
  - Plotly 우선 렌더링 도입
  - Altair fallback 유지
  - 날짜 기준 unified hover / vertical crosshair 적용
- 조회 기간 상태 helper 추가
  - `resolve_range_state`
  - `apply_time_window`
  - preset / custom date range session-state 동기화
- preset 변경 후 다음 rerun에서 stale date widget state가 다시 기간을 덮지 않도록 보정
- 선택된 조회 기간이 차트 빌더 내부에서 다시 90개 포인트로 축소되지 않도록 수정
- `requirements.txt`에 `plotly>=6.0,<7.0` 반영
- `tests/test_streamlit_dashboard.py` 보강
  - range state 초기화 / preset sync / custom authority
  - full filtered-range preservation
  - stale widget-state reset
  - Plotly 경로 렌더링 검증
- 검증
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_charts.py src/invest_bot/dashboard/streamlit_data.py src/invest_bot/dashboard/streamlit_reports.py tests/test_streamlit_dashboard.py`
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `50 passed in 0.65s`

## 이번 세션 작업 요약 (2026-07-06)

- `streamlit_dashboard.py` 수정
  - `AppSettings.from_file()`를 1회만 생성
  - 동일 `settings` 인스턴스를 `DashboardDataService(settings=settings)`와 `render_actions_tab(..., settings=settings, ...)`에 함께 주입
- `streamlit_actions.py` 수정
  - report/full-pipeline 경로만 Discord delivery-aware aggregation 사용
  - `리포트 생성`은 batch path에서 `delivery_target="discord"` opt-in
  - `전체 파이프라인`도 report 단계에서만 Discord opt-in
  - partial delivery는 `warning`으로 요약
- `streamlit_layout.py` 수정
  - `warning` feedback branch 추가
- `tests/test_streamlit_dashboard.py` 보강
  - report batch warning
  - full pipeline warning
  - warning render branch
  - settings injection path 회귀 검증
- 검증
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `57 passed in 0.66s`

## 이번 세션 작업 요약 (2026-07-03)

- 관심종목 persistence를 로컬 JSON에서 DB 기반 단일 watchlist로 전환
- `report_favorite_symbols` 테이블과 Alembic migration 추가
- `ReportFavoritesStore`를 DB-backed thin adapter로 전환
- 기존 `ReportFavoritesStore(Path(...))` 호출 형태 호환 유지
- duplicate insert race 시 `IntegrityError` 대신 `False`를 반환하도록 repository 보강
- 자동 JSON backfill/import는 이번 1차 범위에서 제외
- user/account ownership 없는 단일 global symbol watchlist 범위 유지
- 검증
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_report_favorites.py tests/test_init_db_script.py tests/test_streamlit_dashboard.py -q`
  - 결과: `51 passed in 1.64s`
  - `docker compose` 기준 web recreate 이후에도 `['005930']` 유지 확인
  - `curl http://127.0.0.1:8000` → `HTTP/1.1 200 OK`

## 이번 세션 작업 요약 (2026-06-28)

- `streamlit_actions.py` 수정
  - `한 종목` 섹션 제거
  - `데이터 갱신` 탭을 여러 종목 기준 배치 실행 흐름으로 단순화
  - `데이터 수집`, `지표 계산`, `신호 생성`, `리포트 생성`, `전체 파이프라인`을 모두 선택 종목들에 대해 실행 가능하게 정리
- `streamlit_reports.py`, `streamlit_formatters.py` 수정
  - `투자 리포트` 탭 상단 metrics strip 제거
  - 전략 판단 텍스트에 green/red/black 상태 색상 적용
- `streamlit_data.py` 수정
  - `원본 데이터 / 분석 데이터` 이원 진입 제거
  - 종목 선택 기반 summary-first 데이터 탐색 흐름으로 재구성
  - 차트/전체 표/컬럼 설명은 expander 아래로 이동
- `tests/test_streamlit_dashboard.py` 보강
  - 배치 실행 구조, report top metrics 제거, 색상 contract, symbol-first data flow, HTML escaping 회귀 검증 추가
- 검증
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile src/invest_bot/dashboard/streamlit_actions.py src/invest_bot/dashboard/streamlit_reports.py src/invest_bot/dashboard/streamlit_formatters.py src/invest_bot/dashboard/streamlit_data.py tests/test_streamlit_dashboard.py`
  - `PYTHONPYCACHEPREFIX=/private/tmp/pycache .venv/bin/python -m pytest tests/test_streamlit_dashboard.py -q`
  - 결과: `39 passed in 0.48s`

## 현재 잔여 작업

- 사용자/account ownership이 필요한 shared watchlist 확장 여부 결정
- 브라우저 세션을 넘어서는 사용자별 화면 설정 저장 매체·계정 정책 결정

## 접속 정보

대시보드:

```text
http://127.0.0.1:8000
```

## 관련 파일

- [`service.py`](../../src/invest_bot/dashboard/service.py)
- [`streamlit_dashboard.py`](../../src/invest_bot/dashboard/streamlit_dashboard.py)
- [`streamlit_reports.py`](../../src/invest_bot/dashboard/streamlit_reports.py)
- [`streamlit_watchlist.py`](../../src/invest_bot/dashboard/streamlit_watchlist.py)
- [`report_favorites.py`](../../src/invest_bot/dashboard/report_favorites.py)
- [`run_dashboard.py`](../../scripts/run_dashboard.py)
- [`run_streamlit_dashboard.py`](../../scripts/run_streamlit_dashboard.py)
