# Python Runtime And Test Guide

## Runtime rule

- Python 관련 명령은 저장소 내부 `.venv`에서 실행한다.
- 전역 Python 또는 시스템 site-packages에 의존하지 않는다.

## Environment bootstrap

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## Test sequence

1. 설정/compose/bootstrap 같은 경계 파일을 바꾼 경우, 먼저 대상 테스트만 실행한다.
2. 변경 범위가 맞으면 전체 `pytest`를 실행한다.
3. 대시보드에서 테스트 결과를 읽어야 하면 `scripts/run_tests.py`를 사용해 결과 XML을 다시 생성한다.

추천 명령:

```bash
.venv/bin/python -m pytest tests/test_settings.py tests/test_db_bootstrap.py tests/test_db_migration_artifacts.py
.venv/bin/python -m pytest tests/test_market_report_generator.py tests/test_dashboard_service.py
.venv/bin/python -m pytest
```

대시보드 리포트 갱신:

```bash
.venv/bin/python scripts/run_tests.py
```

## Delivery rule

- commit 전에 변경 결과를 markdown으로 정리한다.
- 보고서에는 기능별 목적, 변경 파일, 핵심 변경 내용, 검증 결과, 남은 리스크를 포함한다.

## Current verification baseline

- 2026-06-07 기준 `.venv`는 Python 3.13으로 맞춰져 있다.
- 같은 날짜 기준 전체 테스트 스위트 `44 passed`를 확인했다.
