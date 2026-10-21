#!/usr/bin/env python3
"""Native engine regression tests; independent of the dashboard."""
import ctypes, pathlib, subprocess, tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
class State(ctypes.Structure):
    _fields_=[('cells',ctypes.c_uint32*32768),('stages',ctypes.c_uint32*17),('stage_changes',ctypes.c_uint32*17),('tick',ctypes.c_uint64),('checksum',ctypes.c_uint32),('flags',ctypes.c_uint32),('dimension',ctypes.c_uint32),('count',ctypes.c_uint32)]
def run():
    with tempfile.TemporaryDirectory() as d:
        libpath=pathlib.Path(d)/'engine.so'
        subprocess.run(['cc','-O2','-std=c11','-shared','-fPIC',str(ROOT/'src/engine.c'),'-o',str(libpath)],check=True)
        lib=ctypes.CDLL(str(libpath));lib.hex_init.argtypes=[ctypes.POINTER(State),ctypes.POINTER(ctypes.c_uint32),ctypes.c_size_t,ctypes.c_uint32];lib.hex_step.argtypes=[ctypes.POINTER(State)]
        seeds=(ctypes.c_uint32*4)(0x071EB8,0xDB10BC,0xEB1078,0x0B1DBC)
        for dim in (8,12,16,24,32):
            a,b=State(),State()
            for st in (a,b):lib.hex_init(ctypes.byref(st),seeds,4,dim)
            assert a.count==dim**3
            assert list(a.cells[:a.count])==list(b.cells[:b.count])
            for st in (a,b):lib.hex_step(ctypes.byref(st))
            assert a.tick==b.tick==1
            assert list(a.cells[:a.count])==list(b.cells[:b.count])
            assert a.checksum==b.checksum
            assert all(0<=x<=a.count for x in a.stage_changes)
            assert a.stage_changes[0]>0
            assert a.stage_changes[1]==0
            assert a.stage_changes[16]==0
            print(f'PASS {dim}³: {a.count} cells, 17 stage counts in bounds, deterministic')
if __name__=='__main__':run()
