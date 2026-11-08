from datetime import date
import hashlib
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from invest_bot.backtest import resolve_backtest_combination_settings
from invest_bot.backtest.persistence import read_combination_metadata
from invest_bot.dashboard import streamlit_backtest as app
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.market.storage import CsvStorage
from tests.test_streamlit_backtest import _FakeStreamlit, _loaded_inputs


def batch(*, saved_signal=False, custom_ma=False):
    frame = pd.DataFrame({
        'date': pd.date_range('2026-04-01', periods=5), 'close': [100., 50., 80., 110., 100.],
        'rsi_14': [50., 35., 50., 65., 50.], 'ma_5': [98., 100., 102., 99., 98.],
        'ma_20': [99., 99., 100., 100., 100.], 'ma_60': [97.] * 5, 'momentum_20': [0.] * 5,
    })
    signal = frame[['date', 'close']].assign(signal=['hold', 'buy', 'hold', 'sell', 'hold']) if saved_signal else None
    inputs = _loaded_inputs(indicator=frame, price=frame[['date', 'close']], golden_signal=signal)
    parameters = {'rsi': {'buy_threshold': 40., 'sell_threshold': 60.}}
    if custom_ma:
        parameters['golden-cross'] = {'short_window': 2., 'long_window': 3.}
    return app._execute_backtests(
        [app.ResolvedSymbol('005930', '005930', '가상 종목')], ['rsi', 'golden-cross'], {'005930': inputs},
        strategy_parameters=parameters,
        combination_settings=resolve_backtest_combination_settings(['rsi', 'golden-cross']),
        preparation_period=(date(2025, 4, 1), date(2026, 4, 1)),
    )


def combo(result):
    return result['summary_frame'].query("strategy_id == 'combination-and'").iloc[0]


@pytest.mark.parametrize('saved_signal,custom_ma,used', [(False, False, False), (True, False, True), (True, True, False)])
def test_real_execute_captures_effective_component_settings_and_actual_sources(saved_signal, custom_ma, used):
    result = batch(saved_signal=saved_signal, custom_ma=custom_ma)
    metadata = read_combination_metadata(combo(result).combination_settings_json)
    assert metadata.status == 'recorded'
    components = metadata.metadata['components']
    assert components['rsi']['strategy_parameters'] == {'buy_threshold': 40., 'sell_threshold': 60.}
    assert components['golden-cross']['uses_saved_signal'] is used
    assert components['golden-cross']['input_sources']['signal'] == (
        {'dataset': 'golden_cross_signals', 'filename': '005930_signals.csv'} if used else {'dataset': None, 'filename': None}
    )
    assert components['rsi']['input_sources']['indicator']['filename'] == '005930_indicators.csv'
    assert components['rsi']['input_sources']['investor'] == {'dataset': None, 'filename': None}
    assert components['rsi']['input_sources']['price'] == {'dataset': None, 'filename': None}
    row = combo(result)
    assert row.input_row_count == 5 and row.prepare_lookback_days == 365
    trades = result['trade_frame'].query("strategy_id == 'combination-and'")
    if not trades.empty:
        assert trades.combination_settings_json.eq(row.combination_settings_json).all()


def test_recorded_component_display_is_frozen_after_widget_change(monkeypatch):
    result = batch()
    screen = _FakeStreamlit()
    screen.session_state[app.BACKTEST_PARAMETERS_KEY] = {'rsi': {'buy_threshold': 20, 'sell_threshold': 80}}
    monkeypatch.setattr(app, 'st', screen)
    text = app._strategy_parameter_summary_from_row(combo(result))
    assert 'RSI' in text and '40' in text and '60' in text and '20' not in text.split('RSI')[-1].split('·')[0]
    assert '위 비교 결과' not in text


@pytest.mark.parametrize('metadata,expected', [({}, '기록 없음'), ({'metadata_version': 99}, '미지원'), ({'metadata_version': 1}, '잘못된')])
def test_history_component_display_does_not_guess_missing_or_unsupported_settings(metadata, expected):
    row = pd.Series({'strategy_id': 'combination-and', 'combination_settings_json': json.dumps(metadata),
                     'strategy_parameter_summary': '조합 전략: 개별 전략 설정은 위 비교 결과에서 확인'})
    assert expected in app._strategy_parameter_summary_from_row(row)


