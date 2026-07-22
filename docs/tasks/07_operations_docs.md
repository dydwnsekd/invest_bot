# Task 07. Operations And Docs

## 목표

프로젝트 문서와 운영 안내를 정리해 작업 연속성과 운영 효율을 높인다.

## 완료된 항목

- [x] `README.md` 기본 정리
- [x] `agent.md` 프로젝트 가이드 작성
- [x] project skill 초안 작성
- [x] task 문서 구조 작성
- [x] 지표 설명 가이드 작성
- [x] 시장 리포트 설명 가이드 작성
- [x] 세션 분리 원칙 및 새 세션 프롬프트 문서 작성
- [x] DB 마이그레이션 준비 문서 작성 (`ERD`, `docker-compose` 초안 검토, repository interface 제안 포함)
- [x] Discord 리포트 전달 변경사항 문서 반영

## 남은 항목

- [ ] task 문서 갱신 규칙 정리
- [ ] 수집/분석/대시보드 운영 가이드
- [ ] 로그 확인 가이드
- [ ] 릴리즈/배포 방식 정리

## 이번 세션 문서 갱신 요약 (2026-07-06)

- `README.md`
  - Discord 리포트 전달 1차 범위 추가
  - batch/full-pipeline only, plain-text only, non-blocking failure 정책 반영
- `docs/analysis/market_report_guide.md`
  - Discord 전달 동작과 `sent` / `skipped` / `failed` 상태 설명 추가
  - Discord 메시지에 포함되는 필드 그룹 정리
- `docs/tasks/04_dashboard.md`
  - 작업 실행 탭의 Discord warning/success/error 집계 규칙 추가
  - settings 1회 생성/주입과 warning feedback branch 반영

## 관련 파일

- [`README.md`](../../README.md)
- [`agent.md`](../../agent.md)
- [`codex_session_prompts.md`](../operations/codex_session_prompts.md)
- [`SKILL.md`](../../skills/invest-bot-reference-reader/SKILL.md)
- [`indicator_guide.md`](../analysis/indicator_guide.md)
- [`market_report_guide.md`](../analysis/market_report_guide.md)
- [`db_migration_plan.md`](../operations/db_migration_plan.md)
