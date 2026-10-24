"""Independent QA02 app: real main/router/renderers, synthetic SQLite, no real jobs.

Can be launched by the parent for desktop/mobile browser observation with
streamlit run tests/qa02_dashboard_fixture.py. This module never starts a server.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from sqlalchemy import Engine, event

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard import data_status, streamlit_actions as actions
from invest_bot.dashboard import streamlit_dashboard as dashboard
from invest_bot.dashboard import streamlit_overview as overview
from invest_bot.dashboard import streamlit_reports as reports
from invest_bot.dashboard import streamlit_watchlist as watchlist
from invest_bot.dashboard.report_favorites import ReportFavoritesStore
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_state import DashboardFrameLoader
from invest_bot.db.contracts import StockRecord
from invest_bot.db.engine import build_engine, build_session_factory, ensure_schema
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.repositories import SqlAlchemyStockRepository
from invest_bot.market.symbol_lookup import SymbolEntry


NAMES = {"005930": "삼성전자", "000660": "SK하이닉스", "035420": "NAVER", "005380": "현대차"}
SCENARIOS = {"005930": "분석 지연·summary만 유효", "000660": "수급 원본 누락", "035420": "판단 날짜 불일치·수급 기간 불일치", "005380": "정상·detail 우선"}
DAYS = ["2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"]


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 22)


class QA02Harness:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or Path(tempfile.mkdtemp(prefix="qa02-synthetic-", dir="/private/tmp"))
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database_url = f"sqlite:///{self.directory / 'qa02.sqlite'}"
        engine = build_engine(self.database_url)
        ensure_schema(engine)
        stocks = SqlAlchemyStockRepository(build_session_factory(engine))
        for symbol, name in NAMES.items():
            stocks.upsert(StockRecord(symbol, name, "KOSPI"))
        engine.dispose()
        self.storage = DbFrameStorage(self.database_url)
        self.settings = AppSettings(database_url_value=self.database_url, discord_webhook_url="")
        self.favorites = ReportFavoritesStore(settings=self.settings)
        for symbol in NAMES:
            self.favorites.add(symbol)
        self.service = DashboardDataService(dataset_storage=self.storage,
                                           raw_root=self.directory / "not-used-raw",
                                           processed_root=self.directory / "not-used-processed",
                                           settings=self.settings)
        self.service.load_test_report = lambda: None
        self.calls: list[tuple] = []
        self.forbidden_calls: list[str] = []
        self.measurements: list[dict] = []
        self.sql_attempts: list[dict] = []
        self.render_complete = False
        self.last_snapshot = None
        self._seed()
        original_build_snapshot = self.service.build_snapshot
        def measured_snapshot():
            self.phase = "snapshot"
            self.last_snapshot = original_build_snapshot()
            self.phase = "consumer"
            return self.last_snapshot
        self.service.build_snapshot = measured_snapshot

    @staticmethod
    def prices(symbol: str) -> pd.DataFrame:
        return pd.DataFrame({"date": DAYS, "symbol": symbol, "open": [98., 99., 100., 101., 102.],
                             "high": [102., 103., 104., 105., 106.], "low": [97., 98., 99., 100., 101.],
                             "close": [100., 101., 102., 103., 104.], "volume": [1000., 1100., 1200., 1300., 1400.],
                             "ma_5": [99.] * 5, "ma_20": [98.] * 5, "ma_60": [97.] * 5, "rsi_14": [55.] * 5})

    def _seed(self):
        for symbol, name in NAMES.items():
            prices = self.prices(symbol)
            self.storage.save("daily_prices", f"{symbol}_raw.csv", prices)
            indicator = prices.iloc[:-1] if symbol == "005930" else prices
            self.storage.save("daily_prices_indicators", f"{symbol}_indicator.csv", indicator)
            analysis_day = "2026-10-21" if symbol == "005930" else DAYS[-1]
            signal = pd.DataFrame({"symbol": [symbol], "date": [analysis_day], "signal": ["hold"], "close": [103.]})
            self.storage.save("golden_cross_signals", f"{symbol}_signals.csv", signal)
            report_day = "2026-10-23" if symbol == "035420" else analysis_day
            report = pd.DataFrame([{"symbol": symbol, "symbol_name": name, "date": report_day,
                                   "close": 103., "ma_5": 99., "ma_20": 98., "ma_60": 97., "rsi_14": 55.,
                                   "final_opinion": "watch", "summary": f"{name} 독립 QA02 저장 리포트",
                                   "trend_state": "bullish", "golden_cross_signal": "hold", "investor_flow": "supportive",
                                   "rsi_strategy_signal": "sell", "trend_filter_signal": "buy", "mean_reversion_signal": "hold"}])
            self.storage.save("market_reports", f"{symbol}_report.csv", report)
            if symbol == "000660":
                continue
            if symbol == "005930":
                summary = pd.DataFrame({"trade_date": ["2026-10-19", "2026-10-21", "2026-10-22"],
                                        "foreign_net": [-11., 0., 15.], "institutional_net": [5., None, -3.]})
                self.storage.save("investor_daily", f"{symbol}_undated.csv", pd.DataFrame({"foreign_net": [999.]}))
            elif symbol == "035420":
                summary = pd.DataFrame({"trade_date": ["2026-10-23"], "foreign_net": [88.]})
            else:
                summary = pd.DataFrame({"trade_date": [DAYS[-1]], "foreign_net": [999.], "institutional_net": [999.]})
                self.storage.save("investor_daily", f"{symbol}_detail.csv", pd.DataFrame({"date": [DAYS[-1]], "foreign_net": [0.]}))
            self.storage.save("investor_daily_summary", f"{symbol}_summary.csv", summary)

    @contextmanager
    def observe(self):
        self.phase = "before"
        self.selects: list[tuple[str, str]] = []
        def listener(conn, _cursor, statement, _parameters, _context, _executemany):
            if str(conn.engine.url) == self.database_url and statement.lstrip().upper().startswith("SELECT"):
                self.selects.append((self.phase, statement))
        event.listen(Engine, "before_cursor_execute", listener)
        try:
            yield
        finally:
            event.remove(Engine, "before_cursor_execute", listener)
            self.sql_attempts.append({
                "completed_render": self.render_complete,
                "total_selects": len(self.selects),
                "snapshot_selects": sum(phase == "snapshot" for phase, _ in self.selects),
                "favorite_selects_after_snapshot": sum(phase == "consumer" and "report_favorite_symbols" in sql for phase, sql in self.selects),
                "frame_consumer_selects": sum(phase == "consumer" and "report_favorite_symbols" not in sql for phase, sql in self.selects),
            })

    def forbidden(self, name):
        def fail(*_args, **_kwargs):
            self.forbidden_calls.append(name)
            raise AssertionError(f"QA02 forbidden operational call: {name}")
        return fail

    def render(self):
        import streamlit as st
        self.render_complete = False
        def settings_provider(*_args, **_kwargs):
            with st.sidebar.expander("QA02 가상 실행 조건", expanded=False):
                configured = st.toggle("가상 Discord 설정", value=False, key="qa02_configured")
                st.selectbox("가상 수집 결과", ["all", "partial", "none"], key="qa02_collection")
                st.selectbox("가상 전송 결과", ["sent", "failed", "skipped"], key="qa02_delivery")
                st.caption("고정 기준일 2026-10-22 · 실제 데이터·API·Discord 미사용")
            self.settings.discord_webhook_url = "https://example.invalid/qa02-never-delivered" if configured else ""
            return self.settings
        def collect(symbols, days):
            self.calls.append(("collect", tuple(symbols), days))
            mode = st.session_state.get("qa02_collection", "all")
            successful = symbols if mode == "all" else symbols[:1] if mode == "partial" else []
            return {"successful_symbols": successful, "success_count": len(successful), "failed_count": len(symbols) - len(successful)}
        def report(symbol, *, delivery_target, settings):
            configured = bool(settings.discord_webhook_url.strip())
            self.calls.append(("report", symbol, delivery_target, configured))
            result = st.session_state.get("qa02_delivery", "sent") if configured else "skipped"
            detail = "synthetic HTTP 500" if result == "failed" else "Discord webhook URL is not configured." if result == "skipped" else ""
            return {"symbol": symbol, "delivery": {"status": result, "error_detail": detail}}
        lookup = SimpleNamespace(list_entries=lambda: [SymbolEntry(symbol, name) for symbol, name in NAMES.items()])
        with self.observe(), ExitStack() as stack:
            stack.enter_context(patch.object(dashboard.AppSettings, "from_file", settings_provider))
            stack.enter_context(patch.object(dashboard, "DashboardDataService", lambda **_kwargs: self.service))
            stack.enter_context(patch.object(dashboard, "SymbolLookup", lambda: lookup))
            stack.enter_context(patch.object(dashboard, "_load_optional_schedule_status", lambda: None))
            stack.enter_context(patch.object(data_status, "date", FixedDate))
            stack.enter_context(patch.object(overview, "date", FixedDate))
            stack.enter_context(patch.object(reports, "ReportFavoritesStore", lambda **_kwargs: self.favorites))
            stack.enter_context(patch.object(watchlist, "ReportFavoritesStore", lambda **_kwargs: self.favorites))
            stack.enter_context(patch.object(actions, "collect_market_data_for_symbols", collect))
            stack.enter_context(patch.object(actions, "generate_indicators_for_symbol", lambda symbol: self.calls.append(("indicators", symbol))))
            stack.enter_context(patch.object(actions, "generate_golden_cross_signals_for_symbol", lambda symbol: self.calls.append(("signals", symbol))))
            stack.enter_context(patch.object(actions, "generate_market_report_for_symbol", report))
            for name in ("refresh_favorite_symbols_if_needed", "generate_indicators_for_symbol", "generate_golden_cross_signals_for_symbol", "generate_market_report_for_symbol", "MarketDataCollector"):
                stack.enter_context(patch.object(watchlist, name, self.forbidden(name)))
            dashboard.main()
            self.render_complete = True
            favorites = [statement for phase, statement in self.selects if phase == "consumer" and "report_favorite_symbols" in statement]
            consumers = [statement for phase, statement in self.selects if phase == "consumer" and "report_favorite_symbols" not in statement]
            measurement = {"tab": st.session_state.get("selected_tab"), "total_selects": len(self.selects),
                           "snapshot_selects": sum(phase == "snapshot" for phase, _ in self.selects),
                           "favorite_selects_after_snapshot": len(favorites), "frame_consumer_selects": len(consumers),
                           "job_calls": len(self.calls), "forbidden_calls": list(self.forbidden_calls)}
            measurement["selects_all_script_attempts"] = sum(attempt["total_selects"] for attempt in self.sql_attempts) + len(self.selects)
            self.measurements.append(measurement)
            st.session_state["qa02_measurement"] = measurement
            st.session_state["qa02_calls"] = list(self.calls)
            st.caption("QA02 독립 통합: " + str(measurement))


def render_fixture():
    import streamlit as st
    harness = st.session_state.get("qa02_harness")
    if harness is None:
        harness = QA02Harness()
        st.session_state["qa02_harness"] = harness
    harness.render()


if __name__ == "__main__":
    render_fixture()
