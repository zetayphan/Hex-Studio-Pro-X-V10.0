#!/usr/bin/env python3
"""Experiment directory manager for Hex Studio Pro X V10 (standard library only)."""
import argparse, json, pathlib, re, shutil, sys, urllib.request, urllib.error, datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
STORE=ROOT/'experiments'/'records'
SAVE=ROOT/'saved'/'state.json'
def api(url,path,payload=None):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url.rstrip('/')+path,data=data,headers={'Content-Type':'application/json'} if data else {},method='POST' if data is not None else 'GET')
    try:
        with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError(f'API {e.code}: {e.read().decode()[:300]}') from e
def safe(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',name):raise ValueError('Name must contain only letters, numbers, _ or - (1–64 chars)')
    return STORE/name
def read(name):return json.loads((safe(name)/'state.json').read_text())
def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2));tmp.replace(path)
def main():
    p=argparse.ArgumentParser(description='V10 named experiment storage, replay and comparison')
    p.add_argument('--url',default='http://127.0.0.1:8141')
    sub=p.add_subparsers(dest='cmd',required=True)
    for cmd in ('save','restore','show','export'):
        a=sub.add_parser(cmd);a.add_argument('name')
    sub.add_parser('list')
    a=sub.add_parser('compare');a.add_argument('first');a.add_argument('second')
    a=sub.add_parser('transform');a.add_argument('name');a.add_argument('operation',choices=['xor','add','and','or','rotate_left']);a.add_argument('operand');a.add_argument('--start',type=int,default=0);a.add_argument('--count',type=int,default=1)
    a=sub.add_parser('replay');a.add_argument('name')
    args=p.parse_args();STORE.mkdir(parents=True,exist_ok=True)
    if args.cmd=='list':
        for d in sorted(STORE.iterdir()):
            if d.is_dir() and (d/'state.json').exists():print(d.name)
    elif args.cmd=='save':
        folder=safe(args.name)
        if folder.exists():raise ValueError('Experiment already exists; choose another name')
        api(args.url,'/api/save',{})
        data=json.loads(SAVE.read_text())
        write_json(folder/'state.json',data)
        write_json(folder/'manifest.json',{'name':args.name,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'Hex Studio Pro X V10','actions':[]})
        print('Saved',folder)
    elif args.cmd=='restore':
        data=read(args.name)
        # Back up the currently saved snapshot before replacing it.
        if SAVE.exists():shutil.copy2(SAVE,SAVE.with_name('state.before_experiment_restore.json'))
        write_json(SAVE,data)
        result=api(args.url,'/api/load',{})
        print('Restored',args.name,'tick',result.get('tick'))
    elif args.cmd=='show':
        data=read(args.name);print(json.dumps({'name':args.name,'tick':data.get('tick'),'checksum':data.get('checksum'),'cells':len(data.get('cells',[])),'actions':json.loads((safe(args.name)/'manifest.json').read_text()).get('actions',[])},indent=2))
    elif args.cmd=='export':
        print((safe(args.name)/'state.json').resolve())
    elif args.cmd=='compare':
        a,b=read(args.first),read(args.second);x,y=a.get('cells',[]),b.get('cells',[])
        different=sum(v!=w for v,w in zip(x,y))+abs(len(x)-len(y))
        print(json.dumps({'experiments':[args.first,args.second],'cell_counts':[len(x),len(y)],'different_cells':different,'ticks':[a.get('tick'),b.get('tick')],'checksums':[a.get('checksum'),b.get('checksum')]},indent=2))
    elif args.cmd=='transform':
        folder=safe(args.name);manifest_path=folder/'manifest.json'
        if not manifest_path.exists():raise ValueError('Save a named experiment first')
        operand=int(args.operand,0)
        payload={'operation':args.operation,'operand':hex(operand),'start':args.start,'count':args.count}
        result=api(args.url,'/api/transform',payload)
        manifest=json.loads(manifest_path.read_text());manifest['actions'].append(payload);write_json(manifest_path,manifest)
        print('Applied',args.operation,'tick',result.get('tick'))
    elif args.cmd=='replay':
        # Restore baseline, then replay recorded operations. Engine must be paused.
        folder=safe(args.name);manifest=json.loads((folder/'manifest.json').read_text())
        if SAVE.exists():shutil.copy2(SAVE,SAVE.with_name('state.before_experiment_restore.json'))
        api(args.url,'/api/control',{'running':False})
        write_json(SAVE,read(args.name));api(args.url,'/api/load',{})
        api(args.url,'/api/control',{'running':False})
        for action in manifest['actions']:api(args.url,'/api/transform',action)
        print('Replayed',len(manifest['actions']),'transformations')
if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,urllib.error.URLError) as e:print('ERROR:',e,file=sys.stderr);sys.exit(1)
