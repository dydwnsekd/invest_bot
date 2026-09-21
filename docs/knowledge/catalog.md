# 문서 등록부

이 등록부는 [OKF](../../OKF.md)의 문서 ID·역할·상태를 관리하는 단일 목록이다. 날짜가 있는 보고서를 수정일만 보고 현재 규칙으로 승격하지 않는다. 관리 역할은 책임 분야이며 별도 에이전트 실행을 요구하지 않는다.

## 진입점과 규약

| ID | 문서 | 종류 | 상태 | 관리 역할 · 담당 주제 |
| --- | --- | --- | --- | --- |
| D-OKF | [OKF](../../OKF.md) | policy | active | 통합 · 지식 관리 규약 |
| D-HOME | [지식 홈](../README.md) | index | active | 통합 · 질문별 탐색 |
| D-GUIDE | [프로젝트·OKF HTML 안내서](../project-guide.html) | index | active | 통합 · 전체 구조·OKF 이해; 작성 시점의 설명용 요약 |
| D-CATALOG | [문서 등록부](catalog.md) | index | active | 통합 · 문서 역할과 상태 |
| D-CONCEPTS | [개념 지도](concepts.md) | concept | active | 통합 · 핵심 개념과 구현 근거 |
| D-TEMPLATE | [작성 양식](template.md) | policy | active | 통합 · 새 문서 작성 |
| D-ARCHIVE | [기록 보관 안내](../archive/README.md) | index | active | 통합 · 과거 기록 읽기 |
| D-DECISION-0001 | [OKF 도입 결정](../decisions/0001-local-okf.md) | decision | active | 통합 · 이번 구조를 선택한 이유 |
| D-README | [프로젝트 README](../../README.md) | runbook | active | 통합 · 실행·설정 안내; 날짜별 업데이트는 과거 기록 |
| D-AGENT | [agent 가이드](../../agent.md) | policy | active | 통합 · 작업 규칙 |
| D-DESIGN | [DESIGN](../../DESIGN.md) | reference | active | 대시보드 · 의도한 제품 UX |

## 현재 기능과 작업 상태

| ID | 문서 | 종류 | 상태 | 관리 역할 · 담당 주제 |
| --- | --- | --- | --- | --- |
| D-STATUS | [task 요약](../tasks/00_summary.md) | status | active | 통합 · 기능별 완료·대기; 날짜별 과거 결과 구분 |
| D-ENV | [환경](../tasks/01_environment.md) | status | active | 운영 · 환경 작업 |
| D-DATA | [수집](../tasks/02_data_collection.md) | status | active | 데이터 · 수집 작업 |
| D-ANALYSIS | [분석](../tasks/03_analysis.md) | status | active | 퀀트 · 지표 작업 |
| D-DASHBOARD | [대시보드](../tasks/04_dashboard.md) | status | active | 대시보드 · 현재 UI 기능; 날짜별 작업은 기록 |
| D-BACKTEST | [전략·백테스트](../tasks/05_strategy_backtest.md) | status | active | 퀀트 · 구현된 전략과 백테스트 규칙 |
| D-TRADING | [주문·리스크](../tasks/06_trading_risk.md) | plan | proposed | 거래 · 아직 구현하지 않은 주문 기능 |
| D-OPS | [운영](../tasks/07_operations_docs.md) | runbook | active | 운영 · 초기화 모드와 로그 |
| D-SESSIONS | [개선 작업 추적](../operations/improvement_sessions_2026-09-13.md) | status | active | 통합 · 역할별 단일 작업·순차 실행 |
| D-INDICATORS | [지표 가이드](../analysis/indicator_guide.md) | reference | active | 퀀트 · 지표 의미 |
| D-REPORT | [리포트 가이드](../analysis/market_report_guide.md) | reference | active | 퀀트 · 기준일·출력 필드·해석 |
| D-RUNTIME | [Python·테스트](../operations/python_runtime_and_test_guide.md) | runbook | active | QA · 검증 실행법; 옛 수치는 해당 시점 기록 |
| D-PROMPTS | [세션 프롬프트](../operations/codex_session_prompts.md) | runbook | active | 통합 · 담당 작업 시작법 |

## 구조 문서와 제안

