from __future__ import annotations

import pandas as pd
import streamlit as st

from invest_bot.dashboard.service import TestReportPreview


def render_test_tab(test_report: TestReportPreview | None) -> None:
    st.markdown('<h3 class="section-title">검증 상태</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">대시보드와 파이프라인 변경이 기존 동작을 깨지 않았는지 최근 테스트 결과로 확인합니다.</div>',
        unsafe_allow_html=True,
    )

    if test_report is None:
        st.info("저장된 pytest 결과가 없습니다. `python scripts/run_tests.py` 실행 후 다시 확인해 주세요.")
        return

    metric_columns = st.columns(5)
    metric_columns[0].metric("전체", test_report.total)
    metric_columns[1].metric("통과", test_report.passed)
    metric_columns[2].metric("실패", test_report.failed)
    metric_columns[3].metric("스킵", test_report.skipped)
    metric_columns[4].metric("에러", test_report.errors)

    with st.container(border=True):
        st.markdown("#### 최근 테스트 결과")
        st.caption(test_report.command)
        failed_cases = [case for case in test_report.test_cases if case.status != "passed"]
        if not failed_cases:
            st.success("현재 저장된 테스트 결과에는 실패가 없습니다.")
        else:
            for case in failed_cases:
                st.error(f"{case.name}: {case.detail}")

        if st.toggle("전체 테스트 케이스 보기", key="toggle_test_cases"):
            frame = pd.DataFrame(
                [{"name": case.name, "status": case.status, "detail": case.detail} for case in test_report.test_cases]
            )
            st.dataframe(frame, width="stretch", hide_index=True)
