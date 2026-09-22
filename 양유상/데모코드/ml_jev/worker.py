"""A separate loopback worker keeps one actual SemIf GGUF model warm."""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .engine import SemIfClassifier, json_classify, COMMIT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8814)
    args = parser.parse_args()
    classifier = SemIfClassifier()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, data):
            payload = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path != '/health':
                return self.send(404, {'error': 'not_found'})
            self.send(200, {'status': 'ready', 'model': 'Qwen3-4B Q4_K_M', 'backend': 'actual_semif_llamacpp',
                'semif_commit': COMMIT, 'external_inference': False, 'load_seconds': classifier.load_seconds,
                'model_metadata': classifier.metadata, 'official_typesafe_jev_executed': False, 'busy': lock.locked()})

        def do_POST(self):
            if self.path != '/classify':
                return self.send(404, {'error': 'not_found'})
            if not lock.acquire(blocking=False):
                return self.send(409, {'error': 'local_model_busy'})
            try:
                size = int(self.headers.get('Content-Length', 0))
                if size < 1 or size > 20000:
                    return self.send(413, {'error': 'invalid_input_size'})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('JSON object required')
                method = body.get('method', 'semif')
                if method not in ('semif', 'json'):
                    raise ValueError('Unknown method')
                kwargs = {key: body.get(key, '') for key in ('text', 'field_path', 'description')}
                kwargs['input_mode'] = body.get('input_mode', 'full')
                if method == 'semif':
                    kwargs['reverse_options'] = body.get('reverse_options', False) is True
                    result = classifier.classify(**kwargs)
                else:
                    result = json_classify(**kwargs)
                self.send(200, result)
            except (ValueError, TypeError) as error:
                self.send(400, {'error': str(error)})
            except Exception as error:
                self.send(503, {'error': type(error).__name__})
            finally:
                lock.release()

        def log_message(self, format, *args):
            # No body or real user text is logged.
            pass

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(json.dumps({'status': 'ready', 'port': args.port, 'backend': 'actual_semif_llamacpp', 'load_seconds': classifier.load_seconds}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
