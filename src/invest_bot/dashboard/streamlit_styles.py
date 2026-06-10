from __future__ import annotations

import streamlit as st


def apply_custom_style() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Noto+Sans+KR:wght@400;500;700&display=swap');

        html, body, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at top left, rgba(15, 118, 110, 0.12), transparent 28%),
                radial-gradient(circle at top right, rgba(217, 119, 6, 0.10), transparent 24%),
                linear-gradient(180deg, #f7f2e9 0%, #f3ede2 100%);
        }

        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] p,
        [data-testid="stAppViewContainer"] div,
        [data-testid="stAppViewContainer"] span,
        [data-testid="stAppViewContainer"] label,
        [data-testid="stAppViewContainer"] h1,
        [data-testid="stAppViewContainer"] h2,
        [data-testid="stAppViewContainer"] h3,
        [data-testid="stAppViewContainer"] h4,
        [data-testid="stAppViewContainer"] h5,
        [data-testid="stAppViewContainer"] h6,
        [data-testid="stAppViewContainer"] button,
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] div,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4,
        [data-testid="stSidebar"] h5,
        [data-testid="stSidebar"] h6,
        [data-testid="stSidebar"] button {
            font-family: "Noto Sans KR", "Space Grotesk", sans-serif;
        }

        .material-symbols-rounded,
        .material-symbols-outlined,
        .material-icons,
        [class*="material-symbols"],
        [data-testid="stExpandSidebarButton"],
        [data-testid="stExpandSidebarButton"] *,
        [data-testid="stSidebarCollapseButton"] span,
        [data-testid="stSidebarNavCollapseButton"] span {
            font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
            font-weight: normal !important;
            font-style: normal !important;
            font-size: 1.25rem !important;
            line-height: 1 !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            display: inline-block !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
            direction: ltr !important;
            -webkit-font-smoothing: antialiased !important;
            font-variation-settings:
                "FILL" 0,
                "wght" 400,
                "GRAD" 0,
                "opsz" 24;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
        }

        [data-testid="stSidebar"] * {
            color: #f8fafc;
        }

        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
            border-radius: 0.95rem;
            border: 1px solid rgba(148, 163, 184, 0.26);
            background: rgba(30, 41, 59, 0.82);
            color: #f8fafc;
            font-weight: 700;
            box-shadow: none;
            transition: all 0.16s ease;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            border-color: rgba(45, 212, 191, 0.6);
            background: rgba(51, 65, 85, 0.96);
            color: #ffffff;
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #14b8a6 0%, #0f766e 100%);
            border-color: rgba(20, 184, 166, 0.65);
            color: #f8fffe;
            box-shadow: 0 10px 24px rgba(15, 118, 110, 0.24);
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #2dd4bf 0%, #0f766e 100%);
            color: #ffffff;
        }

        .hero-shell {
            padding: 1.4rem 1.6rem;
            border-radius: 1.4rem;
            background: linear-gradient(135deg, rgba(255,250,242,0.96), rgba(255,255,255,0.84));
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 22px 60px rgba(15, 23, 42, 0.08);
            margin-bottom: 1rem;
        }

        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.28rem 0.7rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            color: #0f766e;
            background: rgba(15, 118, 110, 0.10);
            margin-bottom: 0.75rem;
        }

        .hero-title {
            font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
            font-size: 2.2rem;
            line-height: 1.05;
            margin: 0;
            color: #111827;
            letter-spacing: -0.04em;
        }

        .hero-copy {
            margin-top: 0.75rem;
            color: #475569;
            font-size: 0.98rem;
        }

        .streamlit-card {
            padding: 1rem 1rem 0.85rem 1rem;
            border-radius: 1.1rem;
            background: rgba(255, 252, 247, 0.96);
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
        }

        .section-title {
            margin: 0;
            font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
            font-size: 1.15rem;
            color: #111827;
            letter-spacing: -0.03em;
        }

        .section-copy {
            margin-top: 0.35rem;
            color: #64748b;
            font-size: 0.93rem;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.34rem 0.7rem;
            font-size: 0.78rem;
            font-weight: 700;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
        }

        .badge-buy, .badge-bullish, .badge-supportive, .badge-active, .badge-strong {
            background: rgba(22, 163, 74, 0.12);
            color: #166534;
        }

        .badge-sell, .badge-bearish, .badge-weak, .badge-overbought {
            background: rgba(220, 38, 38, 0.11);
            color: #991b1b;
        }

        .badge-hold, .badge-watch, .badge-neutral, .badge-normal, .badge-quiet, .badge-oversold, .badge-mixed, .badge-unknown {
            background: rgba(148, 163, 184, 0.14);
            color: #334155;
        }

        .summary-box {
            padding: 0.95rem 1rem;
            border-radius: 1rem;
            background: rgba(248, 250, 252, 0.82);
            border: 1px solid rgba(148, 163, 184, 0.22);
        }

        .muted-label {
            color: #64748b;
            font-size: 0.82rem;
        }

        .sidebar-nav-title {
            margin-top: 0.4rem;
            margin-bottom: 0.6rem;
            font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
            font-size: 0.92rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: #cbd5e1;
        }

        .sidebar-info-card {
            margin-top: 0.35rem;
            padding: 0.95rem 1rem;
            border-radius: 1rem;
            background: rgba(30, 41, 59, 0.78);
            border: 1px solid rgba(148, 163, 184, 0.22);
        }

        .sidebar-info-title {
            margin: 0 0 0.6rem 0;
            font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
            font-size: 0.95rem;
            font-weight: 700;
            color: #f8fafc;
        }

        .sidebar-info-label {
            margin-top: 0.45rem;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #94a3b8;
        }

        .sidebar-info-value {
            margin-top: 0.18rem;
            padding: 0.42rem 0.55rem;
            border-radius: 0.7rem;
            background: rgba(15, 23, 42, 0.5);
            color: #f8fafc;
            font-size: 0.82rem;
            word-break: break-all;
        }

        div[data-baseweb="tab-list"] {
            gap: 0.45rem;
            padding: 0.3rem;
            border-radius: 1rem;
            background: rgba(255, 250, 242, 0.82);
            border: 1px solid rgba(148, 163, 184, 0.18);
        }

        button[data-baseweb="tab"] {
            height: 2.8rem;
            padding: 0 1rem;
            border-radius: 0.85rem;
            color: #475569;
            background: transparent;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(255, 247, 237, 0.96));
            color: #0f172a;
            border: 1px solid rgba(15, 118, 110, 0.18);
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
        }

        button[data-baseweb="tab"]::after {
            background: transparent !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
