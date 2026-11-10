"""Baseline-compatible G06c UI: real router, QA02 SQLite, no operational jobs.

Run with AppTest or let main launch this file for browser comparison. Seed once
per session. Default backtest is Samsung + RSI/Golden Cross (two readiness
cards and three result cards, including AND). Selecting Trend Filter after an
explicit run gives three readiness cards while retaining the three saved-in-
memory result cards; it does not execute again. No result is persisted.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from datetime import date
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from sqlalchemy import Engine, event

from tests.qa02_dashboard_fixture import NAMES, QA02Harness
from invest_bot.dashboard import streamlit_actions as actions
from invest_bot.dashboard import streamlit_backtest as backtest
from invest_bot.dashboard import streamlit_dashboard as dashboard


class G06cHarness(QA02Harness):
    def __init__(self, directory: Path | None = None):
        super().__init__(directory or Path(tempfile.mkdtemp(prefix="g06c-synthetic-", dir=ROOT.parent)))
        self.runner_calls = []
        self.write_attempts = []
        self.sql_context = "screen"
        self.classified_attempts = []
        self.seed_count = 1

    def _seed(self):
        super()._seed()
        # Keep all four QA02 trust scenarios, including Samsung's 4/5-day lag.
        # Align the stored signal to the actual indicator input, not raw prices.
        for symbol in NAMES:
            indicator = self.prices(symbol)
            if symbol == "005930":
                indicator = indicator.iloc[:-1]
            signal = indicator[["date", "close"]].copy()
            signal["symbol"] = symbol
            signal["signal"] = ["hold", "buy", "hold", "sell", "hold"][:len(signal)]
            self.storage.save("golden_cross_signals", f"{symbol}_signals.csv", signal)

    @contextmanager
    def observe(self):
        events = []
        def deny_write(conn, _cursor, statement, _parameters, _context, _many):
            if str(conn.engine.url) == self.database_url:
                verb = statement.lstrip().split(None, 1)[0].upper()
                if verb == "SELECT":
                    events.append({"phase": self.phase, "context": self.sql_context, "statement": statement})
                if verb in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER"}:
                    self.write_attempts.append(verb)
                    raise AssertionError(f"G06c render attempted SQLite write: {verb}")
        event.listen(Engine, "before_cursor_execute", deny_write)
        try:
            with super().observe():
                yield
        finally:
            event.remove(Engine, "before_cursor_execute", deny_write)
            self.classified_attempts.append(events)

    def render(self):
        original_run = backtest.DEFAULT_BACKTEST_RUNNER.run
        original_sources = backtest._load_backtest_inputs
        original_history = backtest._render_backtest_history_panel

        def classified_read(context, reader, *args, **kwargs):
            previous = self.sql_context
            self.sql_context = context
            try:
                return reader(*args, **kwargs)
            finally:
                self.sql_context = previous

        def counted_run(symbol, rows):
            self.runner_calls.append({"symbol": symbol, "rows": len(rows)})
            return original_run(symbol, rows)

        with ExitStack() as stack:
            stack.enter_context(patch.object(backtest.DEFAULT_BACKTEST_RUNNER, "run", counted_run))
            stack.enter_context(patch.object(backtest, "_load_backtest_inputs", lambda *a, **kw: classified_read("backtest_sources", original_sources, *a, **kw)))
            stack.enter_context(patch.object(backtest, "_render_backtest_history_panel", lambda *a, **kw: classified_read("backtest_history", original_history, *a, **kw)))
            stack.enter_context(patch.object(backtest, "_run_prepare_action", self.forbidden("prepare")))
            stack.enter_context(patch.object(dashboard, "_refresh_home_watchlist_snapshot", self.forbidden("home_refresh")))
            stack.enter_context(patch.object(self.storage, "save", self.forbidden("storage_save")))
            for name in ("collect_market_data_for_symbols", "generate_indicators_for_symbol", "generate_golden_cross_signals_for_symbol"):
                stack.enter_context(patch.object(backtest, name, self.forbidden(name)))
            for name in ("run_collect_action", "run_full_pipeline_action", "run_market_report_batch_action", "run_batch_symbol_action"):
                stack.enter_context(patch.object(actions, name, self.forbidden(name)))
            super().render()
        st.session_state["g06c_measurement"] = {
            **st.session_state["qa02_measurement"],
            "runner_calls": list(self.runner_calls), "write_attempts": list(self.write_attempts),
            "seed_count": self.seed_count,
            "sql_events": self.classified_attempts[-1],
            "source_selects": sum(item["context"] == "backtest_sources" for item in self.classified_attempts[-1]),
            "history_selects": sum(item["context"] == "backtest_history" for item in self.classified_attempts[-1]),
        }


def render_fixture():
    harness = st.session_state.get("qa02_harness")
    if harness is None:
        harness = G06cHarness()
        st.session_state["qa02_harness"] = harness
        st.session_state["backtest_selected_symbols"] = ["005930"]
        st.session_state["backtest_selected_strategies"] = ["rsi", "golden-cross"]
        st.session_state["backtest_prepare_collection_period"] = (date(2025, 10, 22), date(2026, 10, 22))
    harness.render()


if __name__ == "__main__":
    render_fixture()
