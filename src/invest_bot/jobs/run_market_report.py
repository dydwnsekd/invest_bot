from __future__ import annotations

from invest_bot.jobs.generate_market_report import MarketReportGenerator, MarketReportRequest


def main() -> None:
    generator = MarketReportGenerator()
    request = MarketReportRequest(
        symbol="005930",
        indicator_filename="005930_20260301_20260329.csv",
        signal_filename="005930_20260301_20260329.csv",
        investor_filename="005930_20260329.csv",
    )
    indicator_frame = generator.load_indicator_frame(request)
    signal_frame = generator.load_signal_frame(request)
    investor_frame = generator.load_investor_frame(request)
    stock_info_frame = generator.load_stock_info_frame(request)

    report = generator.generate_report(
        request=request,
        indicator_frame=indicator_frame,
        signal_frame=signal_frame,
        investor_frame=investor_frame,
        stock_info_frame=stock_info_frame,
    )
    saved = generator.save_report("005930_20260329.csv", report)
    print({"rows": len(report), "saved_path": str(saved.path)})


if __name__ == "__main__":
    main()
