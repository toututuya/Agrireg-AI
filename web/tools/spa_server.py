"""Serve a built Vue SPA with history-mode route fallback.

Usage: python tools/spa_server.py --directory dist --port 8082
"""

from __future__ import annotations

import argparse
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class SpaRequestHandler(SimpleHTTPRequestHandler):
    """Return index.html for client-side routes such as /graph."""

    def send_head(self):
        route_path = urlsplit(self.path).path
        local_path = Path(self.translate_path(route_path))

        if not local_path.exists() and "." not in Path(route_path).name:
            self.path = "/index.html"

        return super().send_head()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a built Vue SPA locally.")
    parser.add_argument("--directory", default="dist", help="Built asset directory")
    parser.add_argument("--host", default="127.0.0.1", help="Listen address")
    parser.add_argument("--port", type=int, default=8082, help="Listen port")
    args = parser.parse_args()

    root = Path(args.directory).resolve()
    if not (root / "index.html").is_file():
        raise SystemExit(f"Missing {root / 'index.html'}; run the production build first.")

    os.chdir(root)
    server = ThreadingHTTPServer((args.host, args.port), SpaRequestHandler)
    print(f"AgriReg AI web preview: http://{args.host}:{args.port}/graph", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
