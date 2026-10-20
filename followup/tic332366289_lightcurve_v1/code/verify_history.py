import common as C
import shutil
p=C.historical(C.PACKET/'tiers_p12_0.json');obj=C.json.loads(p.read_text());shutil.copyfile(p,C.WS/'inputs/inherited_tiers_p12_0.json')
def walk(x,path=''):
    if isinstance(x,dict):
        for k,v in x.items():
            if 'k9' in k.lower(): print(path+'/'+k,C.json.dumps(v)[:8000])
            walk(v,path+'/'+k)
    elif isinstance(x,list):
        for i,v in enumerate(x):walk(v,path+f'/{i}')
walk(obj)
a=C.json.loads((C.WS/'inputs/inherited_stageA.json').read_text());print('Stage A top',a.keys())
print('Chosen',a['chosen_ephemeris']);print('Primary survey',C.json.dumps(a['ephemerides']['survey'] if 'ephemerides' in a else {},indent=1)[:500])
fit=C.json.loads((C.WS/'inputs/inherited_fit.json').read_text());print('FIT',C.json.dumps(fit,indent=1))
# preserve prompt identity too (the prompt was read before its first hash; disclose).
prompt=C.historical(C.Path(r'C:\Users\seanj\Downloads\CLAUDE_TIC332366289_LIGHTCURVE_CHECK_PROMPT.md'))
shutil.copyfile(prompt,C.WS/'inputs/request_prompt.md')
