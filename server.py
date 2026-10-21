#!/usr/bin/env python3
"""Hex Studio Pro local host. Conceptual stages are documented interpretations."""
import argparse, ctypes, json, pathlib, re, socket, subprocess, threading, time, hashlib, shutil, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROOT=pathlib.Path(__file__).resolve().parents[1]
LIB=ROOT/'build'/'libhexstudio.so'; LIB.parent.mkdir(exist_ok=True)
if not LIB.exists() or LIB.stat().st_mtime < (ROOT/'src'/'engine.c').stat().st_mtime:
    subprocess.run(['cc','-O2','-std=c11','-shared','-fPIC',str(ROOT/'src'/'engine.c'),'-o',str(LIB)],check=True)
class State(ctypes.Structure):
    _fields_=[('cells',ctypes.c_uint32*32768),('stages',ctypes.c_uint32*17),('stage_changes',ctypes.c_uint32*17),('tick',ctypes.c_uint64),('checksum',ctypes.c_uint32),('flags',ctypes.c_uint32),('dimension',ctypes.c_uint32),('count',ctypes.c_uint32)]
lib=ctypes.CDLL(str(LIB))
lib.hex_init.argtypes=[ctypes.POINTER(State),ctypes.POINTER(ctypes.c_uint32),ctypes.c_size_t,ctypes.c_uint32]
lib.hex_step.argtypes=[ctypes.POINTER(State)]
lib.hex_enable_extension.argtypes=[ctypes.POINTER(State),ctypes.c_int]
lib.hex_bond_step.argtypes=[ctypes.POINTER(State),ctypes.c_uint32,ctypes.c_uint32]
lib.hex_bond_step.restype=ctypes.c_uint32
lib.hex_separate_conservative.argtypes=[ctypes.POINTER(State),ctypes.c_uint32]
lib.hex_separate_conservative.restype=ctypes.c_uint32
lib.hex_separate_transform.argtypes=[ctypes.POINTER(State),ctypes.c_uint32]
lib.hex_separate_transform.restype=ctypes.c_uint32
separation_changes={'conservative':0,'transformative':0}
unified_changes=0
unified_bond_rate=48
unified_flow_rate=35
separation_rate=55
lib.hex_unified_dynamics.argtypes=[ctypes.POINTER(State),ctypes.c_uint32,ctypes.c_uint32]
lib.hex_unified_dynamics.restype=ctypes.c_uint32
separation_amplitude=35
lib.hex_set_cell.argtypes=[ctypes.POINTER(State),ctypes.c_uint32,ctypes.c_uint32]
lib.hex_set_cell.restype=ctypes.c_int
NAMES=['Late Model','File Layout','Location Spec','Underlying Principle Extension','Derive Structure','Derive Operation','Derive Layout','Integrate Structure','Integrate Operation','Integrate Layout','Run Locations Through Late Model','Run Principle Through System','Run File Through System','Output Hexadecimal','Input Hexadecimal','Repeat Input Output','Save File']
state=State(); lock=threading.RLock(); running=True; interval=.4; history=[]; last_error=None; file_info=None; steps_total=0; errors_total=0; started_at=time.monotonic()
bond_enabled=False; bond_strength=48; bond_threshold=25; bond_changes=0
pair_bonds={}
# Persistent weighted graph, separate from the native 6-neighbor bonding step.
# Edges retain their strength across ticks and are applied to native RGB cells.
persistent_bonds={}
network_enabled=False
network_changes=0
MAX_NETWORK_BONDS=98304  # Maximum nearest-neighbor edges for a 32^3 open lattice

def bond_capacity():
    d=int(state.dimension)
    return min(MAX_NETWORK_BONDS,3*d*d*(d-1))
# Bounded autonomous six-neighbor discovery; avoids O(N^2) searches.
auto_enabled=False
auto_similarity=.76
auto_scan_budget=1200
auto_added=0
auto_removed=0
auto_cursor=0

