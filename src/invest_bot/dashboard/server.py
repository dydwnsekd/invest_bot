from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.jobs.run_market_report import generate_market_report_for_symbol


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
        if parsed.path != "/actions/generate-market-report":
            self.send_error(404, "Not Found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(content_length).decode("utf-8")
        form = parse_qs(payload)
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

        redirect_path = (
            f"/?message={quote(message, safe='')}&message_type={quote(message_type, safe='')}"
        )
        self.send_response(303)
        self.send_header("Location", redirect_path)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def run_dashboard(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"dashboard running at http://{host}:{port}")
    server.serve_forever()
