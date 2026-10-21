"""V5.1 deterministic native-engine regression tests; not reference-PDF validation."""
import ctypes, subprocess, tempfile, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
MAX=32768
class State(ctypes.Structure):
    _fields_=[('cells',ctypes.c_uint32*MAX),('stages',ctypes.c_uint32*17),('stage_changes',ctypes.c_uint32*17),('tick',ctypes.c_uint64),('checksum',ctypes.c_uint32),('flags',ctypes.c_uint32),('dimension',ctypes.c_uint32),('count',ctypes.c_uint32)]
with tempfile.TemporaryDirectory() as d:
    out=pathlib.Path(d)/'engine.so'
    subprocess.run(['cc','-O2','-std=c11','-shared','-fPIC',str(ROOT/'src/engine.c'),'-o',str(out)],check=True)
    lib=ctypes.CDLL(str(out))
    lib.hex_init.argtypes=[ctypes.POINTER(State),ctypes.POINTER(ctypes.c_uint32),ctypes.c_size_t,ctypes.c_uint32]
    lib.hex_step.argtypes=[ctypes.POINTER(State)]
    seed=(ctypes.c_uint32*4)(0x071EB8,0xDB10BC,0xEB1078,0x0B1DBC)
    for n in (8,12,16,24,32):
        a,b=State(),State()
        for state in (a,b):lib.hex_init(ctypes.byref(state),seed,4,n)
        assert a.count==n**3 and all(v<=0xFFFFFF for v in a.cells[:a.count])
        for tick in range(2):
            for state in (a,b):lib.hex_step(ctypes.byref(state))
            assert a.tick==tick+1 and a.checksum==b.checksum
            assert list(a.cells[:a.count])==list(b.cells[:b.count])
            assert all(0<=v<=a.count for v in a.stage_changes)
            assert all(v<=0xFFFFFF for v in a.cells[:a.count])
        print(f'PASS {n}³ / {a.count} cells deterministic, bounded, 24-bit')
print('PASS V5.1 native engine regression tests')
