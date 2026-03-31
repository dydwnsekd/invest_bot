from __future__ import annotations

from pathlib import Path

import pandas as pd

from invest_bot.market.analysis import DailyPriceAnalyzer, IndicatorRequest
from invest_bot.market.storage import CsvStorage


def test_daily_price_analyzer_normalizes_and_saves_indicators(tmp_path: Path):
    raw_storage = CsvStorage(tmp_path / "raw")
    processed_storage = CsvStorage(tmp_path / "processed")
    analyzer = DailyPriceAnalyzer(raw_storage=raw_storage, processed_storage=processed_storage)

    raw_frame = pd.DataFrame(
        [
            {"stck_bsop_date": "20260301", "stck_clpr": "70000", "acml_vol": "1000"},
            {"stck_bsop_date": "20260302", "stck_clpr": "71000", "acml_vol": "1100"},
            {"stck_bsop_date": "20260303", "stck_clpr": "72000", "acml_vol": "1200"},
            {"stck_bsop_date": "20260304", "stck_clpr": "73000", "acml_vol": "1300"},
            {"stck_bsop_date": "20260305", "stck_clpr": "74000", "acml_vol": "1400"},
            {"stck_bsop_date": "20260306", "stck_clpr": "75000", "acml_vol": "1500"},
            {"stck_bsop_date": "20260307", "stck_clpr": "76000", "acml_vol": "1600"},
            {"stck_bsop_date": "20260308", "stck_clpr": "77000", "acml_vol": "1700"},
            {"stck_bsop_date": "20260309", "stck_clpr": "78000", "acml_vol": "1800"},
            {"stck_bsop_date": "20260310", "stck_clpr": "79000", "acml_vol": "1900"},
            {"stck_bsop_date": "20260311", "stck_clpr": "80000", "acml_vol": "2000"},
            {"stck_bsop_date": "20260312", "stck_clpr": "81000", "acml_vol": "2100"},
            {"stck_bsop_date": "20260313", "stck_clpr": "82000", "acml_vol": "2200"},
            {"stck_bsop_date": "20260314", "stck_clpr": "83000", "acml_vol": "2300"},
            {"stck_bsop_date": "20260315", "stck_clpr": "84000", "acml_vol": "2400"},
            {"stck_bsop_date": "20260316", "stck_clpr": "85000", "acml_vol": "2500"},
            {"stck_bsop_date": "20260317", "stck_clpr": "86000", "acml_vol": "2600"},
            {"stck_bsop_date": "20260318", "stck_clpr": "87000", "acml_vol": "2700"},
            {"stck_bsop_date": "20260319", "stck_clpr": "88000", "acml_vol": "2800"},
            {"stck_bsop_date": "20260320", "stck_clpr": "89000", "acml_vol": "2900"},
        ]
    )
    raw_storage.save("daily_prices", "005930_20260301_20260329.csv", raw_frame)

    loaded = analyzer.load_daily_prices(
        IndicatorRequest(symbol="005930", source_filename="005930_20260301_20260329.csv")
    )
    indicators = analyzer.calculate_indicators(loaded)
    saved = analyzer.save_indicators("005930_20260301_20260329.csv", indicators)

    assert "date" in loaded.columns
    assert "close" in loaded.columns
    assert "ma_5" in indicators.columns
    assert "ma_20" in indicators.columns
    assert "volume_ma_5" in indicators.columns
    assert "rsi_14" in indicators.columns
    assert indicators.iloc[4]["ma_5"] == 72000
    assert saved.path.exists()
