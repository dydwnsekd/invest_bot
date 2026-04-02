from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from invest_bot.dashboard.service import DashboardDataService


class DashboardHandler(BaseHTTPRequestHandler):
    service = DashboardDataService()

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in {"/", "/index.html"}:
            self.send_error(404, "Not Found")
            return

        content = self.service.render_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def run_dashboard(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"dashboard running at http://{host}:{port}")
    server.serve_forever()
