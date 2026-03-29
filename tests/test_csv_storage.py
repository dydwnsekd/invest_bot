from __future__ import annotations

from pathlib import Path

import pandas as pd

from invest_bot.market.storage import CsvStorage


def test_csv_storage_saves_frame_to_expected_dataset_directory(tmp_path: Path):
    storage = CsvStorage(tmp_path)
    frame = pd.DataFrame([{"symbol": "005930", "close": 70000}])

    result = storage.save("daily_prices", "005930_20260301_20260329.csv", frame)

    assert result.rows == 1
    assert result.path.exists()
    assert result.path.parent == tmp_path / "daily_prices"
