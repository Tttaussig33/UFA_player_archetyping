"""Serve the completed app locally; open the browser without exposing it publicly."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser

root=Path(__file__).resolve().parents[1]
handler=partial(SimpleHTTPRequestHandler,directory=str(root/'dist'))
server=None
for port in range(4173,4194):
    try:
        server=ThreadingHTTPServer(('127.0.0.1',port),handler)
        break
    except OSError:
        continue
if server is None:raise SystemExit('No available preview port from 4173 to 4193.')
url=f'http://127.0.0.1:{server.server_port}'
print(f'UFA player archetyping: {url}\nKeep this window open. Press Control-C to stop.',flush=True)
webbrowser.open(url)
try:server.serve_forever()
except KeyboardInterrupt:print('\nPreview stopped.')
finally:server.server_close()
