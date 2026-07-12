from __future__ import annotations

import streamlit as st


def apply_custom_style() -> None:
    st.markdown(
        """
        <style>
        html,
        body,
        [data-testid="stAppViewContainer"] {
            --app-bg: #0b1220;
            --app-panel: #111827;
            --app-panel-elevated: #182235;
            --app-panel-soft: #0f172a;
            --app-border: rgba(148, 163, 184, 0.18);
            --app-border-strong: rgba(148, 163, 184, 0.28);
            --app-text: #e5edf7;
            --app-text-muted: #94a3b8;
            --app-text-soft: #cbd5e1;
            --app-accent: #5eead4;
            --app-accent-strong: #2dd4bf;
            --app-success-bg: rgba(34, 197, 94, 0.18);
            --app-success-text: #bbf7d0;
            --app-danger-bg: rgba(248, 113, 113, 0.18);
            --app-danger-text: #fecaca;
            --app-neutral-bg: rgba(148, 163, 184, 0.16);
            --app-neutral-text: #dbe4f0;
            --font-ui: "Pretendard", "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", "Apple Gothic", "Nanum Gothic", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            --font-label: "Pretendard", "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", "Segoe UI", "Inter", "IBM Plex Sans", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            background:
                radial-gradient(circle at top left, rgba(94, 234, 212, 0.08), transparent 26%),
                radial-gradient(circle at top right, rgba(59, 130, 246, 0.10), transparent 22%),
                linear-gradient(180deg, #08111f 0%, #0b1220 48%, #0f172a 100%);
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
            border-right: 1px solid rgba(148, 163, 184, 0.14);
        }

        [data-testid="stSidebar"] * {
            color: var(--app-text);
        }

        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
            border-radius: 0.95rem;
            border: 1px solid var(--app-border-strong);
            background: rgba(17, 24, 39, 0.92);
            color: var(--app-text);
            font-family: var(--font-label);
            font-weight: 600;
            box-shadow: none;
            transition: border-color 0.16s ease, background 0.16s ease, color 0.16s ease;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            border-color: rgba(94, 234, 212, 0.42);
            background: rgba(24, 34, 53, 0.96);
            color: #f8fafc;
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, rgba(45, 212, 191, 0.18), rgba(94, 234, 212, 0.12));
            border-color: rgba(94, 234, 212, 0.36);
            color: #d7fffb;
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, rgba(45, 212, 191, 0.24), rgba(94, 234, 212, 0.16));
            color: #effffc;
        }

        .hero-shell {
            padding: 1.4rem 1.6rem;
            border-radius: 1.4rem;
            background: linear-gradient(180deg, rgba(17, 24, 39, 0.94), rgba(15, 23, 42, 0.92));
            border: 1px solid var(--app-border);
            box-shadow: 0 18px 36px rgba(2, 6, 23, 0.24);
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
            font-weight: 600;
            color: #c7fff7;
            background: rgba(45, 212, 191, 0.12);
            border: 1px solid rgba(94, 234, 212, 0.20);
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
            background: rgba(17, 24, 39, 0.88);
            border: 1px solid var(--app-border);
            box-shadow: 0 12px 28px rgba(2, 6, 23, 0.18);
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
            border-color: rgba(34, 197, 94, 0.22);
        }

        .badge-sell, .badge-bearish, .badge-weak, .badge-overbought {
            background: var(--app-danger-bg);
            color: var(--app-danger-text);
            border-color: rgba(248, 113, 113, 0.24);
        }

        .badge-hold, .badge-watch, .badge-neutral, .badge-normal, .badge-quiet, .badge-oversold, .badge-mixed, .badge-unknown {
            background: var(--app-neutral-bg);
            color: var(--app-neutral-text);
            border-color: rgba(148, 163, 184, 0.22);
        }

        .summary-box {
            padding: 0.95rem 1rem;
            border-radius: 1rem;
            background: rgba(15, 23, 42, 0.78);
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
            background: rgba(17, 24, 39, 0.76);
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
            background: rgba(8, 17, 31, 0.76);
            color: var(--app-text);
            font-family: var(--font-label);
            font-size: 0.82rem;
            word-break: break-all;
        }

        div[data-baseweb="tab-list"] {
            gap: 0.45rem;
            padding: 0.3rem;
            border-radius: 1rem;
            background: rgba(15, 23, 42, 0.84);
            border: 1px solid var(--app-border);
        }

        button[data-baseweb="tab"] {
            height: 2.8rem;
            padding: 0 1rem;
            border-radius: 0.85rem;
            font-family: var(--font-label);
            color: var(--app-text-muted);
            background: transparent;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(180deg, rgba(24, 34, 53, 0.96), rgba(17, 24, 39, 0.96));
            color: #f8fafc;
            border: 1px solid rgba(94, 234, 212, 0.20);
            box-shadow: 0 8px 20px rgba(2, 6, 23, 0.18);
        }

        button[data-baseweb="tab"]::after {
            background: transparent !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
