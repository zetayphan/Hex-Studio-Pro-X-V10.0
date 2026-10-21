#!/usr/bin/env python3
"""V9 real-server endurance probe: readiness is a prerequisite, not a sample."""
import argparse, json, pathlib, statistics, sys, time, urllib.request
p=argparse.ArgumentParser()
p.add_argument('--url',default='http://127.0.0.1:8141')
p.add_argument('--seconds',type=int,default=300)
p.add_argument('--interval',type=float,default=5)
p.add_argument('--wait',type=float,default=20)
p.add_argument('--output',default='diagnostics/endurance_v9.json')
a=p.parse_args()
if a.seconds<1 or a.interval<=0 or a.wait<0:p.error('invalid duration/interval/wait')
base=a.url.rstrip('/')
def request(path):
    with urllib.request.urlopen(base+path,timeout=5) as r:return json.load(r)
deadline=time.monotonic()+a.wait
while True:
    try:
        health=request('/api/health')
        if not health.get('ok'):raise ValueError('health endpoint returned unhealthy')
        break
    except Exception as e:
        if time.monotonic()>=deadline:
            print(f'FAIL: server not ready at {base}: {e}',file=sys.stderr)
            sys.exit(2)
        time.sleep(min(0.5,max(0,deadline-time.monotonic())))
print(f'Ready: {base} ({health.get("version", "unknown")})',flush=True)
rows=[];errors=[];last_tick=None;start=time.monotonic()
while time.monotonic()-start<a.seconds:
    t=time.monotonic()
    try:
        data=request('/api/state');tick=data.get('tick');values=data.get('values')
        if not isinstance(tick,int) or not isinstance(values,list) or not values:raise ValueError('invalid state payload')
        if last_tick is not None and tick<last_tick:errors.append({'at':round(t-start,2),'error':'tick regressed'})
        last_tick=tick
        rows.append({'elapsed_s':round(t-start,2),'latency_ms':round((time.monotonic()-t)*1000,2),'tick':tick,'cells':len(values),'running':data.get('running'),'checksum':data.get('checksum')})
    except Exception as e:errors.append({'at':round(t-start,2),'error':str(e)})
    time.sleep(min(a.interval,max(0,a.seconds-(time.monotonic()-start))))
status='PASS' if rows and not errors and (not any(r['running'] for r in rows) or rows[-1]['tick']>rows[0]['tick']) else 'FAIL'
result={'version':'9.0','status':status,'duration_s':round(time.monotonic()-start,2),'samples':len(rows),'errors':errors,'first_tick':rows[0]['tick'] if rows else None,'last_tick':rows[-1]['tick'] if rows else None,'latency_p50_ms':round(statistics.median(r['latency_ms'] for r in rows),2) if rows else None,'measurements':rows}
out=pathlib.Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2));print(f'{status}: {len(rows)} samples, {len(errors)} errors; {out}');sys.exit(status!='PASS')
