from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard.report_favorites import ReportFavoritesStore
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_reports import (
    build_report_entries,
    format_report_selection_option,
    get_report_entry_by_key,
    query_report_previews,
    render_market_report_card,
    resolve_selected_report_key,
    selected_entry_key_index,
    sort_report_entries,
)
from invest_bot.jobs.analyze_daily_prices import generate_indicators_for_symbol
from invest_bot.jobs.run_golden_cross_signals import generate_golden_cross_signals_for_symbol
from invest_bot.jobs.run_market_report import generate_market_report_for_symbol
from invest_bot.market.collector import MarketDataCollector


WATCHLIST_SELECTION_KEY = "watchlist_selected_entry_key"
WATCHLIST_SORT_OPTION_KEY = "watchlist_sort_option"
WATCHLIST_BOOTSTRAP_DAYS = 365


def render_watchlist_tab(
    snapshot,
    service: DashboardDataService,
    *,
    read_preview_frame: Callable[[object], pd.DataFrame],
    load_indicator_frame_for_symbol: Callable[[str], pd.DataFrame | None],
    favorites_store: ReportFavoritesStore | None = None,
) -> None:
    st.markdown('<h3 class="section-title">관심종목</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">저장해 둔 관심종목만 모아서 최신 리포트와 차트를 빠르게 다시 확인할 수 있습니다.</div>',
        unsafe_allow_html=True,
    )

    favorites_store = favorites_store or ReportFavoritesStore()
    favorite_symbols = favorites_store.load_symbols()
    if not favorite_symbols:
        st.info("아직 저장된 관심종목이 없습니다. `리포트 해석` 탭에서 관심종목을 추가해 보세요.")
        return

    try:
        refresh_result = refresh_favorite_symbols_if_needed(service, favorite_symbols)
    except Exception as error:  # noqa: BLE001
        refresh_result = {"collected_symbols": [], "pipeline_symbols": []}
        st.warning(f"관심종목 자동 최신화 중 오류가 발생했습니다: {error}")
    if refresh_result["collected_symbols"] or refresh_result["pipeline_symbols"]:
        snapshot = service.build_snapshot()
        updated_symbols = ", ".join(refresh_result["pipeline_symbols"][:3])
        suffix = "" if len(refresh_result["pipeline_symbols"]) <= 3 else f" 외 {len(refresh_result['pipeline_symbols']) - 3}건"
        st.caption(f"관심종목 최신화 완료: {updated_symbols}{suffix}")

    report_previews = [preview for preview in snapshot.processed_previews if preview.name == "market_reports"]
    favorite_previews = [preview for preview in report_previews if preview.symbol in favorite_symbols]
    if not favorite_previews:
        st.info("저장된 관심종목과 연결되는 최신 시장 리포트가 아직 없습니다.")
        return

    query = st.text_input(
        "관심종목 검색",
        placeholder="종목코드 또는 종목명으로 찾기",
        key="watchlist_query",
    ).strip().lower()
    visible_previews = query_report_previews(favorite_previews, query)
    entries = build_report_entries(
        visible_previews,
        service,
        read_preview_frame=read_preview_frame,
        favorite_symbols=favorite_symbols,
    )

    sort_option = st.selectbox(
        "정렬",
        options=["즐겨찾기 우선", "최신순", "종목명순", "매수 관점 우선"],
        index=["즐겨찾기 우선", "최신순", "종목명순", "매수 관점 우선"].index(
            str(st.session_state.get(WATCHLIST_SORT_OPTION_KEY, "즐겨찾기 우선"))
        )
        if str(st.session_state.get(WATCHLIST_SORT_OPTION_KEY, "즐겨찾기 우선"))
        in {"즐겨찾기 우선", "최신순", "종목명순", "매수 관점 우선"}
        else 0,
        key=WATCHLIST_SORT_OPTION_KEY,
    )
    visible_entries = sort_report_entries(entries, sort_option)

    metric_columns = st.columns(3)
    metric_columns[0].metric("저장된 관심종목", len(favorite_symbols))
    metric_columns[1].metric("현재 후보", len(visible_entries))
    metric_columns[2].metric("매수 관점", sum(1 for item in visible_entries if item["final_opinion"] == "buy"))

    if not visible_entries:
        st.warning("현재 검색 조건에 맞는 관심종목 리포트가 없습니다.")
        return

    selected_entry_key = resolve_selected_report_key(
        visible_entries,
        st.session_state.get(WATCHLIST_SELECTION_KEY),
    )
    selected_key = st.selectbox(
        "관심종목 선택",
        options=[str(entry["entry_key"]) for entry in visible_entries],
        index=selected_entry_key_index(visible_entries, selected_entry_key),
        format_func=lambda entry_key: format_report_selection_option(visible_entries, entry_key),
        key=WATCHLIST_SELECTION_KEY,
    )
    selected_entry = get_report_entry_by_key(visible_entries, selected_key)

    st.caption(f"저장된 관심종목 {len(visible_entries)}건 중 선택한 1건만 본문에 표시합니다.")
    render_market_report_card(
        selected_entry["preview"],
        service,
        frame=selected_entry["frame"],
        read_preview_frame=read_preview_frame,
        load_indicator_frame_for_symbol=load_indicator_frame_for_symbol,
        favorites_store=favorites_store,
        is_favorite=bool(selected_entry["is_favorite"]),
    )


