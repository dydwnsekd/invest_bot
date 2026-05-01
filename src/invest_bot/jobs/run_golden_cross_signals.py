from __future__ import annotations

from invest_bot.jobs.generate_golden_cross_signals import (
    GoldenCrossSignalGenerator,
    GoldenCrossSignalRequest,
)


def main() -> None:
    generator = GoldenCrossSignalGenerator()
    request = GoldenCrossSignalRequest(
        symbol="005930",
        source_filename="005930_20260301_20260329.csv",
    )
    indicator_frame = generator.load_indicator_frame(request)
    signal_frame = generator.generate_signals(indicator_frame)
    saved = generator.save_signals(request.source_filename, signal_frame)
    print(
        {
            "indicator_rows": len(indicator_frame),
            "signal_rows": len(signal_frame),
            "saved_path": str(saved.path),
        }
    )


if __name__ == "__main__":
    main()
