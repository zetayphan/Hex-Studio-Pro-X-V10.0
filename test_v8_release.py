#!/usr/bin/env python3
"""V8 regression checks. Operational properties, NOT reference-PDF validation."""
import ctypes, importlib.util, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import server as s

def totals(state):
    return tuple(sum((int(v) >> (8*c)) & 255 for v in state.cells[:state.count]) for c in range(3))

def make(dim):
    x=s.State(); a=(ctypes.c_uint32*4)(0x001122,0xCC8877,0xFFAA33,0x6677DD)
    s.lib.hex_init(ctypes.byref(x),a,4,dim)
    return x

def check(dim):
    a=make(dim);b=make(dim);n=dim**3
    assert a.count==n and b.count==n
    for x in (a,b):
        t=totals(x)
        s.lib.hex_separate_conservative(ctypes.byref(x),55)
        assert totals(x)==t, 'conservative separation violated RGB conservation'
        t=totals(x)
        s.lib.hex_unified_dynamics(ctypes.byref(x),48,35)
        assert totals(x)==t, 'bond/transport violated RGB conservation'
        s.lib.hex_separate_transform(ctypes.byref(x),35)
        s.lib.hex_step(ctypes.byref(x))
        assert all(0<=v<=0xffffff for v in x.cells[:x.count])
        assert all(0<=v<=n for v in x.stage_changes)
    assert list(a.cells[:n])==list(b.cells[:n]),'non-deterministic output'
    assert a.checksum==b.checksum
    print(f'PASS {dim}³ ({n:,} cells): conservation, bounds, deterministic execution')

if __name__=='__main__':
    for d in (8,12,16,24,32):check(d)
    snap=s.snapshot()
    assert len(snap['values'])==snap['cell_count']==snap['dimension']**3
    assert len(snap['stages'])==17
    assert snap['checksum']==f'{s.state.checksum:06X}'
    print('PASS API snapshot shape and checksum; note: reference PDF correctness NOT verified')