def refresh_favorite_symbols_if_needed(
    service: DashboardDataService,
    favorite_symbols: set[str],
    *,
    today: date | None = None,
    collect_callback: Callable[[str, date, date], bool] | None = None,
    analyze_callback: Callable[[str], dict[str, str | int] | None] = generate_indicators_for_symbol,
    signal_callback: Callable[[str], dict[str, str | int] | None] = generate_golden_cross_signals_for_symbol,
    report_callback: Callable[[str], dict[str, str | int] | None] = generate_market_report_for_symbol,
) -> dict[str, list[str]]:
    if not favorite_symbols:
        return {"collected_symbols": [], "pipeline_symbols": []}

    target_date = _latest_expected_market_date(today or date.today())
    collect_symbol_range = collect_callback or (
        lambda symbol, start_date, end_date: _collect_watchlist_symbol_range(
            service,
            symbol,
            start_date=start_date,
            end_date=end_date,
        )
    )
    collected_symbols: list[str] = []
    symbols_needing_pipeline: list[str] = []

    for symbol in sorted(favorite_symbols):
        daily_date = _load_latest_dataset_date(service, "daily_prices", symbol, ("trade_date", "stck_bsop_date", "date"))
        investor_date = _load_latest_dataset_date(
            service,
            "investor_daily_summary",
            symbol,
            ("trade_date", "stck_bsop_date", "date"),
        )
        report_date = _load_latest_dataset_date(service, "market_reports", symbol, ("date",))
        collection_window = _resolve_collection_window(
            target_date=target_date,
            daily_date=daily_date,
            investor_date=investor_date,
        )
        latest_input_date = _latest_input_date(daily_date, investor_date)

        if collection_window is not None:
            if collect_symbol_range(symbol, collection_window[0], collection_window[1]):
                collected_symbols.append(symbol)
                symbols_needing_pipeline.append(symbol)
            continue

        if latest_input_date is not None and (report_date is None or report_date < latest_input_date):
            symbols_needing_pipeline.append(symbol)

    unique_pipeline_symbols: list[str] = []
    seen: set[str] = set()
    for symbol in symbols_needing_pipeline:
        if symbol not in seen:
            unique_pipeline_symbols.append(symbol)
            seen.add(symbol)

    for symbol in unique_pipeline_symbols:
        analyze_callback(symbol)
        signal_callback(symbol)
        report_callback(symbol)

    return {
        "collected_symbols": collected_symbols,
        "pipeline_symbols": unique_pipeline_symbols,
    }


def _latest_expected_market_date(today: date) -> date:
    if today.weekday() < 5:
        return today
    return today - timedelta(days=today.weekday() - 4)


def _resolve_collection_window(
    *,
    target_date: date,
    daily_date: date | None,
    investor_date: date | None,
) -> tuple[date, date] | None:
    if daily_date is None:
        return (target_date - timedelta(days=WATCHLIST_BOOTSTRAP_DAYS), target_date)
    if daily_date < target_date:
        return (daily_date + timedelta(days=1), target_date)
    if investor_date is None or investor_date < target_date:
        return (target_date, target_date)
    return None


def _latest_input_date(daily_date: date | None, investor_date: date | None) -> date | None:
    dates = [item for item in (daily_date, investor_date) if item is not None]
    return max(dates) if dates else None


