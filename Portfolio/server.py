"""
Local development server for the Portfolio site.

Serves static files AND proxies weather API requests so the browser
never hits a cross-origin (CORS) error.

Usage:
    python server.py            # serves on http://localhost:8080
    python server.py 3000       # serves on http://localhost:3000
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8080

# Local path -> UAPI upstream (proxied to avoid browser CORS errors)
UAPI_ROUTES = {
    "/api/weather": "https://uapis.cn/api/v1/misc/weather",
    "/api/worldtime": "https://uapis.cn/api/v1/misc/worldtime",
}


class ProxyHandler(SimpleHTTPRequestHandler):
    """Serve static files, and proxy /api/* requests to the UAPI APIs."""

    def end_headers(self):
        # Allow cross-origin requests from anywhere (dev only)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        # Proxy API requests to the matching UAPI upstream
        if parsed.path in UAPI_ROUTES:
            self._proxy_uapi(UAPI_ROUTES[parsed.path], parsed.query)
            return

        # Everything else: serve as a static file
        super().do_GET()

    def _proxy_uapi(self, target_base, query_string):
        params = urllib.parse.parse_qs(query_string)
        city = params.get("city", [""])[0]

        if not city:
            self._send_json(400, {"error": "CITY_REQUIRED"})
            return

        target_url = target_base + "?city=" + urllib.parse.quote(city)

        try:
            req = urllib.request.Request(
                target_url,
                headers={"User-Agent": "PortfolioWeatherApp/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                self.send_response(resp.status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(raw.encode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            self._send_json(e.code, json.loads(body) if body else {"error": "HTTP_ERROR"})
        except Exception as e:
            self._send_json(502, {"error": "PROXY_ERROR", "details": str(e)})

    def _send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Quiet logging (only print errors)
        sys.stderr.write("%s - - [%s] %s\n" %
                         (self.address_string(), self.log_date_time_string(), format % args))


def main():
    # Always serve static files from the directory where server.py lives,
    # regardless of the working directory the script was launched from.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Usage: python server.py [port]")
            sys.exit(1)

    server = HTTPServer(("0.0.0.0", port), ProxyHandler)
    print("=" * 50)
    print("Portfolio server running:")
    print("  Home:     http://localhost:%d/index.html" % port)
    print("  Projects: http://localhost:%d/projects.html  (Weather App)" % port)
    print("  Weather proxy: http://localhost:%d/api/weather?city=Beijing" % port)
    print("  World time proxy: http://localhost:%d/api/worldtime?city=Tokyo" % port)
    print("Press Ctrl+C to stop.")
    print("=" * 50)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
