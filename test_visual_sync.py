#!/usr/bin/env python3
"""Static checks of the dashboard's shared snapshot wiring (not browser-render proof)."""
from pathlib import Path
import re, subprocess, tempfile
html=(Path(__file__).resolve().parents[1]/'web/index.html').read_text()
assert "fetch('/api/state'" in html
assert re.search(r'function render\(s\)',html)
assert 'render(await r.json())' in html
assert 'setInterval(poll,900)' in html
assert 'pollBusy' in html
assert 'document.hidden' in html
assert 'classicCanvas76' in html and 'tabCanvas77' in html and 'tabWebgl77' in html
assert 'body.canvas-mode77' in html and 'body.webgl-mode77' in html
assert 'latest={values:vals.slice()' in html
assert 'tick:s.tick,checksum:s.checksum' in html
assert 'last&&render(last)' in html
assert 'requestAnimationFrame(animateDensity)' in html
scripts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.S|re.I)
assert scripts, 'No inline scripts found'
with tempfile.TemporaryDirectory() as td:
    for i,script in enumerate(scripts):
        path=Path(td)/f'script_{i}.js';path.write_text(script)
        result=subprocess.run(['node','--check',str(path)],capture_output=True,text=True)
        assert result.returncode==0, f'JS script {i}: {result.stderr}'
print(f'PASS: {len(scripts)} inline scripts parse; shared snapshot and render-mode wiring detected')
print('NOTE: Static checks cannot prove pixel-level Canvas/WebGL synchronization')
