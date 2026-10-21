#!/usr/bin/env python3
"""Run the existing native, API and dashboard static checks."""
import pathlib, subprocess, sys, time, json
root=pathlib.Path(__file__).resolve().parents[1]
checks=['smoke.py','test_v42.py','test_v43.py','test_v51.py','test_v8_release.py','integration.py','pro.py','test_visual_sync.py','test_v86_contract.py']
results=[]
for name in checks:
    start=time.monotonic()
    try:
        p=subprocess.run([sys.executable,str(root/'tests'/name)],cwd=root,text=True,capture_output=True,timeout=120)
        result={'test':name,'status':'PASS' if p.returncode==0 else 'FAIL','seconds':round(time.monotonic()-start,2),'output':(p.stdout+'\n'+p.stderr)[-3000:]}
    except subprocess.TimeoutExpired:
        result={'test':name,'status':'TIMEOUT','seconds':120}
    results.append(result)
    print(result['status'],name,flush=True)
(root/'verification_results.json').write_text(json.dumps(results,indent=2))
sys.exit(0 if all(r['status']=='PASS' for r in results) else 1)
