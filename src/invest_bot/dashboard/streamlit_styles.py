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
            justify-content: flex-start;
            padding: 0.34rem 0.1rem 0.34rem 0.72rem;
            border-radius: 0;
            border: 0;
            border-left: 2px solid transparent;
            background: transparent;
            color: var(--app-text-muted);
            font-family: var(--font-label);
            font-weight: 700;
            box-shadow: none;
            transition: border-color 0.16s ease, color 0.16s ease, padding-left 0.16s ease;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            border-left-color: rgba(56, 189, 248, 0.52);
            background: transparent;
            color: #f8fafc;
            padding-left: 0.86rem;
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: transparent;
            border-left-color: rgba(56, 189, 248, 0.92);
            color: #f8fafc;
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
            background: transparent;
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

        .compact-hero {
            padding: 1.05rem 1.2rem;
            margin-bottom: 0.85rem;
        }

        .compact-hero .eyebrow {
            margin-bottom: 0.55rem;
        }

        .compact-hero .hero-title {
            font-size: clamp(1.55rem, 3.1vw, 2.05rem);
        }

        .compact-hero .hero-copy {
            max-width: 54rem;
            font-size: 0.94rem;
        }

        .quick-start-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.65rem;
            margin-top: 0.9rem;
        }

        .quick-start-card {
            padding: 0.8rem 0.85rem;
            border-radius: 0.9rem;
            background: rgba(15, 23, 42, 0.72);
            border: 1px solid rgba(203, 213, 225, 0.22);
        }

        .quick-start-card strong {
            display: block;
            margin-top: 0.45rem;
            color: #f8fafc;
            font-size: 0.95rem;
        }

        .quick-start-card p {
            margin: 0.35rem 0 0 0;
            color: var(--app-text-muted);
            font-size: 0.86rem;
            line-height: 1.48;
        }

        .quick-start-step {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.55rem;
            height: 1.55rem;
            border-radius: 0.55rem;
            background: rgba(56, 189, 248, 0.18);
            border: 1px solid rgba(56, 189, 248, 0.34);
            color: #e0f2fe;
            font-family: var(--font-label);
            font-size: 0.82rem;
            font-weight: 800;
        }

        .inline-eyebrow {
            margin-bottom: 0.65rem;
        }

        .investor-brief-card {
            border-color: rgba(56, 189, 248, 0.44);
            background:
                radial-gradient(circle at top right, rgba(56, 189, 248, 0.16), transparent 34%),
                rgba(17, 24, 39, 0.95);
        }

        .briefing-lead-card {
            margin-top: 0.95rem;
            padding: 1rem;
            border-radius: 1rem;
            background: rgba(2, 6, 23, 0.38);
            border: 1px solid rgba(203, 213, 225, 0.22);
        }

        .briefing-symbol {
            color: #f8fafc;
            font-family: var(--font-ui);
            font-size: 1.25rem;
            font-weight: 800;
            letter-spacing: -0.025em;
        }

        .briefing-summary {
            margin-top: 0.45rem;
            color: var(--app-text-soft);
            font-size: 0.94rem;
            line-height: 1.58;
            word-break: keep-all;
            overflow-wrap: anywhere;
        }

        .briefing-meta-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.55rem;
            margin-top: 0.85rem;
        }

        .briefing-meta-grid div,
        .next-action-item,
        .watch-target-card {
            border-radius: 0.8rem;
            background: rgba(15, 23, 42, 0.76);
            border: 1px solid rgba(203, 213, 225, 0.20);
        }

        .briefing-meta-grid div {
            padding: 0.65rem;
        }

        .briefing-meta-grid span,
        .watch-target-reason {
            display: block;
            color: var(--app-text-muted);
            font-family: var(--font-label);
            font-size: 0.74rem;
            font-weight: 700;
        }

        .briefing-meta-grid strong {
            display: block;
            margin-top: 0.22rem;
            color: #f8fafc;
            font-size: 0.92rem;
        }

        .watch-target-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.65rem;
            margin-top: 0.9rem;
        }

        .watch-target-card {
            padding: 0.82rem;
        }

        .watch-target-card strong {
            display: block;
            margin-top: 0.32rem;
            color: #f8fafc;
            font-size: 0.98rem;
        }

        .watch-target-card span {
            display: inline-block;
            margin-top: 0.35rem;
            border-radius: 999px;
            padding: 0.18rem 0.48rem;
            color: #e0f2fe;
            background: rgba(56, 189, 248, 0.16);
            border: 1px solid rgba(56, 189, 248, 0.26);
            font-family: var(--font-label);
            font-size: 0.74rem;
            font-weight: 800;
        }

        .watch-target-card p,
        .next-action-item p {
            margin: 0.45rem 0 0 0;
            color: var(--app-text-muted);
            font-size: 0.84rem;
            line-height: 1.5;
            word-break: keep-all;
            overflow-wrap: anywhere;
        }

        .next-action-list {
            display: grid;
            gap: 0.62rem;
            margin-top: 0.9rem;
        }

        .next-action-item {
            padding: 0.78rem 0.85rem;
        }

        .next-action-item strong {
            color: #f8fafc;
            font-size: 0.92rem;
        }

        .symbol-strip-card {
            margin: 0.85rem 0;
        }

        .symbol-card-grid,
        .readiness-card-grid,
        .backtest-result-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.65rem;
            margin-top: 0.9rem;
        }

        .symbol-focus-card,
        .readiness-card,
        .backtest-result-card,
        .selection-summary-card div,
        .backtest-step-grid div {
            border-radius: 0.9rem;
            background: rgba(15, 23, 42, 0.78);
            border: 1px solid rgba(203, 213, 225, 0.22);
            padding: 0.82rem;
        }

        .symbol-focus-topline,
        .readiness-symbol,
        .selection-summary-card span,
        .backtest-step-grid span {
            color: var(--app-text-muted);
            font-family: var(--font-label);
            font-size: 0.74rem;
            font-weight: 800;
        }

        .symbol-focus-card strong,
        .readiness-card strong,
        .backtest-result-card strong,
        .selection-summary-card strong,
        .backtest-step-grid strong {
            display: block;
            margin-top: 0.3rem;
            color: #f8fafc;
            font-size: 0.95rem;
            line-height: 1.35;
        }

        .symbol-focus-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin-top: 0.45rem;
        }

        .symbol-focus-badges span,
        .readiness-card span {
            display: inline-flex;
            width: fit-content;
            border-radius: 999px;
            padding: 0.18rem 0.48rem;
            color: #e0f2fe;
            background: rgba(56, 189, 248, 0.16);
            border: 1px solid rgba(56, 189, 248, 0.26);
            font-family: var(--font-label);
            font-size: 0.72rem;
            font-weight: 800;
        }

        .symbol-focus-card p,
        .readiness-card p,
        .backtest-result-card p,
        .backtest-step-grid p {
            margin: 0.45rem 0 0 0;
            color: var(--app-text-muted);
            font-size: 0.82rem;
            line-height: 1.48;
            word-break: keep-all;
            overflow-wrap: anywhere;
        }

        .backtest-result-card .backtest-result-interpretation {
            margin-top: 0.65rem;
            padding-top: 0.6rem;
            border-top: 1px solid rgba(203, 213, 225, 0.16);
            color: var(--app-text-soft);
        }

        .report-focus-card {
            padding: 1rem;
            border-radius: 1rem;
            background:
                radial-gradient(circle at top right, rgba(56, 189, 248, 0.13), transparent 32%),
                rgba(15, 23, 42, 0.80);
            border: 1px solid rgba(56, 189, 248, 0.28);
        }

        .report-focus-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
        }

        .report-focus-summary {
            margin-top: 0.65rem;
            color: var(--app-text-soft);
            font-size: 0.94rem;
            line-height: 1.58;
            word-break: keep-all;
            overflow-wrap: anywhere;
        }

        .report-focus-meta,
        .selection-summary-card,
        .backtest-step-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.65rem;
            margin-top: 0.85rem;
        }

        .report-focus-meta div {
            border-radius: 0.75rem;
            background: rgba(2, 6, 23, 0.28);
            border: 1px solid rgba(203, 213, 225, 0.18);
            padding: 0.65rem;
        }

        .report-focus-meta span {
            color: var(--app-text-muted);
            font-family: var(--font-label);
            font-size: 0.72rem;
            font-weight: 800;
        }

        .report-focus-meta strong {
            display: block;
            margin-top: 0.22rem;
            color: #f8fafc;
            font-size: 0.9rem;
        }

        .watchlist-brief-card {
            margin-top: 0.85rem;
            border-color: rgba(34, 197, 94, 0.30);
        }

        .backtest-flow-card {
            margin-bottom: 0.85rem;
        }

        .backtest-step-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .backtest-step-grid span {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.5rem;
            height: 1.5rem;
            border-radius: 0.52rem;
            color: #e0f2fe;
            background: rgba(56, 189, 248, 0.18);
            border: 1px solid rgba(56, 189, 248, 0.32);
        }

        .selection-summary-card {
            margin: 0.85rem 0;
        }

        .readiness-card-ready {
            border-color: rgba(34, 197, 94, 0.32);
        }

        .readiness-card-blocked {
            border-color: rgba(248, 113, 113, 0.34);
        }

        .backtest-result-value {
            margin-top: 0.4rem;
            color: #f8fafc;
            font-family: var(--font-ui);
            font-size: 1.35rem;
            font-weight: 850;
            letter-spacing: -0.03em;
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

        .interpretation-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
            gap: 0.9rem;
            align-items: stretch;
            margin-top: 0.75rem;
        }

        .interpretation-card,
        .interpretation-reason-card {
            min-width: 0;
            padding: 1rem;
            border-radius: 1rem;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid var(--app-border);
            box-shadow: 0 10px 24px rgba(2, 6, 23, 0.20);
            overflow-wrap: anywhere;
            word-break: keep-all;
            line-height: 1.5;
        }

        .interpretation-card-header {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            align-items: flex-start;
            margin-bottom: 0.75rem;
        }

        .interpretation-card h4 {
            margin: 0.18rem 0 0 0;
            font-size: 1rem;
            line-height: 1.35;
            color: var(--app-text);
            overflow-wrap: anywhere;
        }

        .interpretation-pill {
            flex: 0 0 auto;
            max-width: 8rem;
            padding: 0.28rem 0.55rem;
            border-radius: 999px;
            background: rgba(56, 189, 248, 0.18);
            border: 1px solid rgba(56, 189, 248, 0.38);
            color: var(--app-text);
            font-size: 0.78rem;
            font-weight: 800;
            line-height: 1.35;
            text-align: center;
            white-space: normal;
        }

        .interpretation-signal-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.45rem;
        }

        .interpretation-signal-cell {
            min-width: 0;
            padding: 0.58rem 0.62rem;
            border-radius: 0.75rem;
            background: rgba(2, 6, 23, 0.52);
            border: 1px solid rgba(203, 213, 225, 0.20);
        }

        .interpretation-signal-cell span {
            display: block;
            color: var(--app-text-muted);
            font-size: 0.74rem;
            line-height: 1.3;
        }

        .interpretation-signal-cell strong {
            display: block;
            margin-top: 0.14rem;
            color: var(--app-text);
            font-size: 0.86rem;
            line-height: 1.35;
            white-space: normal;
            overflow-wrap: anywhere;
        }

        .interpretation-summary,
        .interpretation-reason-card p {
            margin: 0.75rem 0 0 0;
            color: var(--app-text-soft);
            font-size: 0.9rem;
            line-height: 1.55;
            white-space: normal;
            overflow-wrap: anywhere;
            word-break: keep-all;
        }

        .interpretation-reason-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
            gap: 0.7rem;
        }

        .interpretation-reason-title {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem 0.55rem;
            align-items: baseline;
            line-height: 1.4;
        }

        .interpretation-reason-title strong {
            color: var(--app-text);
        }

        .interpretation-reason-title span {
            color: var(--app-text-muted);
            font-size: 0.85rem;
        }

        .glossary-guide-box {
            margin-top: 0.9rem;
        }

        .glossary-guide-box ol {
            margin: 0.55rem 0 0 1.15rem;
            padding: 0;
        }

        .glossary-guide-box li {
            margin: 0.38rem 0;
            color: var(--app-text-soft);
            line-height: 1.55;
            word-break: keep-all;
            overflow-wrap: anywhere;
        }


        </style>
        """,
        unsafe_allow_html=True,
    )
