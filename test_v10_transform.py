import json, pathlib, subprocess, sys, time, urllib.request, socket, os
ROOT=pathlib.Path(__file__).resolve().parents[1]
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
proc=subprocess.Popen([sys.executable,'-u',str(ROOT/'src/server.py'),'--port',str(port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
def request(path,body=None):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(f'http://127.0.0.1:{port}{path}',data=data,headers={'Content-Type':'application/json'} if data else {})
    with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)
try:
    for _ in range(80):
        try:health=request('/api/health');break
        except Exception:time.sleep(.1)
    else:raise AssertionError('Server did not become ready')
    assert health['version']=='10.0'
    request('/api/control',{'running':False})
    before=request('/api/state')['values'][0]
    after=request('/api/transform',{'operation':'xor','start':0,'count':1,'operand':'0xFF'})['values'][0]
    assert after==(before^0xFF),(before,after)
    assert request('/api/state')['values'][0]==after
    try:request('/api/transform',{'operation':'xor','start':0,'count':50000,'operand':'0xFF'})
    except urllib.error.HTTPError as error:assert error.code==400
    else:raise AssertionError('Unbounded transform accepted')
    assert request('/api/state')['values'][0]==after
    print('PASS V10 health, native transform, persistence, bounds')
finally:
    proc.terminate()
    try:proc.wait(timeout=3)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
