#!/usr/bin/env python3
"""
Live-reload dev server for Atharva's portfolio.
- Serves files on http://localhost:5500
- Watches .html / .css / .js files for changes
- Auto-refreshes the browser via SSE (no browser extension needed)
"""

import http.server, os, sys, time, threading, hashlib
from functools import partial

PORT = 5500
WATCH_EXTS = {'.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.webp'}
RELOAD_SCRIPT = b"""
<script>
(function(){
  const es = new EventSource('/__livereload');
  es.onmessage = () => location.reload();
  es.onerror   = () => { es.close(); };
})();
</script>
"""

# ── file-hash watcher ────────────────────────────────────────────────────────
_clients = []
_clients_lock = threading.Lock()

def _file_hash(path):
    try:
        with open(path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return None

def _watch(root):
    hashes = {}
    while True:
        time.sleep(0.6)
        for dirpath, _, files in os.walk(root):
            for fname in files:
                if any(fname.endswith(ext) for ext in WATCH_EXTS):
                    path = os.path.join(dirpath, fname)
                    h = _file_hash(path)
                    if path in hashes and hashes[path] != h:
                        print(f'\n  ↻  Change detected: {fname}  →  reloading browser…')
                        with _clients_lock:
                            for q in _clients:
                                q.append(True)
                    hashes[path] = h

# ── SSE + file handler ───────────────────────────────────────────────────────
class LiveHandler(http.server.SimpleHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Suppress noisy per-request logs; only show reloads
        pass

    def do_GET(self):
        if self.path == '/__livereload':
            self._sse()
            return

        # Inject reload script into HTML responses
        if self.path in ('/', '/index.html', ''):
            self._serve_html()
            return

        super().do_GET()

    def _sse(self):
        q = []
        with _clients_lock:
            _clients.append(q)
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try:
            while True:
                if q:
                    q.pop()
                    self.wfile.write(b'data: reload\n\n')
                    self.wfile.flush()
                time.sleep(0.3)
        except Exception:
            pass
        finally:
            with _clients_lock:
                try: _clients.remove(q)
                except ValueError: pass

    def _serve_html(self):
        path = os.path.join(os.getcwd(), 'index.html')
        try:
            with open(path, 'rb') as f:
                content = f.read()
        except FileNotFoundError:
            self.send_error(404)
            return
        # Inject before </body>
        content = content.replace(b'</body>', RELOAD_SCRIPT + b'</body>', 1)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

# ── entry point ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    watcher = threading.Thread(target=_watch, args=(root,), daemon=True)
    watcher.start()

    handler = partial(LiveHandler, directory=root)
    with http.server.ThreadingHTTPServer(('', PORT), handler) as httpd:
        print(f'\n  🚀  Portfolio dev server running')
        print(f'  📂  Serving: {root}')
        print(f'  🌐  Open:    http://localhost:{PORT}')
        print(f'  ♻️   Live reload: ON  (watches .html .css .js)')
        print(f'\n  Ctrl+C to stop\n')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\n  Server stopped.')
            sys.exit(0)
