from __future__ import annotations

import pandas as pd

from invest_bot.market.storage import CsvStorage
from tests.helpers import make_test_dir


def test_csv_storage_saves_frame_to_expected_dataset_directory():
    test_dir = make_test_dir("csv_storage")
    storage = CsvStorage(test_dir)
    frame = pd.DataFrame([{"symbol": "005930", "close": 70000}])

    result = storage.save("daily_prices", "005930_20260301_20260329.csv", frame)

    assert result.rows == 1
    assert result.path.exists()
    assert result.path.parent == test_dir / "daily_prices"
