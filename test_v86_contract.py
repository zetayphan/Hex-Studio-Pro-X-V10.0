#!/usr/bin/env python3
"""Static contract checks: deliberately not a substitute for live rendering."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
server=(root/'src/server.py').read_text();html=(root/'web/index.html').read_text()
assert "'/api/state'" in server and 'def snapshot()' in server
assert 'function render(' in html and "fetch('/api/state'" in html
assert 'webgl' in html.lower() and 'canvas' in html.lower()
assert 'v84-monitor-script' in html and 'v85' in html.lower()
assert 'hidden' in html.lower()
print('PASS: V8.6 API/visualization/hidden instrumentation static contracts')
