import json, pathlib, subprocess, sys, time, urllib.request, urllib.error
root=pathlib.Path(__file__).resolve().parents[1]
p=subprocess.Popen([sys.executable,str(root/'src/server.py'),'--port','18917'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
def request(path,body=None):
    req=urllib.request.Request('http://127.0.0.1:18917'+path, None if body is None else json.dumps(body).encode(), {} if body is None else {'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=3))
try:
    for i in range(50):
        try:request('/api/health');break
        except Exception:time.sleep(.1)
    request('/api/control',{'running':False});request('/api/reset',{});a=request('/api/state');assert a['tick']==0 and len(a['stages'])==17 and len(a['values'])==a['cell_count']==512
    assert a['diagnostics']['engine']=='native C / 512 x 24-bit cells'
    request('/api/control',{'running':True,'interval_ms':50});time.sleep(.65)
    b=request('/api/state');assert b['tick']>=2
    request('/api/control',{'running':False});request('/api/reset',{})
    c=request('/api/state');assert c['tick']==0 and not c['running']
    request('/api/input',{'hex':'AABBCC DDEEFF'});d=request('/api/step',{});assert d['tick']==1
    request('/api/save',{});request('/api/step',{});assert request('/api/load',{})['hex']==d['hex']
    try:request('/api/input',{'hex':'INVALID'});raise AssertionError('accepted invalid hex')
    except urllib.error.HTTPError as e:assert e.code==400
    print('PASS Pro: 17 stages, continuous processing, reset, diagnostics, validation, persistence')
finally:p.terminate();p.wait(timeout=5)
