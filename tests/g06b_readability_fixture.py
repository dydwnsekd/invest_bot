"""Read-only product renderers with synthetic states for G06b visual checks."""


def render_readability_fixture():
    from datetime import UTC, date, datetime
    from pathlib import Path

    import pandas as pd
    import streamlit as st

    from invest_bot.dashboard.data_status import WatchlistDataStatus
    from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
    from invest_bot.dashboard.streamlit_interpretations import render_interpretation_cards
    from invest_bot.dashboard.streamlit_reports import render_market_report_card
    from invest_bot.dashboard.streamlit_styles import apply_custom_style
    from invest_bot.dashboard.streamlit_watchlist import render_watchlist_data_status

    st.set_page_config(page_title="G06b 상태 가독성 검증", layout="wide")
    apply_custom_style()
    st.caption("가상 데이터 · 실제 API·DB·수집·분석·전송을 실행하지 않는 화면입니다.")
    st.button("상태 확인", type="primary", key="g06b_primary")
    st.text_input("상태 검색", key="g06b_search")
    opinion = st.selectbox("종합 상태", ["buy", "sell", "hold"], key="g06b_opinion")
    view = st.radio("화면", ["리포트", "관심종목", "해석 모아보기"], horizontal=True, key="g06b_view")
    with st.sidebar:
        st.button("조회 화면", type="primary")
        with st.expander("아이콘 확인"):
            st.caption("아이콘 이름이 일반 텍스트로 표시되지 않아야 합니다.")
    with st.expander("검증 조건"):
        st.caption("대비4.5:1 이상 · 보조 라벨0.8rem 이상 · 기존 상태 판단은 유지합니다.")
    with st.status("가상 검증 준비 완료", state="complete", expanded=False):
        st.write("읽기 전용 표본을 표시합니다.")

    service = DashboardDataService(raw_root="/virtual/g06b/raw", processed_root="/virtual/g06b/processed")

    def forbidden(*args, **kwargs):
        raise AssertionError("Readability renderer attempted backing storage access")

    service.get_dataset_storage = forbidden
    row = dict(
        date="2026-10-22", symbol="005930", symbol_name="삼성전자", final_opinion=opinion,
        close=101.0, ma_5=100.0, ma_20=99.0, ma_60=98.0, rsi_14=55.0,
        golden_cross_signal="buy", rsi_strategy_signal="sell", trend_filter_signal="hold",
        mean_reversion_signal="buy", trend_state="bullish", investor_flow="mixed",
        summary="상태별 글자색·보조 라벨·아이콘 가상 검증",
        golden_cross_reason="매수 상태 표본", rsi_strategy_reason="매도 상태 표본",
        trend_filter_reason="중립 상태 표본", mean_reversion_reason="매수 상태 표본",
    )
    frame = pd.DataFrame([row])
    preview = DatasetPreview(
        name="market_reports", display_name="시장 리포트", path=Path("005930_g06b.csv"),
        row_count=1, columns=list(frame.columns), summary="가상 상태",
        purpose="가독성 확인", first_look="상태", symbol="005930", symbol_name="삼성전자",
        recommended_columns=["date"],
    )
    if view == "리포트":
        render_market_report_card(
            preview, service, frame=frame, read_preview_frame=forbidden,
            load_indicator_frame_for_symbol=lambda _: None,
            load_professional_frame_for_symbol=lambda _: None,
        )
    elif view == "관심종목":
        day = date(2026, 10, 22)
        render_watchlist_data_status([
            WatchlistDataStatus(
                symbol="005930", label="분석 갱신 필요", detail="원본은 최신이며 분석 결과를 확인하세요.",
                daily_date=day, investor_date=day, indicator_date=day, signal_date=day, report_date=day,
                collection_created_at=datetime(2026, 10, 22, 1, tzinfo=UTC),
                analysis_created_at=datetime(2026, 10, 22, 2, tzinfo=UTC),
            ),
        ])
    else:
        st.markdown(render_interpretation_cards([{
            "날짜": row["date"], "종목": "삼성전자 (005930)", "최종 의견": opinion,
            "골든크로스": "매수", "RSI 전략": "매도", "추세필터": "관망", "평균회귀": "관망",
            "추세": "상승 우세", "수급": "혼조", "한 줄 해석": row["summary"],
        }]), unsafe_allow_html=True)
