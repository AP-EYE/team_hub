"""Loopback-only JSON worker. Start: .venv-model/Scripts/python -m ml.worker"""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ml.engine import LocalClassifier, MODEL_ID
from ml.normalize import normalize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8812)
    args = parser.parse_args()
    engine = LocalClassifier()
    inference_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, data):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != "/health":
                return self.respond(404, {"error": "not_found"})
            self.respond(200, {"status": "ready", "model": MODEL_ID, "revision": engine.revision, "backend": "cpu_direct_logits", "external_inference": False, "calibrated": False})

        def do_POST(self):
            if self.path not in ("/classify", "/normalize"):
                return self.respond(404, {"error": "not_found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 32768:
                    return self.respond(413, {"error": "invalid_input_size"})
                state = json.loads(self.rfile.read(length))
                if not isinstance(state, dict):
                    raise ValueError("JSON object required")
                with inference_lock:
                    if self.path == "/normalize":
                        result = normalize(engine, state.get("field_path", ""), state.get("description", ""))
                    else:
                        result = engine.classify(state.get("text", ""), state.get("field_path", ""), state.get("description", ""))
                self.respond(200, result)
            except (ValueError, TypeError) as exc:
                self.respond(400, {"error": str(exc)})

        def log_message(self, message, *args):
            # Never log request bodies or user values.
            print(message % args, flush=True)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(json.dumps({"status": "ready", "port": args.port, "load_seconds": engine.load_seconds}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
