from __future__ import annotations

import streamlit as st


def apply_custom_style() -> None:
    st.markdown(
        """
        <style>
        html,
        body,
        [data-testid="stAppViewContainer"] {
            --app-bg: #050816;
            --app-panel: #111827;
            --app-panel-elevated: #1e293b;
            --app-panel-soft: #0f172a;
            --app-border: rgba(203, 213, 225, 0.32);
            --app-border-strong: rgba(203, 213, 225, 0.48);
            --app-text: #f8fafc;
            --app-text-muted: #cbd5e1;
            --app-text-soft: #e2e8f0;
            --app-accent: #38bdf8;
            --app-accent-strong: #0ea5e9;
            --app-success-bg: rgba(34, 197, 94, 0.28);
            --app-success-text: #f8fafc;
            --app-danger-bg: rgba(248, 113, 113, 0.30);
            --app-danger-text: #fff7f7;
            --app-neutral-bg: rgba(148, 163, 184, 0.28);
            --app-neutral-text: #f8fafc;
            --font-ui: "Pretendard", "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", "Apple Gothic", "Nanum Gothic", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            --font-label: "Pretendard", "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", "Segoe UI", "Inter", "IBM Plex Sans", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            background:
                radial-gradient(circle at top left, rgba(56, 189, 248, 0.14), transparent 26%),
                radial-gradient(circle at top right, rgba(14, 165, 233, 0.12), transparent 22%),
                linear-gradient(180deg, #020617 0%, #050816 48%, #0f172a 100%);
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
            font-family: var(--font-ui);
            color: var(--app-text);
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
            border-right: 1px solid var(--app-border-strong);
        }

        [data-testid="stSidebar"] * {
            color: var(--app-text);
        }

        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
            border-radius: 0.95rem;
            border: 1px solid var(--app-border-strong);
            background: rgba(17, 24, 39, 0.98);
            color: var(--app-text);
            font-family: var(--font-label);
            font-weight: 700;
            box-shadow: none;
            transition: border-color 0.16s ease, background 0.16s ease, color 0.16s ease;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            border-color: rgba(56, 189, 248, 0.72);
            background: rgba(30, 41, 59, 0.98);
            color: #f8fafc;
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.34), rgba(56, 189, 248, 0.22));
            border-color: rgba(56, 189, 248, 0.78);
            color: #f8fafc;
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.44), rgba(56, 189, 248, 0.30));
            color: #ffffff;
        }

        .hero-shell {
            padding: 1.4rem 1.6rem;
            border-radius: 1.4rem;
            background: linear-gradient(180deg, rgba(17, 24, 39, 0.98), rgba(15, 23, 42, 0.96));
            border: 1px solid var(--app-border-strong);
            box-shadow: 0 18px 36px rgba(2, 6, 23, 0.34);
            margin-bottom: 1rem;
        }

        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.28rem 0.7rem;
            border-radius: 999px;
            font-family: var(--font-label);
            font-size: 0.78rem;
            font-weight: 700;
            color: #f8fafc;
            background: rgba(14, 165, 233, 0.24);
            border: 1px solid rgba(56, 189, 248, 0.42);
            margin-bottom: 0.75rem;
        }

        .hero-title {
            font-family: var(--font-ui);
            font-size: 2.2rem;
            line-height: 1.05;
            margin: 0;
            color: #f8fafc;
            letter-spacing: -0.035em;
        }

        .hero-copy {
            margin-top: 0.75rem;
            color: var(--app-text-soft);
            font-size: 0.98rem;
        }

        .streamlit-card {
            padding: 1rem 1rem 0.85rem 1rem;
            border-radius: 1.1rem;
            background: rgba(17, 24, 39, 0.94);
            border: 1px solid var(--app-border);
            box-shadow: 0 12px 28px rgba(2, 6, 23, 0.24);
        }

        .section-title {
            margin: 0;
            font-family: var(--font-ui);
            font-size: 1.15rem;
            color: #f8fafc;
            letter-spacing: -0.02em;
        }

        .section-copy {
            margin-top: 0.35rem;
            color: var(--app-text-muted);
            font-size: 0.93rem;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.34rem 0.7rem;
            font-family: var(--font-label);
            font-size: 0.78rem;
            font-weight: 700;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
            border: 1px solid transparent;
        }

        .badge-buy, .badge-bullish, .badge-supportive, .badge-active, .badge-strong {
            background: var(--app-success-bg);
            color: var(--app-success-text);
            border-color: rgba(34, 197, 94, 0.38);
        }

        .badge-sell, .badge-bearish, .badge-weak, .badge-overbought {
            background: var(--app-danger-bg);
            color: var(--app-danger-text);
            border-color: rgba(248, 113, 113, 0.42);
        }

        .badge-hold, .badge-watch, .badge-neutral, .badge-normal, .badge-quiet, .badge-oversold, .badge-mixed, .badge-unknown {
            background: var(--app-neutral-bg);
            color: var(--app-neutral-text);
            border-color: rgba(203, 213, 225, 0.40);
        }

        .summary-box {
            padding: 0.95rem 1rem;
            border-radius: 1rem;
            background: rgba(15, 23, 42, 0.90);
            border: 1px solid var(--app-border);
        }

        .muted-label {
            color: var(--app-text-muted);
            font-family: var(--font-label);
            font-size: 0.82rem;
        }

        .sidebar-nav-title {
            margin-top: 0.4rem;
            margin-bottom: 0.6rem;
            font-family: var(--font-label);
            font-size: 0.92rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: var(--app-text-muted);
        }

        .sidebar-info-card {
            margin-top: 0.35rem;
            padding: 0.95rem 1rem;
            border-radius: 1rem;
            background: rgba(17, 24, 39, 0.88);
            border: 1px solid var(--app-border);
        }

        .sidebar-info-title {
            margin: 0 0 0.6rem 0;
            font-family: var(--font-ui);
            font-size: 0.95rem;
            font-weight: 700;
            color: #f8fafc;
        }

        .sidebar-info-label {
            margin-top: 0.45rem;
            font-family: var(--font-label);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--app-text-muted);
        }

        .sidebar-info-value {
            margin-top: 0.18rem;
            padding: 0.42rem 0.55rem;
            border-radius: 0.7rem;
            background: rgba(2, 6, 23, 0.88);
            color: var(--app-text);
            font-family: var(--font-label);
            font-size: 0.82rem;
            word-break: break-all;
            border: 1px solid var(--app-border);
        }

        div[data-baseweb="tab-list"] {
            gap: 0.45rem;
            padding: 0.3rem;
            border-radius: 1rem;
            background: rgba(15, 23, 42, 0.94);
            border: 1px solid var(--app-border-strong);
        }

        button[data-baseweb="tab"] {
            height: 2.8rem;
            padding: 0 1rem;
            border-radius: 0.85rem;
            font-family: var(--font-label);
            color: var(--app-text-soft);
            background: rgba(15, 23, 42, 0.18);
            border: 1px solid transparent;
            font-weight: 600;
        }

        button[data-baseweb="tab"]:hover {
            color: #f8fafc;
            background: rgba(30, 41, 59, 0.78);
            border-color: rgba(56, 189, 248, 0.36);
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(180deg, rgba(30, 41, 59, 0.98), rgba(17, 24, 39, 0.98));
            color: #f8fafc;
            border: 1px solid rgba(56, 189, 248, 0.60);
            box-shadow: 0 8px 20px rgba(2, 6, 23, 0.24);
        }

        button[data-baseweb="tab"]::after {
            background: transparent !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
