#!/usr/bin/env python3
"""Optional real-server endurance probe; does not mutate engine state."""
import argparse, json, time, urllib.request, pathlib, statistics, sys
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8141');p.add_argument('--seconds',type=int,default=600);p.add_argument('--interval',type=float,default=2);p.add_argument('--output',default='diagnostics/endurance_v86.json');a=p.parse_args()
if a.seconds<1 or a.interval<=0:p.error('invalid duration/interval')
rows=[]; errors=[];start=time.monotonic();last_tick=None
while time.monotonic()-start<a.seconds:
    t=time.monotonic()
    try:
        with urllib.request.urlopen(a.url.rstrip('/')+'/api/state',timeout=10) as response: data=json.load(response)
        tick=data.get('tick'); values=data.get('values',[])
        if not isinstance(tick,int) or not isinstance(values,list) or not values:raise ValueError('invalid state response')
        if last_tick is not None and tick<last_tick:errors.append({'at':round(t-start,2),'error':'tick regressed; possible reset'})
        last_tick=tick
        rows.append({'elapsed_s':round(t-start,2),'latency_ms':round((time.monotonic()-t)*1000,2),'tick':tick,'cells':len(values),'checksum':data.get('checksum'),'running':data.get('running')})
    except Exception as e:errors.append({'at':round(t-start,2),'error':str(e)})
    time.sleep(min(a.interval,max(0,a.seconds-(time.monotonic()-start))))
result={'version':'8.6','duration_s':round(time.monotonic()-start,2),'samples':len(rows),'errors':errors,'latency_p50_ms':round(statistics.median([r['latency_ms'] for r in rows]),2) if rows else None,'first_tick':rows[0]['tick'] if rows else None,'last_tick':rows[-1]['tick'] if rows else None,'status':'PASS' if rows and not errors else 'FAIL','measurements':rows}
out=pathlib.Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2));print(f"{result['status']}: {len(rows)} samples, {len(errors)} errors; {out}");sys.exit(result['status']!='PASS')
