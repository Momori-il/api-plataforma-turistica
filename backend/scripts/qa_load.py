"""Locust benchmark with controlled cache modes and automatic restoration of service settings."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
import httpx
from scripts.macro4_support import ROOT,STATE,state,docker,evidence

def run():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    if not args.real:parser.error('--real required')
    s=state();f=s['fixture'];assert f['tag'].startswith('macro4-')
    qa_python=ROOT/'backend/.demo/qa/Scripts/python.exe'
    if not qa_python.exists():qa_python=Path(sys.executable)
    override=ROOT/'backend/.demo/macro4-load.override.yml'
    output=ROOT/'docs/evidence/performance';output.mkdir(parents=True,exist_ok=True)
    report={'tool':'Locust 2.47.0','host':'127.0.0.1:8000','think_time_ms':[50,100],
            'warmup_seconds':30,'measured_window_seconds':180,'scenarios':[],
            'scope':'SQL Docker integration only; login/payment quotas raised only during load; rate limiter remains enabled',
            'restore_completed':False}
    if args.resume:
        report=json.loads((output/'summary.json').read_text(encoding='utf-8'))
        report['restore_completed']=False
    api=httpx.Client(base_url='http://127.0.0.1:8000',timeout=15,trust_env=False)
    def healthy():
        end=time.monotonic()+60
        while time.monotonic()<end:
            try:
                if api.get('/ready').json().get('status')=='ready':
                    docker('exec','-T','availability-api','python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)")
                    return
            except (httpx.HTTPError,RuntimeError):pass
            time.sleep(1)
        raise RuntimeError('Services failed to recover')
    def settings(ttl):
        override.write_text('services:\n  core-api:\n    environment:\n      LOGIN_RATE_LIMIT: "100000"\n      PAYMENT_RATE_LIMIT: "100000"\n  availability-api:\n    environment:\n      AVAILABILITY_CACHE_TTL_SECONDS: "'+str(ttl)+'"\n',encoding='utf-8')
        docker('-f',str(ROOT/'compose.yml'),'-f',str(override),'up','-d','--no-deps','core-api','availability-api');healthy()
    def locust(name,scenario,users,seconds,warmup=False):
        previous=next((r for r in report['scenarios'] if r['name']==name),None)
        if previous and previous['failures']==0:return previous
        def counters():
            code="import json,urllib.request,pathlib; token=pathlib.Path('/run/secrets/metrics_token').read_text().strip(); text=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/metrics',headers={'Authorization':'Bearer '+token})).read().decode(); print(json.dumps({line.split()[0]:float(line.split()[1]) for line in text.splitlines() if line.startswith(('cache_hits_total ','cache_misses_total ','cache_fallback_total '))}))"
            return json.loads(docker('exec','-T','availability-api','python','-c',code))
        before=counters()
        final=output/(name+'_final.json')
        env=dict(os.environ,AE4_QA_STATE=str(STATE),AE4_SCENARIO=scenario,AE4_FINAL_STATS=str(final))
        prefix=output/name
        command=[str(qa_python),'-m','locust','-f',str(ROOT/'backend/performance/locustfile.py'),'--headless',
                 '--host','http://127.0.0.1:8000','-u',str(users),'-r',str(users),'--run-time',str(seconds)+'s',
                 '--stop-timeout','15','--only-summary','--csv',str(prefix)]
        with (ROOT/'backend/.demo'/('macro4-load-'+name+'.log')).open('w',encoding='utf-8') as log:
            p=subprocess.run(command,env=env,cwd=ROOT/'backend',stdout=log,stderr=subprocess.STDOUT,timeout=seconds+90)
        rows=list(csv.DictReader(Path(str(prefix)+'_stats.csv').open(encoding='utf-8')))
        total=next(r for r in rows if r['Name']=='Aggregated')
        result={'name':name,'scenario':scenario,'users':users,'seconds':seconds,'exit_code':p.returncode,
                'requests':int(total['Request Count']),'failures':int(total['Failure Count']),
                'average_ms':float(total['Average Response Time']),'median_ms':float(total['Median Response Time']),
                'p95_ms':float(total['95%']),'p99_ms':float(total['99%']),'max_ms':float(total['Max Response Time']),
                'requests_per_second':float(total['Requests/s'])}
        if final.exists():
            result.update(json.loads(final.read_text(encoding='utf-8')))
            result['measurement_source']='Locust final shutdown statistics'
        result['error_rate']=result['failures']/result['requests'] if result['requests'] else 1
        result['success_rate']=1-result['error_rate']
        after=counters();result['cache_counter_delta']={key:after[key]-value for key,value in before.items()}
        if not warmup:
            if previous:report.setdefault('previous_attempts',[]).append(previous)
            report['scenarios']=[r for r in report['scenarios'] if r['name']!=name]+[result]
            evidence('performance/summary.json',report)
        # CSV contains statistics only, no requests or credentials. Keep measured summaries, not redundant histories.
        for suffix in ['_stats_history.csv','_exceptions.csv']:
            Path(str(prefix)+suffix).unlink(missing_ok=True)
        if warmup:
            for suffix in ['_stats.csv','_failures.csv']:Path(str(prefix)+suffix).unlink(missing_ok=True)
            final.unlink(missing_ok=True)
        print(json.dumps(result),flush=True)
        return result
    try:
        settings(10 if args.resume else 0)
        # Reauthenticate after readiness, before load. Credentials remain in the ignored local state only.
        user=f['users']['TURISTA'];r=api.post('/auth/login',json={'email':user['email'],'password':s['password']});assert r.status_code==200
        s['sessions']['TURISTA']['accessToken']=r.json()['access_token'];STATE.write_text(json.dumps(s),encoding='utf-8')
        query={'fecha_desde':f['fecha_desde'],'fecha_hasta':f['fecha_hasta'],'personas':1,'cantidad_habitaciones':1}
        headers={'Authorization':'Bearer '+s['sessions']['TURISTA']['accessToken'],'Idempotency-Key':f['tag']+'-load'}
        r=api.post('/api/v1/reservas/hotel',json={'hotel_id':f['hotel'],'habitacion_id':f['room'],**query},headers=headers)
        assert r.status_code==201
        s['load_reservation']=r.json()['id'];s['payment_key']=str(uuid4());STATE.write_text(json.dumps(s),encoding='utf-8')
        if not any(r['name']=='availability_miss' for r in report['scenarios']):
            locust('warmup_miss','availability_miss',10,30,True)
            locust('availability_miss','availability_miss',10,180)
        settings(10)
        locust('warmup_hit','availability_hit',10,30,True)
        locust('availability_hit','availability_hit',10,180)
        docker('stop','redis')
        locust('availability_fallback','availability_fallback',10,60)
        docker('start','redis');healthy()
        locust('hotels','hotels',10,60)
        locust('login','login',2,60)
        locust('reservation','reservation',5,30)
        locust('payment','payment',5,30)
        for users in [25,50,75]:locust('stress_'+str(users),'availability_stress',users,30)
    finally:
        docker('start','redis')
        docker('up','-d','--no-deps','core-api','availability-api');healthy()
        report['restore_completed']=True
        api.close();evidence('performance/summary.json',report)
    return report

if __name__=='__main__':run()
