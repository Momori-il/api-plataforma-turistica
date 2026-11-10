"""Twenty bounded new reservations measured by Locust, using final statistics on shutdown."""
import argparse
import json
import os
import subprocess
from uuid import uuid4
from scripts.macro4_support import ROOT,STATE,state,helper,evidence

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');args=parser.parse_args()
    if not args.real:parser.error('--real required')
    s=state();f=s['fixture'];s['fresh_run']=uuid4().hex;STATE.write_text(json.dumps(s),encoding='utf-8')
    before=helper({'action':'inspect','tag':f['tag'],'fixture':f})
    prefix=ROOT/'docs/evidence/performance/reservation_create'
    final=prefix.with_suffix('.json')
    env=dict(os.environ,AE4_QA_STATE=str(STATE),AE4_SCENARIO='reservation_create',AE4_FINAL_STATS=str(final))
    command=[str(ROOT/'backend/.demo/qa/Scripts/python.exe'),'-m','locust','-f','performance/locustfile.py','--headless',
             '--host','http://127.0.0.1:8000','-u','1','-r','1','-t','30s','--only-summary','--csv',str(prefix)]
    with (ROOT/'backend/.demo/macro4-load-fresh.log').open('w',encoding='utf-8') as out:
        process=subprocess.run(command,env=env,cwd=ROOT/'backend',stdout=out,stderr=subprocess.STDOUT,timeout=60)
    result=json.loads(final.read_text(encoding='utf-8'))
    after=helper({'action':'inspect','tag':f['tag'],'fixture':f})
    result.update(name='reservation_create',scenario='fresh hotel reservations',users=1,
                  created_rows=after['reservations']-before['reservations'],exit_code=process.returncode)
    result['error_rate']=result['failures']/result['requests'];result['success_rate']=1-result['error_rate']
    assert result['requests']==20 and result['failures']==0 and result['created_rows']==20,result
    path=ROOT/'docs/evidence/performance/summary.json';report=json.loads(path.read_text(encoding='utf-8'))
    report['scenarios']=[r for r in report['scenarios'] if r['name']!='reservation_create']+[result]
    evidence('performance/summary.json',report)
    for suffix in ['_stats_history.csv','_exceptions.csv']:prefix.with_name(prefix.name+suffix).unlink(missing_ok=True)
    print(json.dumps(result))

if __name__=='__main__':main()
