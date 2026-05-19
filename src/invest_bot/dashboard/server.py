from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.jobs.analyze_daily_prices import generate_indicators_for_symbol
from invest_bot.jobs.collect_market_data import collect_market_data_for_symbols
from invest_bot.jobs.run_market_report import generate_market_report_for_symbol
from invest_bot.jobs.run_golden_cross_signals import generate_golden_cross_signals_for_symbol


class DashboardHandler(BaseHTTPRequestHandler):
    service = DashboardDataService()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in {"/", "/index.html"}:
            self.send_error(404, "Not Found")
            return

        query = parse_qs(parsed.query)
        message = query.get("message", [""])[0]
        message_type = query.get("message_type", ["info"])[0]
        content = self.service.render_html(message=message, message_type=message_type).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/actions/collect-market-data":
            self._handle_collect_market_data()
            return
        if parsed.path == "/actions/analyze-daily-prices":
            self._handle_analyze_daily_prices()
            return
        if parsed.path == "/actions/generate-golden-cross-signals":
            self._handle_generate_golden_cross_signals()
            return
        if parsed.path == "/actions/generate-market-report":
            self._handle_generate_market_report()
            return
        if parsed.path == "/actions/run-full-pipeline":
            self._handle_run_full_pipeline()
            return

        self.send_error(404, "Not Found")

    def _handle_collect_market_data(self) -> None:
        form = self._read_form_body()
        symbols_text = (form.get("symbols", ["005930"])[0] or "005930").strip()
        days_text = (form.get("days", ["30"])[0] or "30").strip()

        try:
            days = max(int(days_text), 1)
        except ValueError:
            days = 30

        symbols = [token.strip() for token in symbols_text.replace(",", "\n").splitlines() if token.strip()]

        try:
            result = collect_market_data_for_symbols(symbols=symbols, days=days)
            message = (
                f"데이터 수집을 완료했습니다. 종목 {result['symbol_count']}개 중 "
                f"{result['success_count']}개 성공, {result['failed_count']}개 실패입니다."
            )
            message_type = "success" if result["failed_count"] == 0 else "info"
        except Exception as error:  # noqa: BLE001
            message = f"데이터 수집 중 오류가 발생했습니다: {error}"
            message_type = "error"

        self._redirect_with_message(message=message, message_type=message_type)

    def _handle_generate_market_report(self) -> None:
        form = self._read_form_body()
        symbol = (form.get("symbol", ["005930"])[0] or "005930").strip()

        try:
            result = generate_market_report_for_symbol(symbol)
            message = f"{symbol} 시장 리포트를 생성했습니다. 저장 위치: {result['saved_path']}"
            message_type = "success"
        except FileNotFoundError as error:
            message = str(error)
            message_type = "error"
        except Exception as error:  # noqa: BLE001
            message = f"리포트 생성 중 오류가 발생했습니다: {error}"
            message_type = "error"

        self._redirect_with_message(message=message, message_type=message_type)

    def _handle_analyze_daily_prices(self) -> None:
        form = self._read_form_body()
        symbol = (form.get("symbol", ["005930"])[0] or "005930").strip()

        try:
            result = generate_indicators_for_symbol(symbol)
            message = f"{symbol} 지표 계산을 완료했습니다. 저장 위치: {result['saved_path']}"
            message_type = "success"
        except FileNotFoundError as error:
            message = str(error)
            message_type = "error"
        except Exception as error:  # noqa: BLE001
            message = f"지표 계산 중 오류가 발생했습니다: {error}"
            message_type = "error"

        self._redirect_with_message(message=message, message_type=message_type)

    def _handle_generate_golden_cross_signals(self) -> None:
        form = self._read_form_body()
        symbol = (form.get("symbol", ["005930"])[0] or "005930").strip()

        try:
            result = generate_golden_cross_signals_for_symbol(symbol)
            message = f"{symbol} 골든크로스 신호 생성을 완료했습니다. 저장 위치: {result['saved_path']}"
            message_type = "success"
        except FileNotFoundError as error:
            message = str(error)
            message_type = "error"
        except Exception as error:  # noqa: BLE001
            message = f"골든크로스 신호 생성 중 오류가 발생했습니다: {error}"
            message_type = "error"

        self._redirect_with_message(message=message, message_type=message_type)

    def _handle_run_full_pipeline(self) -> None:
        form = self._read_form_body()
        symbols_text = (form.get("symbols", ["005930"])[0] or "005930").strip()
        days_text = (form.get("days", ["30"])[0] or "30").strip()
        symbols = [token.strip() for token in symbols_text.replace(",", "\n").splitlines() if token.strip()]

        try:
            days = max(int(days_text), 1)
        except ValueError:
            days = 30

        try:
            collect_result = collect_market_data_for_symbols(symbols=symbols, days=days)
            pipeline_symbols = collect_result["symbols"]
            analyzed = [generate_indicators_for_symbol(symbol) for symbol in pipeline_symbols]
            signaled = [generate_golden_cross_signals_for_symbol(symbol) for symbol in pipeline_symbols]
            reported = [generate_market_report_for_symbol(symbol) for symbol in pipeline_symbols]
            message = (
                f"전체 파이프라인을 완료했습니다. 수집 {collect_result['success_count']}/{collect_result['symbol_count']} 성공, "
                f"지표 계산 {len(analyzed)}건, 신호 생성 {len(signaled)}건, 리포트 생성 {len(reported)}건입니다."
            )
            message_type = "success" if collect_result["failed_count"] == 0 else "info"
        except FileNotFoundError as error:
            message = str(error)
            message_type = "error"
        except Exception as error:  # noqa: BLE001
            message = f"전체 파이프라인 실행 중 오류가 발생했습니다: {error}"
            message_type = "error"

        self._redirect_with_message(message=message, message_type=message_type)

    def _read_form_body(self) -> dict[str, list[str]]:
        content_length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(content_length).decode("utf-8")
        return parse_qs(payload)

    def _redirect_with_message(self, message: str, message_type: str) -> None:
        redirect_path = f"/?message={quote(message, safe='')}&message_type={quote(message_type, safe='')}"
        self.send_response(303)
        self.send_header("Location", redirect_path)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def run_dashboard(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"dashboard running at http://{host}:{port}")
    server.serve_forever()
