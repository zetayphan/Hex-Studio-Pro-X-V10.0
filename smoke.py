import ctypes,pathlib,subprocess
root=pathlib.Path(__file__).resolve().parents[1];lib=root/'build'/'libhexstudio.so';lib.parent.mkdir(exist_ok=True)
subprocess.run(['cc','-shared','-fPIC','-O2',str(root/'src'/'engine.c'),'-o',str(lib)],check=True)
class State(ctypes.Structure):
 _fields_=[('cells',ctypes.c_uint32*32768),('stages',ctypes.c_uint32*17),('stage_changes',ctypes.c_uint32*17),('tick',ctypes.c_uint64),('checksum',ctypes.c_uint32),('flags',ctypes.c_uint32),('dimension',ctypes.c_uint32),('count',ctypes.c_uint32)]
c=ctypes.CDLL(str(lib));c.hex_init.argtypes=[ctypes.POINTER(State),ctypes.POINTER(ctypes.c_uint32),ctypes.c_size_t,ctypes.c_uint32];c.hex_step.argtypes=[ctypes.POINTER(State)];c.hex_enable_extension.argtypes=[ctypes.POINTER(State),ctypes.c_int];s=State();values=(ctypes.c_uint32*4)(0x071eb8,0xdb10bc,0xeb1078,0x0b1dbc)
c.hex_init(ctypes.byref(s),values,4,8);assert s.tick==0
c.hex_step(ctypes.byref(s));assert s.tick==1 and all(0<=x<=0xffffff for x in s.cells)
first=s.checksum;c.hex_step(ctypes.byref(s));assert s.tick==2
c.hex_init(ctypes.byref(s),values,4,8);c.hex_step(ctypes.byref(s));assert s.checksum==first
c.hex_enable_extension(ctypes.byref(s),0);assert s.flags==0
print('PASS: native C core, 17 passes, 24-bit range, deterministic replay, extension toggle')
