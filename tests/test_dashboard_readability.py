import re
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from invest_bot.dashboard import streamlit_styles
from invest_bot.dashboard.streamlit_formatters import state_text_color
from tests.g06b_readability_fixture import render_readability_fixture


def contrast_ratio(foreground, background):
    def luminance(color):
        channels = [int(color[offset:offset + 2], 16) / 255 for offset in (1, 3, 5)]
        linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
        return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_contrast_reference_black_and_white():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio("#111827", "#111827") == pytest.approx(1.0)


@pytest.mark.parametrize("state", ["buy", "sell", "hold"])
@pytest.mark.parametrize("background", ["#050816", "#0f172a", "#1e293b"])
def test_strategy_state_text_is_readable_on_all_dashboard_panel_colors(state, background):
    assert contrast_ratio(state_text_color(state), background) >= 4.5


def test_custom_text_sizes_meet_minimum_without_changing_icon_hiding(monkeypatch):
    captured = []
    monkeypatch.setattr(streamlit_styles, "st", SimpleNamespace(markdown=lambda body, **_: captured.append(body)))
    streamlit_styles.apply_custom_style()
    css = captured[0]
    sizes = [float(value) for value in re.findall(r"font-size:\s*([\d.]+)rem", css)]
    assert sizes and min(sizes) >= 0.8
    assert "font-size: 0 !important;" in css
    assert 'font-feature-settings: "liga" !important;' in css


def test_success_status_icon_uses_material_font_and_ligatures(monkeypatch):
    captured = []
    monkeypatch.setattr(streamlit_styles, "st", SimpleNamespace(markdown=lambda body, **_: captured.append(body)))
    streamlit_styles.apply_custom_style()
    blocks = re.findall(r"([^{}]+)\{([^{}]+)\}", captured[0])
    protected = [body for selector, body in blocks if '[data-testid="stExpanderIconCheck"]' in selector]
    assert any('font-family: "Material Symbols Rounded"' in body and 'font-feature-settings: "liga" !important;' in body for body in protected)


@pytest.mark.parametrize("opinion", ["buy", "sell", "hold"])
def test_actual_report_renderer_keeps_all_three_strategy_states_readable(opinion):
    app = AppTest.from_function(render_readability_fixture, default_timeout=15).run()
    app.selectbox[0].set_value(opinion).run()
    assert not app.exception
    html = "\n".join(item.value for item in app.markdown)
    colors = re.findall(r"<span style='color:(#[0-9a-f]{6});font-weight:700;'", html)
    assert len(colors) == 3
    assert len(set(colors)) == 3
    assert all(contrast_ratio(color, "#0f172a") >= 4.5 for color in colors)
    assert "매수 상태 표본" in html and "매도 상태 표본" in html and "중립 상태 표본" in html


@pytest.mark.parametrize("view", ["관심종목", "해석 모아보기"])
def test_other_read_views_render_status_labels_without_backing_storage(view):
    app = AppTest.from_function(render_readability_fixture, default_timeout=15).run()
    app.radio[0].set_value(view).run()
    assert not app.exception
    html = "\n".join(item.value for item in app.markdown)
    assert ("watchlist-status-card__dates" if view == "관심종목" else "interpretation-signal-cell") in html
