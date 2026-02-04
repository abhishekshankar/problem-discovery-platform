from __future__ import annotations

import json
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


class IngestHandler(BaseHTTPRequestHandler):
    signal_path: Path = Path("data/devvit_signals.jsonl")

    def _write(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/ingest":
            self._write(404, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            self._write(400, {"error": "empty_body"})
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._write(400, {"error": "invalid_json"})
            return

        self.signal_path.parent.mkdir(parents=True, exist_ok=True)
        with self.signal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload))
            handle.write("\n")

        self._write(200, {"status": "ok"})


def run_server(host: str = "0.0.0.0", port: int = 8089, signal_path: str | None = None) -> None:
    if signal_path:
        IngestHandler.signal_path = Path(signal_path)
    server = HTTPServer((host, port), IngestHandler)
    print(f"Ingest server listening on http://{host}:{port}/ingest")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Devvit ingest server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8089)
    parser.add_argument("--signal-path", dest="signal_path", default=None)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, signal_path=args.signal_path)
