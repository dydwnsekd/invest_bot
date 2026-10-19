"""Actual action renderer with synthetic symbols and stubbed execution boundaries."""


def render_action_fixture(webhook="configured", delivery="sent", collection="all"):
    from contextlib import ExitStack
    from types import SimpleNamespace
    from unittest.mock import patch

    import streamlit as st

    from invest_bot.config.settings import AppSettings
    from invest_bot.dashboard import streamlit_actions as actions
    from invest_bot.dashboard.streamlit_layout import render_action_feedback
    from invest_bot.dashboard.streamlit_styles import apply_custom_style
    from invest_bot.market.symbol_lookup import SymbolEntry

    st.set_page_config(page_title="G06a 가상 실행 검증", layout="wide")
    apply_custom_style()
    st.caption("가상 데이터 검증: 실행 작업은 기록만 하며 외부로 전송하지 않습니다.")
    configured = st.toggle("가상 Discord 설정", value=webhook == "configured")
    urls = {"configured": "https://example.invalid/webhooks/synthetic-token", "empty": "", "whitespace": "  "}
    url = urls[webhook] if configured == (webhook == "configured") else urls["configured" if configured else "empty"]
    settings = AppSettings(discord_webhook_url=url)
    calls = st.session_state.setdefault("g06a_calls", [])

    def collect(symbols, days):
        calls.append(("collect", tuple(symbols), days))
        successful = symbols if collection == "all" else symbols[:1] if collection == "partial" else []
        return {
            "successful_symbols": successful,
            "success_count": len(successful),
            "failed_count": len(symbols) - len(successful),
        }

    def report(symbol, *, delivery_target, settings):
        calls.append(("report", symbol, delivery_target, bool(settings.discord_webhook_url.strip())))
        status = delivery if settings.discord_webhook_url.strip() else "skipped"
        detail = "HTTP 500" if status == "failed" else "Discord webhook URL is not configured." if status == "skipped" else ""
        return {"symbol": symbol, "delivery": {"status": status, "error_detail": detail}}

    lookup = SimpleNamespace(list_entries=lambda: [
        SymbolEntry(symbol="005930", symbol_name="삼성전자"),
        SymbolEntry(symbol="000660", symbol_name="SK하이닉스"),
        SymbolEntry(symbol="035420", symbol_name="NAVER"),
        SymbolEntry(symbol="005380", symbol_name="현대차"),
    ])

    with ExitStack() as stack:
        stack.enter_context(patch.object(actions, "collect_market_data_for_symbols", collect))
        stack.enter_context(patch.object(actions, "generate_indicators_for_symbol", lambda symbol: calls.append(("indicators", symbol))))
        stack.enter_context(patch.object(actions, "generate_golden_cross_signals_for_symbol", lambda symbol: calls.append(("signals", symbol))))
        stack.enter_context(patch.object(actions, "generate_market_report_for_symbol", report))
        render_action_feedback()
        actions.render_actions_tab(lookup, None, settings=settings, render_schedule_status_panel=lambda _: None)
    st.caption(f"가상 작업 호출 {len(calls)}회 · 실제 API·DB·Discord 호출 없음")