| ID | 문서 | 종류 | 상태 | 관리 역할 · 담당 주제 |
| --- | --- | --- | --- | --- |
| D-DB-SCHEMA | [DB schema](../architecture/db_schema.md) | reference | review-required | 데이터 · placeholder 쓰기 정책·관심종목 테이블 정합성 필요 |
| D-DB-ERD | [DB ERD](../architecture/db_migration_erd.md) | reference | review-required | 데이터 · schema와 같은 차이, 전체 최신 ERD 아님 |
| D-REPOSITORIES | [repository 계약](../architecture/repository_interfaces.md) | reference | review-required | 데이터 · 쓰기 정책은 실제 계약·구현과 대조 |
| D-DB-PLAN | [DB 구현 계획](../architecture/db_migration_plan.md) | plan | proposed | 데이터 · 미완료 구조 개편 제안 |
| D-DB-OPS-PLAN | [DB 운영 계획](../operations/db_migration_plan.md) | plan | proposed | 운영 · 구조 개편의 운영 관점, 현재 구현 명세 아님 |
| D-DB-OPS-ERD | [운영 ERD](../operations/db_erd.md) | reference | review-required | 운영 · 최신 테이블·쓰기 경계 재검토 필요 |
| D-STRATEGY-REFERENCE | [전략 후보 설명](../strategies/01_reference_strategies.md) | reference | review-required | 퀀트 · 원본 reference 미포함; 아이디어 설명 재검토, 구현 여부는 D-BACKTEST |
| D-PROJECT-SKILL | [프로젝트 참조 skill](../../skills/invest-bot-reference-reader/SKILL.md) | policy | review-required | 통합 · 옛 절대 경로·외부 reference 디렉터리 가정 재검토 |
| D-PROJECT-RULES | [프로젝트 참조 규칙](../../skills/invest-bot-reference-reader/references/project-rules.md) | policy | review-required | 통합 · 참조 skill의 기존 보조 지침 |

DB 문서의 구체적인 차이와 현재 확인 경로는 [개념 지도](concepts.md#저장-경계와-알려진-문서-차이)에 있다. 등록부의 분류로 제품 정책을 새로 승인하거나 구현을 바꾸지는 않는다.

## 과거 기록

| ID | 문서 | 종류 | 상태 | 관리 역할 · 담당 주제 |
| --- | --- | --- | --- | --- |
| H-DB-0606 | [DB 변경 보고](../operations/db_migration_change_report_2026-06-06.md) | evidence | historical | 데이터 · 6월 migration 작업 |
| H-WRITE-0607 | [write path 보고](../operations/db_write_path_change_report_2026-06-07.md) | evidence | historical | 데이터 · 6월 저장 경로 작업 |
| H-HANDOFF-0607 | [OMX 인계](../operations/next_steps_omx_handoff_2026-06-07.md) | plan | historical | 통합 · 과거 권장 작업과 런타임 명령 |
| H-QA-0615 | [QA 보고](../ultraqa-report-2026-06-15.md) | evidence | historical | QA · 당시 검증 |
| H-DASHBOARD-REFACTOR | [대시보드 리팩터링](../operations/streamlit_dashboard_refactor.md) | evidence | historical | 대시보드 · 날짜별 작업 이력 |
| H-DASHBOARD-PLAN | [완료된 0~7단계](../tasks/06_dashboard_execution_plan.md) | plan | historical | 대시보드 · 완료 단계의 배경과 검증 |
| H-STRATEGY-CANDIDATES | [전략 후보 요약](../strategies/00_summary.md) | plan | historical | 퀀트 · 초기 구현 후보·가능성 |
| H-STRATEGY-FOLLOWUP | [이전 후속 전략](../strategies/02_deferred_strategies.md) | plan | historical | 퀀트 · 6월 당시 구현·후속 목록 |
| H-DATA-0913 | [데이터 개선 보고](../operations/session_reports/2026-09-13_data.md) | evidence | historical | 데이터 · 담당 브랜치와 후속 검증 |
| H-QUANT-0913 | [퀀트 개선 보고](../operations/session_reports/2026-09-13_quant.md) | evidence | historical | 퀀트 · 담당 브랜치와 9월 16일 통합 검증 |
| H-OPS-0913 | [운영 개선 보고](../operations/session_reports/2026-09-13_operations.md) | evidence | historical | 운영 · 담당 브랜치 검증 |
| H-QA-0913 | [QA 개선 보고](../operations/session_reports/2026-09-13_qa.md) | evidence | historical | QA · 담당 브랜치 검증과 당시 환경 제약 |
| H-DASHBOARD-0919 | [대시보드 검토 보고](../operations/session_reports/2026-09-19_dashboard.md) | evidence | historical | 대시보드 · 9월 19일 미커밋 검토본의 변경·측정·검증 |

## 대체 관계와 유지 규칙

- H-STRATEGY-CANDIDATES와 H-STRATEGY-FOLLOWUP의 현재 구현 상태는 D-BACKTEST가 대체한다(`superseded-by`). 후보 아이디어 자체를 삭제한 것은 아니다.
- H-HANDOFF-0607의 다음 작업 순서는 D-SESSIONS가 대체한다.
- H-DASHBOARD-PLAN의 완료 이력과 현재 대시보드 후속 작업은 서로 다른 작업이다. 현재 상태는 D-DASHBOARD와 D-SESSIONS에서 확인한다.
- 새 관리 문서는 이 목록에 한 번만 등록한다. 현재 관리 대상은 루트의 README·agent·DESIGN·OKF, `docs/**/*.md`, `docs/project-guide.html`, 프로젝트 참조 skill의 Markdown이다. 외부 의존성 문서와 임시 산출물은 포함하지 않는다.
