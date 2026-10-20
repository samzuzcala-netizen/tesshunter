"""Coordinate permitted S/B/C/D work while the fixed A batch completes.

No truth is read. This changes scheduling only, not runner.py or scientific inputs.
Do not run a competing new batch while this dispatcher is active.
"""
from common import *
import csv,time,collections,psutil
from concurrent.futures import ThreadPoolExecutor
from runner import invoke

LIMITS={'S':4,'B':4,'C':2,'D':2}
REQUIREMENTS={'S':[('stageA','decision',{'PASS'},'A')],
 'B':[('stageA','decision',{'PASS'},'A'),('secondary','gate',{'PASS','HOLD'},'S')],
 'C':[('stageB','decision',{'PASS'},'B')], 'D':[('stageC','decision',{'PASS'},'C')]}

def settled(token):
    p=P9/'results/operations'/f'{token}.json'
    if not p.exists():return False
    d=read(p)
    return d.get('status')=='complete' or (len(d.get('attempts',[]))>=2 and d.get('status') in ('error','timeout'))

def active_tokens():
    result=set()
    for p in psutil.process_iter(['cmdline']):
        args=p.info.get('cmdline') or []
        if not any(Path(a).name=='runner.py' for a in args if '\n' not in a):continue
        try:
            if 'stage' not in args:continue
            stage=args[args.index('--stage')+1];key=args[args.index('--key')+1]
            result.add(f'{stage}_{key}')
        except (ValueError,IndexError):continue
    return result

def candidates():
    result=[];a_tokens=[]
    for tic in read(P9/'manifests/final_ids.json'):
        root=P9/'results/blind'/f'tic{tic}';path=root/'survivors.csv'
        if not path.exists():continue
        for r in csv.DictReader(path.open(encoding='utf-8')):
            key=f'tic{tic}_P{float(r["period_days"]):.4f}';a_tokens.append(f'A_{key}')
            for stage,reqs in REQUIREMENTS.items():
                token=f'{stage}_{key}'
                if settled(token):continue
                if not all(settled(f'{prev}_{key}') and (root/folder/f'{key}.json').exists()
                    and read(root/folder/f'{key}.json').get(field) in allowed for folder,field,allowed,prev in reqs):continue
                result.append((stage,token,['stage','--tic',str(tic),'--stage',stage,'--key',key]))
    return result,a_tokens

def main():
    lockpath=P9/'work/dispatcher.json'
    if lockpath.exists():
        previous=read(lockpath)
        if previous.get('status')=='running' and psutil.pid_exists(previous['pid']):raise RuntimeError('Dispatcher already running')
    start=utc();jobs={};events=[]
    write(lockpath,dict(pid=os.getpid(),started_utc=start,status='running',code_sha256=sha(Path(__file__))))
    with ThreadPoolExecutor(max_workers=sum(LIMITS.values())) as executor:
        while True:
            for token,(stage,future) in list(jobs.items()):
                if future.done():
                    result=future.result();events.append(dict(utc=utc(),token=token,status=result['status']))
                    print(token,result['status'],round(result['attempts'][-1]['wall_seconds'],1),flush=True);del jobs[token]
            active=active_tokens()|set(jobs);counts=collections.Counter(t.split('_')[0] for t in active)
            available,a_tokens=candidates()
            for stage,token,cmd in available:
                if token in active or counts[stage]>=LIMITS[stage]:continue
                # S and B share four light-stage workers; C and D each have at most two.
                if stage in ('S','B') and counts['S']+counts['B']>=4:continue
                future=executor.submit(invoke,cmd,token,{'S':900,'B':900,'C':36000,'D':14400}[stage])
                jobs[token]=(stage,future);active.add(token);counts[stage]+=1
                events.append(dict(utc=utc(),token=token,status='dispatched'));print('dispatched',token,flush=True)
            write(P9/'results/dispatch_status.json',dict(utc=utc(),started_utc=start,active=sorted(active),
              A_settled=sum(settled(t) for t in a_tokens),A_total=len(a_tokens),events=events,code_sha256=sha(Path(__file__))))
            if all(settled(t) for t in a_tokens) and not available and not jobs and not active:break
            time.sleep(15)
    write(lockpath,dict(pid=os.getpid(),started_utc=start,finished_utc=utc(),status='complete',code_sha256=sha(Path(__file__))))
    print('All permitted automated stages settled; final manual reviews and locks remain separate.',flush=True)

if __name__=='__main__':main()
