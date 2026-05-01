from __future__ import annotations

import pandas as pd

from invest_bot.jobs.generate_golden_cross_signals import (
    GoldenCrossSignalGenerator,
    GoldenCrossSignalRequest,
)
from invest_bot.market.storage import CsvStorage
from tests.helpers import make_test_dir


def test_golden_cross_signal_generator_loads_generates_and_saves_signals():
    test_dir = make_test_dir("golden_cross_signal_generator")
    processed_storage = CsvStorage(test_dir / "processed")
    generator = GoldenCrossSignalGenerator(processed_storage=processed_storage)

    indicator_frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "ma_5": 98.0, "ma_20": 100.0},
            {"date": "2026-04-02", "close": 101, "ma_5": 101.0, "ma_20": 100.0},
            {"date": "2026-04-03", "close": 99, "ma_5": 99.0, "ma_20": 100.0},
        ]
    )
    processed_storage.save("daily_prices_indicators", "005930_signals.csv", indicator_frame)

    loaded = generator.load_indicator_frame(
        GoldenCrossSignalRequest(symbol="005930", source_filename="005930_signals.csv")
    )
    signals = generator.generate_signals(loaded)
    saved = generator.save_signals("005930_signals.csv", signals)

    assert saved.path.exists()
    assert signals.iloc[0]["signal"] == "hold"
    assert signals.iloc[1]["signal"] == "buy"
    assert signals.iloc[2]["signal"] == "sell"
    assert "signal_reason" in signals.columns
    assert "signal_prev_ma_5" in signals.columns