def test_save_panel_does_not_touch_storage_until_click(monkeypatch):
    result = batch()
    screen = _FakeStreamlit()
    monkeypatch.setattr(app, 'st', screen)
    service = SimpleNamespace(get_dataset_storage=lambda: pytest.fail('storage touched without click'))
    app._render_save_results_panel(service, result)
    assert '실행 결과 저장' in screen.button_labels
    assert any('3' in text and '005930' in text for text in screen.caption_calls)


def test_explicit_save_then_new_service_history_retains_identity_settings_and_metrics(monkeypatch, tmp_path):
    result = batch(saved_signal=True)
    row = combo(result).copy()
    screen = _FakeStreamlit(button_values={'backtest_save_results': True})
    monkeypatch.setattr(app, 'st', screen)
    monkeypatch.setattr(app.DEFAULT_BACKTEST_RUNNER, 'run', lambda *_: pytest.fail('save/history executed runner'))
    service = DashboardDataService(raw_root=tmp_path/'raw', processed_root=tmp_path/'processed')
    app._render_save_results_panel(service, result)
    files = sorted((tmp_path/'processed').glob('backtest_*/*.csv'))
    assert len(files) == 6 and screen.success_messages and not screen.error_messages
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    app._render_save_results_panel(service, result)
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    fresh = DashboardDataService(raw_root=tmp_path/'raw', processed_root=tmp_path/'processed')
    entries, errors = app._load_backtest_history_entries(fresh)
    assert not errors and len(entries) == 3 and {entry['symbol'] for entry in entries} == {'005930'}
    entry = next(entry for entry in entries if entry['strategy_id'] == 'combination-and')
    assert entry['source_label'] == '005930_indicators.csv'
    loaded, errors = app._load_backtest_history_result(fresh, entry)
    assert not errors
    stored = loaded['summary_frame'].iloc[0]
    for key in ['run_id', 'combination_settings_json', 'input_start_date', 'input_end_date',
                'input_row_count', 'prepare_lookback_days']:
        assert stored[key] == row[key]
    for key in ['total_return_pct', 'final_equity', 'max_drawdown_pct']:
        assert stored[key] == pytest.approx(row[key], rel=1e-12, abs=1e-12)
    assert loaded['trade_frame']['symbol'].eq('005930').all()
    assert '40' in app._strategy_parameter_summary_from_row(stored)


def test_duplicate_save_is_rejected_without_overwriting(monkeypatch, tmp_path):
    result = batch()
    service = DashboardDataService(raw_root=tmp_path/'raw', processed_root=tmp_path/'processed')
    screen = _FakeStreamlit(button_values={'backtest_save_results': True})
    monkeypatch.setattr(app, 'st', screen)
    app._render_save_results_panel(service, dict(result))
    before = {p: p.read_bytes() for p in (tmp_path/'processed').glob('backtest_*/*.csv')}
    second = _FakeStreamlit(button_values={'backtest_save_results': True})
    monkeypatch.setattr(app, 'st', second)
    app._render_save_results_panel(service, dict(result))
    assert before == {p: p.read_bytes() for p in before}
    assert second.error_messages and not second.success_messages


def test_partial_save_reports_failure_and_confirmed_count(monkeypatch, tmp_path):
    result = batch()
    storage = CsvStorage(tmp_path/'processed')
    original = storage.save
    count = 0
    def fail_second(*args):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('injected write failure')
        return original(*args)
    storage.save = fail_second
    screen = _FakeStreamlit(button_values={'backtest_save_results': True})
    monkeypatch.setattr(app, 'st', screen)
    app._render_save_results_panel(SimpleNamespace(get_dataset_storage=lambda: storage), result)
    assert count == 2 and not screen.success_messages
    assert any('1' in text and '일부' in text for text in screen.error_messages)
