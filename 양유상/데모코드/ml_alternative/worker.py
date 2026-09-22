"""Loopback wrapper on 8813; existing Ollama remains separately managed."""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from .engine import MODEL, classify, endpoint
from .normalize import normalize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8813)
    args = parser.parse_args()
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
            try:
                response = httpx.get(endpoint()+"/api/tags", timeout=3, trust_env=False)
                response.raise_for_status()
                models = response.json().get("models", [])
                metadata = next((x for x in models if x["name"]==MODEL), None)
                if metadata is None:
                    return self.respond(503, {"status": "model_unavailable", "model": MODEL})
                self.respond(200, {"status": "ready", "model": MODEL, "revision": metadata["digest"], "backend": "ollama_cpu_structured_generation", "source": "live_local_ollama", "external_inference": False, "calibrated": False, "ollama_endpoint": endpoint()})
            except Exception:
                self.respond(503, {"status": "ollama_unavailable", "model": MODEL})

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
                        result = normalize(state.get("field_path", ""), state.get("description", ""))
                    else:
                        result = classify(state.get("text", ""), state.get("field_path", ""), state.get("description", ""))
                self.respond(200, result)
            except (ValueError, TypeError) as exc:
                self.respond(400, {"error": str(exc)})
            except httpx.HTTPError:
                self.respond(503, {"error": "local_model_unavailable"})

        def log_message(self, message, *args):
            print(message % args, flush=True)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(json.dumps({"status": "wrapper_ready", "port": args.port, "model": MODEL, "ollama_endpoint": endpoint()}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
