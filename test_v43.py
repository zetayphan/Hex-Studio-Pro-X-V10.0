"""V4.3 offline regression checks; no browser or Android performance claims."""
from pathlib import Path
import json, subprocess, sys, tempfile, urllib.request, time
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'web/index.html').read_text()
required=['lattice','neighbors','slicecanvas','evolution','heatmap']
for name in required:
    assert f'id="{name}"' in html, f'Missing panel {name}'
    assert f"safeDraw('{name}'" in html, f'Missing isolation for {name}'
assert 'id="panelHealth"' in html
script=html.split('<script>',1)[1].split('</script>',1)[0]
with tempfile.TemporaryDirectory() as d:
    js=Path(d)/'dashboard.js';js.write_text(script)
    if __import__('shutil').which('node'):
        subprocess.run(['node','--check',str(js)],check=True)
print('PASS: all five visualizations isolated; status indicator present; JS syntax checked if Node installed')
# Confirm engine compiles on the current host and regression suite is callable.
subprocess.run([sys.executable,str(ROOT/'tests/test_v42.py')],cwd=ROOT,check=True)
print('PASS: V4.2 native regression suite')