def _collect_watchlist_symbol_range(
    service: DashboardDataService,
    symbol: str,
    *,
    start_date: date,
    end_date: date,
) -> bool:
    settings = service._settings or AppSettings.from_file()
    collector = MarketDataCollector(settings)

    daily_summary, daily_prices = collector.collect_daily_prices(symbol, start_date, end_date)
    if daily_prices.empty:
        return False

    existing_daily_frame = _load_latest_dataset_frame(service, "daily_prices", symbol)
    collector.save_daily_prices(symbol, start_date, end_date, daily_summary, daily_prices)

    if _should_save_merged_daily_snapshot(existing_daily_frame, start_date):
        merged_prices = _merge_daily_price_frames(existing_daily_frame, daily_prices)
        merged_start = _resolve_first_daily_date(merged_prices)
        merged_end = _resolve_last_daily_date(merged_prices)
        merged_summary = _build_daily_price_summary_frame(symbol, merged_start, merged_end, len(merged_prices))
        date_range = f"{merged_start.strftime('%Y%m%d')}_{merged_end.strftime('%Y%m%d')}"
        collector.storage.save("daily_prices", f"{symbol}_{date_range}.csv", merged_prices)
        collector.storage.save("daily_prices_summary", f"{symbol}_{date_range}.csv", merged_summary)

    if _load_latest_dataset_frame(service, "stock_info", symbol) is None:
        stock_info = collector.collect_stock_info(symbol)
        collector.save_stock_info(symbol, stock_info)

    investor_daily, investor_summary = collector.collect_investor_daily(symbol, end_date)
    collector.save_investor_daily(symbol, end_date, investor_daily, investor_summary)
    return True


def _should_save_merged_daily_snapshot(existing_daily_frame: pd.DataFrame | None, start_date: date) -> bool:
    if existing_daily_frame is None or existing_daily_frame.empty:
        return False
    return start_date > _resolve_first_daily_date(existing_daily_frame)


def _load_latest_dataset_date(
    service: DashboardDataService,
    dataset: str,
    symbol: str,
    date_columns: Sequence[str],
) -> date | None:
    frame = _load_latest_dataset_frame(service, dataset, symbol)
    if frame is None or frame.empty:
        return None

    for column in date_columns:
        if column not in frame.columns:
            continue
        parsed = pd.to_datetime(frame[column], errors="coerce")
        parsed = parsed.dropna()
        if parsed.empty:
            continue
        return parsed.max().date()
    return None


def _load_latest_dataset_frame(service: DashboardDataService, dataset: str, symbol: str) -> pd.DataFrame | None:
    storage = service.get_dataset_storage()
    if storage is not None:
        filename = storage.latest_filename(dataset, symbol)
        if filename is None:
            return None
        try:
            return storage.load(dataset, filename)
        except FileNotFoundError:
            return None

    dataset_root = _dataset_root(service, dataset)
    if not dataset_root.exists():
        return None
    matches = sorted(dataset_root.glob(f"{symbol}_*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not matches:
        return None
    try:
        return pd.read_csv(matches[0])
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _merge_daily_price_frames(existing_frame: pd.DataFrame, new_frame: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat([existing_frame.copy(), new_frame.copy()], ignore_index=True)
    date_column = _resolve_daily_date_column(combined)
    if date_column is None:
        return combined.reset_index(drop=True)
    combined[date_column] = combined[date_column].astype(str)
    combined = combined.drop_duplicates(subset=[date_column], keep="last")
    combined = combined.sort_values(date_column).reset_index(drop=True)
    return combined


def _resolve_daily_date_column(frame: pd.DataFrame) -> str | None:
    for column in ("stck_bsop_date", "trade_date", "date"):
        if column in frame.columns:
            return column
    return None


def _resolve_first_daily_date(frame: pd.DataFrame) -> date:
    return _resolve_daily_boundary_date(frame, first=True)


def _resolve_last_daily_date(frame: pd.DataFrame) -> date:
    return _resolve_daily_boundary_date(frame, first=False)


def _resolve_daily_boundary_date(frame: pd.DataFrame, *, first: bool) -> date:
    date_column = _resolve_daily_date_column(frame)
    if date_column is None or frame.empty:
        raise ValueError("daily_prices frame is missing a date column.")
    parsed = pd.to_datetime(frame[date_column], errors="coerce").dropna()
    if parsed.empty:
        raise ValueError("daily_prices frame does not contain parseable dates.")
    return (parsed.min() if first else parsed.max()).date()


def _build_daily_price_summary_frame(symbol: str, start_date: date, end_date: date, row_count: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "row_count": row_count,
            }
        ]
    )


def _dataset_root(service: DashboardDataService, dataset: str) -> Path:
    if dataset in service.RAW_DATASETS:
        return service.raw_root / dataset
    return service.processed_root / dataset
