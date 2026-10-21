#!/usr/bin/env python3
"""Non-mutating-source V8.3 native performance benchmark (isolated state instances)."""
import ctypes, json, pathlib, statistics, sys, time, tracemalloc
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import server as s
rows=[]
for dim in (8,12,16,24,32):
    x=s.State(); seeds=(ctypes.c_uint32*4)(0x112233,0x445566,0x778899,0xAABBCC)
    s.lib.hex_init(ctypes.byref(x),seeds,4,dim)
    durations=[]
    for i in range(25):
        t=time.perf_counter(); s.lib.hex_step(ctypes.byref(x));durations.append((time.perf_counter()-t)*1000)
    rows.append({'dimension':dim,'cells':x.count,'samples':len(durations),'step_ms_median':round(statistics.median(durations),4),'step_ms_p95':round(sorted(durations)[int(.95*(len(durations)-1))],4),'final_checksum':f'{x.checksum:06X}'})
# Real API snapshot JSON serialization size/time, from the active Python state.
snap=s.snapshot();start=time.perf_counter();payload=json.dumps(snap);serialize_ms=(time.perf_counter()-start)*1000
report={'kind':'local native benchmark; not a browser FPS or endurance test','native_steps':rows,'snapshot':{'cells':len(snap['values']),'json_bytes':len(payload.encode()),'serialize_ms':round(serialize_ms,4)}}
(ROOT/'V8_3_PERFORMANCE_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