def auto_discover():
    global auto_added,auto_removed,auto_cursor
    auto_added=auto_removed=0
    if not auto_enabled or not network_enabled:return
    n=int(state.count);d=int(state.dimension)
    if n<2:return
    # Visit successive lattice cells in a deterministic round-robin order.
    # Consider only +X,+Y,+Z edges; each undirected edge is visited once.
    budget=min(n,max(1,auto_scan_budget))
    for offset in range(budget):
        i=(auto_cursor+offset)%n
        x=i%d;y=(i//d)%d;z=i//(d*d)
        candidates=[]
        if x+1<d:candidates.append(i+1)
        if y+1<d:candidates.append(i+d)
        if z+1<d:candidates.append(i+d*d)
        for j in candidates:
            edge=(i,j)
            sim=bond_similarity(int(state.cells[i]),int(state.cells[j]))
            if edge in persistent_bonds:
                # Network evolution handles normal weakening; allow early break on divergence.
                if sim<max(0,auto_similarity-.42):
                    del persistent_bonds[edge];auto_removed+=1
            elif sim>=auto_similarity and len(persistent_bonds)<bond_capacity():
                add_persistent_bond(i,j,max(10,min(90,round(sim*75))))
                auto_added+=1
    auto_cursor=(auto_cursor+budget)%n


def bond_similarity(a,b):
    return 1-sum(abs(((a>>shift)&255)-((b>>shift)&255)) for shift in (0,8,16))/765

def network_step():
    global network_changes
    if not network_enabled or not persistent_bonds:
        network_changes=0;return
    original={i:int(state.cells[i]) for edge in persistent_bonds for i in edge}
    totals={};weights={};expired=[]
    for edge,record in list(persistent_bonds.items()):
        a,b=edge;similarity=bond_similarity(original[a],original[b])
        # Existing bonds survive, strengthen with similarity and weaken with divergence.
        record['strength']=max(0,min(100,record['strength']+(2 if similarity>=.65 else -3)))
        record['age']+=1
        if record['strength']==0:expired.append(edge);continue
        w=record['strength']/100
        for i,j in ((a,b),(b,a)):
            totals[i]=totals.get(i,0)+w*original[j];weights[i]=weights.get(i,0)+w
    for edge in expired:del persistent_bonds[edge]
    changed=0
    for i,weight in weights.items():
        own=original[i];neighbors=[]
        for shift in (0,8,16):
            # Calculate channel-specific weighted mean, never mix packed integers.
            weighted=sum((rec['strength']/100)*((original[b if a==i else a]>>shift)&255) for (a,b),rec in persistent_bonds.items() if i in (a,b))
            mean=weighted/weight
            val=max(0,min(255,round(.88*((own>>shift)&255)+.12*mean)))
            neighbors.append(val)
        out=(neighbors[2]<<16)|(neighbors[1]<<8)|neighbors[0]
        if out!=own:lib.hex_set_cell(ctypes.byref(state),i,out);changed+=1
    network_changes=changed

def add_persistent_bond(a,b,strength=50):
    if not (0<=a<state.count and 0<=b<state.count and a!=b):raise ValueError('Invalid bond endpoints')
    key=tuple(sorted((a,b)))
    if key not in persistent_bonds and len(persistent_bonds)>=bond_capacity():raise ValueError('Network bond limit reached')
    persistent_bonds[key]={'strength':max(1,min(100,int(strength))),'age':0}

SAVE=ROOT/'saved'/'state.json'
def initialize(values,dimension=None):
    global history
    pair_bonds.clear();persistent_bonds.clear()
    a=(ctypes.c_uint32*len(values))(*values)
    lib.hex_init(ctypes.byref(state),a,len(values),dimension or (int(state.dimension) if state.dimension else 8));history=[]
def step():
    global steps_total,bond_changes,unified_changes
    lib.hex_step(ctypes.byref(state))
    # V7 C: coordinate A and B after the existing 17-stage pipeline.
    # A is exactly conservative; B is intentionally nonconservative.
    separation_changes['conservative']=int(lib.hex_separate_conservative(ctypes.byref(state),separation_rate))
    separation_changes['transformative']=int(lib.hex_separate_transform(ctypes.byref(state),separation_amplitude))
    unified_changes=int(lib.hex_unified_dynamics(ctypes.byref(state),unified_bond_rate,unified_flow_rate))
    bond_changes=0
    steps_total+=1
    history.append({'tick':int(state.tick),'value':int(state.checksum),'mean':sum(state.cells[:state.count])//state.count})
    if len(history)>500:del history[:-500]
def snapshot():
    return {'version':'10.0','tick':int(state.tick),'state_version':int(state.tick),'checksum':f'{state.checksum:06X}', 'hex':[f'{v:06X}' for v in state.cells[:state.count]], 'values':list(state.cells[:state.count]),'dimension':int(state.dimension),'cell_count':int(state.count),'cycle':{'feedback':True,'processing':'17 stages → conservative separation → transformative separation → local bonding + nodal transport → feedback'},'unified_dynamics':{'bonding':'local symmetric RGB flux','transport':'conservative directed nodal flux','bond_rate':unified_bond_rate,'flow_rate':unified_flow_rate,'changed_cells':unified_changes,'fluid_model':'discrete transport (not Navier-Stokes)','webgl_driver':'native RGB spatial gradients'},'separation':{'mode':'A+B coordinated by C','conservative_changed':separation_changes['conservative'],'transformative_changed':separation_changes['transformative'],'rate':separation_rate,'amplitude':separation_amplitude,'channel_conservation':'exact during A'},'persistent_network':{'autonomous':{'enabled':auto_enabled,'similarity':auto_similarity,'scan_budget':auto_scan_budget,'added':auto_added,'removed':auto_removed},'enabled':network_enabled,'bond_count':len(persistent_bonds),'possible_neighbor_edges':3*int(state.dimension)**2*(int(state.dimension)-1),'bond_capacity':bond_capacity(),'scanned_cells_per_tick':min(int(state.count),max(1,auto_scan_budget)),'changed_cells':network_changes,'bonds':[{'a':a,'b':b,**rec} for (a,b),rec in list(persistent_bonds.items())[:min(2048,len(persistent_bonds))]]},'bonding':{'enabled':bond_enabled,'strength':bond_strength,'threshold':bond_threshold,'changed_cells':bond_changes,'pair_count':len(pair_bonds),'pairs':[list(k) for k in list(pair_bonds)[:100] ]}, 'stages':[{'name':n,'checksum':f'{state.stages[i]:06X}','status':'executed' if state.tick else 'ready','changed_cells':int(state.stage_changes[i]),'kind':'transformation' if i in (0,2,3,4,7,10,11,13,14,15) else 'structural/management'} for i,n in enumerate(NAMES)],'history':list(history[-100:]),'file':file_info,'running':running,'interval_ms':round(interval*1000),'extension':bool(state.flags&1),'error':last_error,'diagnostics':{'steps_total':steps_total,'errors_total':errors_total,'uptime_seconds':round(time.monotonic()-started_at,1),'engine':f'native C / {state.count} x 24-bit cells','visualization':f'native {state.dimension}x{state.dimension}x{state.dimension} lattice','stage_count':17,'stage_changes_verified_range':int(state.count),'native_architecture':__import__('platform').machine(),'independent_3d_simulation':True}}
def restore(obj):
    global running,interval,history,bond_enabled,bond_strength,bond_threshold,bond_changes,network_enabled,network_changes,auto_enabled,auto_similarity,auto_scan_budget,auto_cursor
    if obj.get('format') not in ('hex-studio-v4-state-1','hex-studio-v3-state-1','hex-studio-v2-state-1'):raise ValueError('Invalid save format')
    vals=obj['cells']; stages=obj['stages']; tick=obj['tick']
    if len(vals)==24 and obj.get('format')=='hex-studio-v2-state-1':
        vals=[(vals[i%24] ^ (i*0x9E3779B9)) & 0xFFFFFF for i in range(512)]
    if len(vals) not in (512,1728,4096,13824,32768) or len(stages)!=17 or any(type(x)!=int or x<0 or x>0xffffff for x in vals+stages) or type(tick)!=int or tick<0:raise ValueError('Invalid saved state')
    state.dimension=round(len(vals)**(1/3));state.count=len(vals)
    for i,v in enumerate(vals):state.cells[i]=v
    changes=obj.get('stage_changes',[0]*17)
    if not isinstance(changes,list) or len(changes)!=17 or any(type(v)!=int or v<0 or v>len(vals) for v in changes):raise ValueError('Invalid stage change counts')
    for i,v in enumerate(changes):state.stage_changes[i]=v
    for i,v in enumerate(stages):state.stages[i]=v
    state.tick=tick;state.checksum=int(obj['checksum']);state.flags=int(obj['flags'])&1
    if not 0<=int(state.checksum)<=0xffffff:raise ValueError('Invalid checksum')
    interval=max(.05,min(5,float(obj.get('interval',.25))))
    loaded_history=obj.get('history',[])
    if not isinstance(loaded_history,list):raise ValueError('Invalid history')
    history=loaded_history[-500:];running=bool(obj.get('running',False))
    persistent_bonds.clear();net={} # V7 no persistent bond network
    if isinstance(net,dict):
        network_enabled=False
        edges=net.get('bonds',[])
        if not isinstance(edges,list) or len(edges)>bond_capacity():raise ValueError('Invalid persistent network')
        for rec in edges:
            a=int(rec['a']);b=int(rec['b']);add_persistent_bond(a,b,rec['strength'])
            persistent_bonds[tuple(sorted((a,b)))]['age']=max(0,int(rec.get('age',0)))
    autonomous=net.get('autonomous',{}) if isinstance(net,dict) else {}
    if isinstance(autonomous,dict):
        auto_enabled=False
        auto_similarity=max(0,min(1,float(autonomous.get('similarity',.76))))
        auto_scan_budget=max(1,min(32768,int(autonomous.get('scan_budget',1200))))
    auto_cursor=0
    network_changes=0
    globals()['separation_rate']=max(0,min(100,int(obj.get('separation',{}).get('rate',55))))
    globals()['separation_amplitude']=max(0,min(100,int(obj.get('separation',{}).get('amplitude',35))))
    global unified_bond_rate,unified_flow_rate
    dyn=obj.get('unified_dynamics',{})
    unified_bond_rate=max(0,min(100,int(dyn.get('bond_rate',48))))
    unified_flow_rate=max(0,min(100,int(dyn.get('flow_rate',35))))
    bond=obj.get('bonding',{});bond_enabled=False;bond_strength=max(0,min(100,int(bond.get('strength',35))));bond_threshold=max(0,min(100,int(bond.get('threshold',45))));bond_changes=0
initialize([0x071EB8,0xDB10BC,0xEB1078,0x0B1DBC])
def worker():
    global last_error,errors_total,running
    while True:
        with lock:
            if running:
                try:step();last_error=None
                except Exception as e:last_error=str(e);errors_total+=1;running=False
            delay=interval
        time.sleep(delay)
threading.Thread(target=worker,daemon=True).start()
EXPERIMENTS=ROOT/'experiments'/'records'
def experiment_folder(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',name):raise ValueError('Invalid experiment name')
    return EXPERIMENTS/name
def experiment_data(name):
    folder=experiment_folder(name)
    return json.loads((folder/'state.json').read_text())
def experiment_manifest(name):
    return json.loads((experiment_folder(name)/'manifest.json').read_text())
def write_atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2));temp.replace(path)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):print('[HTTP]',fmt%args,flush=True)
    def respond(self,code,data):
        raw=json.dumps(data).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path in ('/api/state','/api/health'):
            with lock:self.respond(200,snapshot() if self.path=='/api/state' else {'ok':True,'version':'10.0','tick':int(state.tick)})
            return
        if self.path=='/api/experiments':
            EXPERIMENTS.mkdir(parents=True,exist_ok=True)
            records=[]
            for folder in sorted(EXPERIMENTS.iterdir()):
                if folder.is_dir() and (folder/'state.json').is_file():
                    try:
                        manifest=json.loads((folder/'manifest.json').read_text())
                        data=json.loads((folder/'state.json').read_text())
                        records.append({'name':folder.name,'created':manifest.get('created_utc',''),'tick':data.get('tick'),'cells':len(data.get('cells',[])),'actions':len(manifest.get('actions',[]))})
                    except (ValueError,OSError):continue
            self.respond(200,{'experiments':records});return
        if self.path in ('/','/index.html'):
            raw=(ROOT/'web'/'index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        self.respond(404,{'error':'Unknown route','dashboard':'/'})
    def do_POST(self):
        global separation_rate,separation_amplitude,running,interval,bond_enabled,bond_strength,bond_threshold,bond_changes,network_enabled,network_changes,auto_enabled,auto_similarity,auto_scan_budget
        try:
            n=int(self.headers.get('Content-Length','0'))
            if n<0 or n>2200000:raise ValueError('Invalid request size')
            if self.headers.get('Origin') and not re.fullmatch(r'https?://(localhost|127\.0\.0\.1)(:\d+)?',self.headers['Origin']):raise ValueError('Cross-origin requests forbidden')
            obj=json.loads(self.rfile.read(n) or b'{}')
            if not isinstance(obj,dict):raise ValueError('Expected JSON object')
            with lock:
                if self.path=='/api/experiments/save':
                    name=obj.get('name');folder=experiment_folder(name)
                    if folder.exists():raise ValueError('Experiment name already exists')
                    if not SAVE.exists():raise ValueError('Save the current engine state before creating an experiment')
                    data=json.loads(SAVE.read_text())
                    write_atomic(folder/'state.json',data)
                    write_atomic(folder/'manifest.json',{'name':name,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'actions':[]})
                    self.respond(200,{'saved':name});return
                elif self.path=='/api/experiments/restore':
                    if running:raise ValueError('Pause engine before restoring an experiment')
                    data=experiment_data(obj.get('name'))
                    if SAVE.exists():shutil.copy2(SAVE,SAVE.with_name('state.before_experiment_restore.json'))
                    write_atomic(SAVE,data);restore(data)
                    self.respond(200,snapshot());return
                elif self.path=='/api/experiments/compare':
                    a=experiment_data(obj.get('first'));b=experiment_data(obj.get('second'))
                    x=a.get('cells',[]);y=b.get('cells',[])
                    diff=sum(v!=w for v,w in zip(x,y))+abs(len(x)-len(y))
                    self.respond(200,{'different_cells':diff,'cell_counts':[len(x),len(y)],'ticks':[a.get('tick'),b.get('tick')]});return
                elif self.path=='/api/experiments/details':
                    name=obj.get('name');self.respond(200,{'name':name,'manifest':experiment_manifest(name),'state':{'tick':experiment_data(name).get('tick'),'cells':len(experiment_data(name).get('cells',[]))}});return
                elif self.path=='/api/experiments/record':
                    name=obj.get('name');action=obj.get('action');manifest=experiment_manifest(name)
                    if not isinstance(action,dict) or action.get('operation') not in ('xor','add','and','or','rotate_left'):raise ValueError('Invalid transform record')
                    manifest.setdefault('actions',[]).append({k:action[k] for k in ('operation','operand','start','count')})
                    write_atomic(experiment_folder(name)/'manifest.json',manifest)
                    self.respond(200,{'recorded':len(manifest['actions'])});return
                elif self.path=='/api/file':
                    global file_info
                    raw=bytes.fromhex(obj.get('bytes',''))
                    if not 1<=len(raw)<=1048576:raise ValueError('Upload 1 to 1048576 bytes')
                    vals=[int.from_bytes(raw[i:i+3].ljust(3,b'\0'),'big') for i in range(0,min(len(raw),1536),3)]
                    initialize(vals)
                    file_info={'name':str(obj.get('name','uploaded.bin'))[:128],'size':len(raw)}
                    running=True
                elif self.path=='/api/control':
                    if 'running' in obj:running=bool(obj['running'])
                    if 'interval_ms' in obj:interval=max(.05,min(5,float(obj['interval_ms'])/1000))
                    if 'extension' in obj:lib.hex_enable_extension(ctypes.byref(state),int(bool(obj['extension'])))
                elif self.path=='/api/separation':
                    if 'rate' in obj:separation_rate=max(0,min(100,int(obj['rate'])))
                    if 'amplitude' in obj:separation_amplitude=max(0,min(100,int(obj['amplitude'])))
                elif self.path=='/api/bonding':
                    if 'enabled' in obj:bond_enabled=bool(obj['enabled'])
                    if 'strength' in obj:bond_strength=max(0,min(100,int(obj['strength'])))
                    if 'threshold' in obj:bond_threshold=max(0,min(100,int(obj['threshold'])))
                    if obj.get('apply_now'):
                        bond_changes=int(lib.hex_bond_step(ctypes.byref(state),bond_strength,bond_threshold))
                        history.append({'tick':int(state.tick),'value':int(state.checksum),'mean':sum(state.cells[:state.count])//state.count})
                        if len(history)>500:del history[:-500]
                elif self.path=='/api/network':
                    action=obj.get('action','add')
                    if action=='enable':network_enabled=True
                    elif action=='auto':
                        if 'enabled' in obj:auto_enabled=bool(obj['enabled'])
                        if 'similarity' in obj:auto_similarity=max(0,min(1,float(obj['similarity'])))
                        if 'scan_budget' in obj:auto_scan_budget=max(1,min(32768,int(obj['scan_budget'])))
                    elif action=='clear':persistent_bonds.clear();network_changes=0
                    elif action in ('add','remove'):
                        a=int(obj.get('a',-1));b=int(obj.get('b',-1))
                        if not (0<=a<state.count and 0<=b<state.count and a!=b):raise ValueError('Invalid cell indices')
                        if action=='add':add_persistent_bond(a,b,obj.get('strength',50))
                        else:persistent_bonds.pop(tuple(sorted((a,b))),None)
                    else:raise ValueError('Unknown network action')
                elif self.path=='/api/pair_bond':
                    a=int(obj.get('a',-1));b=int(obj.get('b',-1))
                    if not (0<=a<state.count and 0<=b<state.count and a!=b):raise ValueError('Select two different valid native cells')
                    key=tuple(sorted((a,b)))
                    action=obj.get('action','bond')
                    if action=='bond':
                        if key in pair_bonds:raise ValueError('Pair already bonded; break it before rebonding')
                        strength=max(0,min(100,int(obj.get('strength',50))))
                        old_a=int(state.cells[a]);old_b=int(state.cells[b]);new=[]
                        for source,target in ((old_a,old_b),(old_b,old_a)):
                            value=0
                            for shift in (0,8,16):
                                c=(source>>shift)&255;d=(target>>shift)&255
                                value|=(round((c*(100-strength)+d*strength)/100)&255)<<shift
                            new.append(value)
                        lib.hex_set_cell(ctypes.byref(state),a,new[0]);lib.hex_set_cell(ctypes.byref(state),b,new[1])
                        pair_bonds[key]=(old_a,old_b,new[0],new[1])
                    elif action=='break':
                        if key not in pair_bonds:raise ValueError('No stored bond for this pair')
                        old_a,old_b,applied_a,applied_b=pair_bonds[key]
                        # Only restore if the values have not changed since bonding.
                        if int(state.cells[a])!=applied_a or int(state.cells[b])!=applied_b:
                            raise ValueError('Cells changed since bonding; cannot safely restore previous values')
                        lib.hex_set_cell(ctypes.byref(state),a,old_a);lib.hex_set_cell(ctypes.byref(state),b,old_b)
                        del pair_bonds[key]
                    else:raise ValueError('Action must be bond or break')
                    history.append({'tick':int(state.tick),'value':int(state.checksum),'mean':sum(state.cells[:state.count])//state.count})
                    if len(history)>500:del history[:-500]
                elif self.path=='/api/transform':
                    # Explicit, bounded, deterministic native cell transforms.
                    # Validate every argument before touching the C state.
                    if running:raise ValueError('Pause engine before applying transformations')
                    op=obj.get('operation')
                    if op not in ('xor','add','and','or','rotate_left'):raise ValueError('Unsupported transform operation')
                    start=int(obj.get('start',0));count=int(obj.get('count',1));operand=int(str(obj.get('operand','0')),0)
                    if not (0<=start<state.count and 1<=count<=4096 and start+count<=state.count):raise ValueError('Invalid cell range')
                    if not (0<=operand<=0xFFFFFF):raise ValueError('Operand must fit in 24 bits')
                    original=[int(state.cells[i]) for i in range(start,start+count)]
                    def transform(value):
                        if op=='xor':return value^operand
                        if op=='add':return (value+operand)&0xFFFFFF
                        if op=='and':return value&operand
                        if op=='or':return value|operand
                        n=operand%24
                        return ((value<<n)|(value>>(24-n if n else 24)))&0xFFFFFF
                    updated=[transform(v) for v in original]
                    for offset,value in enumerate(updated):
                        if not lib.hex_set_cell(ctypes.byref(state),start+offset,value):raise RuntimeError('Native cell write failed')
                    history.append({'tick':int(state.tick),'value':int(state.checksum),'mean':sum(state.cells[:state.count])//state.count})
                    if len(history)>500:del history[:-500]
                elif self.path=='/api/cell':
                    index=int(obj['index']);value=obj['hex']
                    if not isinstance(value,str) or not re.fullmatch(r'(?:0[xX])?[0-9a-fA-F]{1,6}',value):raise ValueError('Cell value must be 1–6 hexadecimal digits')
                    if not lib.hex_set_cell(ctypes.byref(state),index,int(value.removeprefix('0x').removeprefix('0X'),16)):raise ValueError('Invalid cell index or value')
                    history.append({'tick':int(state.tick),'value':int(state.checksum),'mean':sum(state.cells[:state.count])//state.count})
                    if len(history)>500:del history[:-500]
                elif self.path=='/api/input':
                    source=obj.get('hex','')
                    if not isinstance(source,str) or not re.fullmatch(r'[\s,0-9a-fA-FxX]+',source):raise ValueError('Use hexadecimal blocks separated by spaces or commas')
                    tokens=source.replace(',',' ').split()
                    if not 1<=len(tokens)<=10000 or any(not re.fullmatch(r'(?:0[xX])?[0-9a-fA-F]{1,6}',t) for t in tokens):raise ValueError('Provide 1–10000 hex blocks, 1–6 digits each')
                    initialize([int(t.removeprefix('0x').removeprefix('0X'),16) for t in tokens])
                elif self.path=='/api/dimension':
                    dim=int(obj.get('dimension',8))
                    if dim not in (8,12,16,24,32):raise ValueError('Dimension must be 8, 12, 16, 24, or 32')
                    running=False;initialize([0x071EB8,0xDB10BC,0xEB1078,0x0B1DBC],dim)
                elif self.path=='/api/reset':
                    running=False;initialize([0x071EB8,0xDB10BC,0xEB1078,0x0B1DBC])
                elif self.path=='/api/step':step()
                elif self.path=='/api/save':
                    SAVE.parent.mkdir(exist_ok=True)
                    data={'format':'hex-studio-v4-state-1','cells':list(state.cells[:state.count]),'stages':list(state.stages),'stage_changes':list(state.stage_changes),'tick':int(state.tick),'checksum':int(state.checksum),'flags':int(state.flags),'interval':interval,'running':running,'history':history,'persistent_network':{'autonomous':{'enabled':auto_enabled,'similarity':auto_similarity,'scan_budget':auto_scan_budget},'enabled':network_enabled,'bonds':[]},'bonding':{'enabled':False,'strength':0,'threshold':0},'separation':{'rate':separation_rate,'amplitude':separation_amplitude},'unified_dynamics':{'bond_rate':unified_bond_rate,'flow_rate':unified_flow_rate}}
                    temp=SAVE.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2));temp.replace(SAVE)
                    self.respond(200,{'saved':str(SAVE),'tick':int(state.tick)});return
                elif self.path=='/api/load':restore(json.loads(SAVE.read_text()))
                else:self.respond(404,{'error':'Unknown endpoint'});return
                self.respond(200,snapshot())
        except (ValueError,TypeError,KeyError,FileNotFoundError,json.JSONDecodeError) as e:self.respond(400,{'error':str(e)})
        except Exception as e:self.respond(500,{'error':str(e)})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8097);args=p.parse_args()
    server=None
    for port in [args.port]:
        try:server=ThreadingHTTPServer(('127.0.0.1',port),Handler);break
        except OSError:continue
    if server is None:raise SystemExit(f'Cannot bind to 127.0.0.1:{args.port}; stop the old server or set HEX_STUDIO_PORT to another port')
    print(f'Hex Studio Pro: http://127.0.0.1:{server.server_port}/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
