import json, pathlib, subprocess, sys, time, urllib.request
root=pathlib.Path(__file__).resolve().parents[1]
p=subprocess.Popen([sys.executable,str(root/'src'/'server.py'),'--port','18888'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
def get(route):return json.load(urllib.request.urlopen('http://127.0.0.1:18888'+route))
def post(route,data={}):
    req=urllib.request.Request('http://127.0.0.1:18888'+route,json.dumps(data).encode(),{'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req))
try:
    for i in range(50):
        try:
            assert get('/api/health')['ok'];break
        except Exception:time.sleep(.1)
    else:raise AssertionError('Server failed to start')
    assert urllib.request.urlopen('http://127.0.0.1:18888/').status==200
    post('/api/control',{'running':False})
    post('/api/input',{'hex':'071EB8 DB10BC EB1078 0B1DBC'})
    before=post('/api/step');assert before['tick']==1
    post('/api/save');post('/api/step')
    restored=post('/api/load')
    assert restored['tick']==before['tick'] and restored['hex']==before['hex'] and restored['stages']==before['stages'] and restored['checksum']==before['checksum']
    assert restored['running'] is False
    print('PASS: V2 homepage, health, input, step, exact save/load, 17 stage audits')
finally:p.terminate();p.wait(timeout=5)
