"""Synthetic read-only UI for G05b AppTest and local browser verification."""


def render_fixture():
    from contextlib import ExitStack
    from datetime import UTC, date, datetime
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch

    import pandas as pd
    import streamlit as st

    from invest_bot.dashboard import data_status, streamlit_actions, streamlit_overview, streamlit_watchlist
    from invest_bot.dashboard.service import DashboardDataService, DashboardSnapshot, DatasetPreview
    from invest_bot.dashboard.streamlit_reports import render_reports_tab
    from invest_bot.dashboard.streamlit_preferences import restore_dashboard_preference_draft, sync_dashboard_preference_draft
    from invest_bot.dashboard.streamlit_state import DashboardFrameLoader
    from invest_bot.dashboard.streamlit_styles import apply_custom_style
    from invest_bot.db.contracts import DatasetFrameRecord
    from invest_bot.db.repositories import frame_to_json

    class FixtureDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 2)

    names = {"005930": "삼성전자", "000660": "SK하이닉스"}
    st.set_page_config(page_title="G05b 가상 데이터 검증", layout="wide")
    apply_custom_style()
    st.title("G05b · 가상 데이터 검증")
    scenario = st.selectbox("상태 사례", ["분석 지연", "원본 누락", "날짜 불일치", "정상"])
    tabs = ["홈", "투자 리포트", "관심종목", "데이터 갱신"]
    pending = st.session_state.pop("selected_tab", None)
    if pending in tabs:
        st.session_state["fixture_tab"] = pending
    view = st.radio("화면", tabs, horizontal=True, key="fixture_tab")
    # Match the production router: capture the previous view and restore the active view.
    sync_dashboard_preference_draft(st.session_state)
    restore_dashboard_preference_draft(st.session_state, tab_name=view)
    records, raw, processed = [], [], []
    for symbol, name in names.items():
        for dataset in ("daily_prices", "investor_daily_summary", "daily_prices_indicators", "golden_cross_signals", "market_reports"):
            if scenario == "원본 누락" and symbol == "005930" and dataset == "investor_daily_summary":
                continue
            day = "2026-10-02"
            if scenario == "분석 지연" and dataset in ("daily_prices_indicators", "golden_cross_signals", "market_reports"):
                day = "2026-10-01"
            if scenario == "날짜 불일치" and symbol == "005930" and dataset == "market_reports":
                day = "2026-10-05"
            frame = pd.DataFrame([dict(
                date=day, symbol=symbol, symbol_name=name,
                open=99.0, high=103.0, low=98.0, close=101.0, volume=1000.0,
                ma_5=100.0, ma_20=99.0, ma_60=98.0, rsi_14=55.0,
                frgn_ntby_qty=12.0, orgn_ntby_qty=0.0,
                signal="hold", signal_reason="No crossover.",
                final_opinion="watch", summary=f"{name} 가상 리포트",
                trend_state="bullish", golden_cross_signal="hold", investor_flow="supportive",
                rsi_strategy_signal="hold", trend_filter_signal="hold", mean_reversion_signal="hold",
            )])
            filename = f"{symbol}_{dataset}.csv"
            created = datetime(2026, 10, 3, 1, tzinfo=UTC)
            records.append(DatasetFrameRecord(
                dataset=dataset, filename=filename, symbol=symbol, row_count=1,
                frame_json=frame_to_json(frame), created_at=created,
            ))
            preview = DatasetPreview(
                name=dataset, display_name=dataset, path=Path(filename),
                row_count=1, columns=list(frame.columns), summary="가상 검증 데이터",
                purpose="가상 화면 검증", first_look="원본·판단 날짜",
                symbol=symbol, symbol_name=name, recommended_columns=["date"], created_at=created,
            )
            (raw if dataset in ("daily_prices", "investor_daily_summary") else processed).append(preview)
    snapshot = DashboardSnapshot(raw, processed, tuple(records))
    service = DashboardDataService(raw_root="/virtual/g05b/raw", processed_root="/virtual/g05b/processed")
    loader = DashboardFrameLoader(service, snapshot.latest_records)
    counts = st.session_state.setdefault("g05b_counts", {})

    def forbidden(name):
        def fail(*args, **kwargs):
            counts[name] = counts.get(name, 0) + 1
            raise AssertionError(f"Read-only screen called {name}")
        return fail

    service.get_dataset_storage = forbidden("storage")
    class Favorites:
        def load_symbols(self):
            return set(names)
        def toggle(self, symbol):
            return True

    with ExitStack() as stack:
        stack.enter_context(patch.object(data_status, "date", FixtureDate))
        stack.enter_context(patch.object(streamlit_overview, "date", FixtureDate))
        for name in (
            "run_collect_action", "run_full_pipeline_action", "run_market_report_batch_action",
            "generate_indicators_for_symbol", "generate_golden_cross_signals_for_symbol", "generate_market_report_for_symbol",
        ):
            stack.enter_context(patch.object(streamlit_actions, name, forbidden(name)))
        for name in ("refresh_favorite_symbols_if_needed", "generate_indicators_for_symbol",
                     "generate_golden_cross_signals_for_symbol", "generate_market_report_for_symbol"):
            stack.enter_context(patch.object(streamlit_watchlist, name, forbidden(name)))
        schedule = SimpleNamespace(log_exists=True, last_finished_at="2026-10-03T01:00:00+00:00", recent_entries=[], last_event="", next_run_at="2026-10-04T01:00:00+00:00", last_success_count=2, last_failed_count=0)
        if view == "홈":
            streamlit_overview.render_overview_tab(
                snapshot, service, None, schedule, read_preview_frame=loader.read_preview,
            )
        elif view == "데이터 갱신":
            st.info("상태 안내에서 이동했습니다. 이 검증 화면은 작업을 실행하지 않습니다.")
        else:
            renderer = render_reports_tab if view == "투자 리포트" else streamlit_watchlist.render_watchlist_tab
            renderer(
                snapshot, service, read_preview_frame=loader.read_preview,
                load_indicator_frame_for_symbol=loader.load_indicator,
                load_professional_frame_for_symbol=loader.load_professional,
                favorites_store=Favorites(),
            )
    st.caption(f"조회 중 실행·전송·저장소 추가 조회: {sum(counts.values())}회")
    st.session_state["g05b_snapshot"] = snapshot
