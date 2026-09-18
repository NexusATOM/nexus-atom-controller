"""Local read-only inspection API. Execution stays in the controlled CLI process."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .store import Store


def serve(root: Path, host="127.0.0.1", port=8765):
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Inspection service binds to loopback only")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = urlsplit(self.path).path.strip("/").split("/")
            store = Store(root)
            try:
                if route == ["health"]:
                    value = {"status": "ok", "read_only": True}
                elif len(route) == 2 and route[0] == "goals":
                    value = store.goal(store.load_goal(route[1]))
                elif len(route) == 3 and route[0] == "goals" and route[2] == "experiments":
                    value = [e.model_dump(mode="json") for e in store.history(route[1])]
                else:
                    self.send_error(404)
                    return
                data = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except KeyError:
                self.send_error(404)
            except ValueError:
                self.send_error(409, "Evidence integrity check failed")
            finally:
                store.close()

    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
