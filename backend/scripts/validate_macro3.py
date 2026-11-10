"""Explicit Docker fault tests; Windows demo is protected by a read-only guard."""
import argparse
from datetime import timedelta
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time
from uuid import uuid4
import httpx
from sqlalchemy import event
import config
from database.connection import engine
from scripts.ae4_preservation import snapshot,check_constraints
from schemas.habitacion import business_today
from security import create_access_token

def run(evidence_section="macro3"):
    docker=shutil.which('docker') or str(Path(os.environ['LOCALAPPDATA'])/'Programs/DockerDesktop/resources/bin/docker.exe')
    environment=dict(os.environ);environment['PATH']=str(Path(docker).parent)+os.pathsep+environment.get('PATH','')
    prefix=[docker,'--context','desktop-linux','compose'];root=config.BASE_DIR.parent
    results={'checks':[],'blocked':[]};ids=[];keys={};cleanup_done=False
    state_file=config.BASE_DIR/'.demo/ae4-m3-validation-run.json'
    workers=['outbox-relay','audit-worker','notifications-worker','availability-worker']
    def command(*args,input=None,timeout=60):
        result=subprocess.run([*prefix,*args],cwd=root,env=environment,input=input,capture_output=True,timeout=timeout)
        if result.returncode:raise RuntimeError('Docker command failed: '+result.stderr.decode(errors='replace')[-1600:])
        return result.stdout.decode(errors='replace')
    def helper(action,**data):
        output=command('run','--rm','-T','--no-deps','sql-init','python','-m','scripts.container_checks',input=json.dumps({'action':action,**data}).encode())
        return json.loads(output)
    def checked(name,details=None):
        results['checks'].append({'name':name,'result':'passed','details':details});print('PASS '+name,flush=True)
    def wait(predicate,seconds=45):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            try:
                value=predicate()
                if value:return value
            except (httpx.HTTPError,RuntimeError):pass
            time.sleep(1)
        raise AssertionError('Controlled integration wait timed out')
    def statuses():
        text=command('ps','--format','json')
        return json.loads(text) if text.lstrip().startswith('[') else [json.loads(line) for line in text.splitlines() if line.startswith('{')]
    def read_only(conn,cursor,statement,params,context,many):
        if not statement.lstrip().upper().startswith(('SELECT','DBCC')):raise RuntimeError('Windows demo writes forbidden')
    event.listen(engine,'before_cursor_execute',read_only)
    original=snapshot(engine);check_constraints(engine)
    baseline=helper('snapshot')['snapshot'];assert baseline==original
    def checkpoint():
        state_file.write_text(json.dumps({'ids':ids,'keys':keys,'expected':baseline}),encoding='utf-8')
    results['native_before']=original
    cid=str(uuid4());trace_id=secrets.token_hex(16)
    api=httpx.Client(base_url='http://127.0.0.1:8000',timeout=10,headers={'X-Correlation-ID':cid},trust_env=False)
    metric_token=(config.BASE_DIR/'.demo/ae4-docker/metrics_token').read_text(encoding='utf-8')
    metric_headers={'Authorization':'Bearer '+metric_token}
    try:
        wait(lambda:api.get('/ready').json().get('status')=='ready')
        live=wait(lambda:(lambda rows:rows if len(rows)==10 and all(r.get('Health')=='healthy' for r in rows) else None)(statuses()),60)
        checked('compose_ten_services_healthy',{'services':[r['Service'] for r in live]})
        assert api.get('/health').status_code==200
        assert api.get('/metrics').status_code==403
        assert api.get('/metrics',headers=metric_headers).status_code==200
        checked('private_metrics_and_probes')
        checked('sql_readonly_permissions',helper('permissions'))
        actors=helper('actors');headers={}
        original_key=config.JWT_SECRET_KEY
        try:
            config.JWT_SECRET_KEY=(config.BASE_DIR/'.demo/ae4-docker/jwt_secret').read_text(encoding='utf-8')
            for actor in actors:
                token,_=create_access_token(actor['id']);headers[actor['role']]={'Authorization':'Bearer '+token}
        finally:config.JWT_SECRET_KEY=original_key
        for role,h in headers.items():
            response=api.get('/auth/me',headers=h);assert response.status_code==200 and response.json()['rol']==role
        for role in ['PRESTADOR','ADMIN']:
            for path in ['/api/v1/hoteles/gestion','/api/v1/actividades/gestion','/api/v1/gestion/reservas']:
                assert api.get(path,headers=headers[role]).status_code==200
        assert api.get('/api/v1/admin/usuarios',headers=headers['ADMIN']).status_code==200
        assert api.get('/api/v1/admin/usuarios',headers=headers['PRESTADOR']).status_code==403
        assert api.get('/api/v1/gestion/reservas',headers=headers['TURISTA']).status_code==403
        checked('three_roles_http_regression')
        start=business_today()+timedelta(days=60)
        query={'fecha_desde':str(start),'fecha_hasta':str(start+timedelta(days=2)),'personas':1,'cantidad_habitaciones':1}
        hotel=None;room=None
        for row in api.get('/api/v1/hoteles/').json():
            response=api.get(f"/api/v1/hoteles/{row['id']}/habitaciones/disponibilidad",params=query)
            assert response.status_code==200,response.text
            if response.json()['habitaciones']:hotel=row['id'];room=response.json()['habitaciones'][0]['id'];break
        assert hotel and room,'No reservable hotel in copied dataset'
        path=f'/api/v1/hoteles/{hotel}/habitaciones/disponibilidad'
        assert api.get(path,params=query).status_code==200
        checked('linux_odbc_public_availability')
        command('stop','availability-api')
        for _ in range(config.BREAKER_FAILURE_THRESHOLD+1):
            response=api.get(path,params=query);assert response.status_code==200,response.text
        metric=api.get('/metrics',headers=metric_headers).text
        assert 'availability_circuit_state{availability_circuit_state="OPEN"} 1.0' in metric
        logs=command('logs','--no-log-prefix','--tail','120','core-api')
        assert 'availability_circuit_bypass_sql' in logs
        checked('availability_down_retry_open_bypass_sql')
        command('start','availability-api');time.sleep(min(11,max(.1,config.BREAKER_OPEN_SECONDS+1)))
        assert api.get(path,params=query).status_code==200
        logs=command('logs','--no-log-prefix','--tail','120','core-api')
        assert 'availability_circuit_half_open' in logs and 'availability_circuit_closed' in logs
        checked('availability_half_open_closed_recovery')
        command('stop','redis')
        assert api.get(path,params=query).status_code==200
        assert api.get('/ready').json()['status']=='degraded'
        command('start','redis');wait(lambda:api.get('/ready').json()['status']=='ready')
        checked('real_redis_down_sql_fallback_recovery')
        command('stop','rabbitmq')
        hkey='macro3-'+uuid4().hex+'-hotel'
        payload={'hotel_id':hotel,'habitacion_id':room,**query}
        response=api.post('/api/v1/reservas/hotel',json=payload,headers={**headers['TURISTA'],'Idempotency-Key':hkey,'traceparent':f'00-{trace_id}-{secrets.token_hex(8)}-01'})
        assert response.status_code==201,response.text
        rid=response.json()['id'];ids.append(rid);keys[str(rid)]=hkey
        checkpoint()
        pending=helper('inspect',ids=ids);assert any(x['status']=='PENDING' for x in pending['events'])
        checked('broker_down_domain_commit_outbox_pending')
        command('start','rabbitmq')
        def published():
            value=helper('inspect',ids=ids)
            return value if value['events'] and all(e['status']=='PUBLISHED' for e in value['events']) and value['audit']==len(value['events']) else None
        wait(published,60);checked('broker_recovery_confirmed_delivery')
        response=api.post('/api/v1/reservas/hotel',json=payload,headers={**headers['TURISTA'],'Idempotency-Key':hkey})
        assert response.status_code==201 and response.json()['id']==rid
        payment={'clave_idempotencia':str(uuid4()),'resultado':'APROBADO'}
        assert api.post(f'/api/v1/reservas/{rid}/pagos/simular',json=payment,headers=headers['TURISTA']).status_code==201
        assert api.post(f'/api/v1/reservas/{rid}/pagos/simular',json=payment,headers=headers['TURISTA']).status_code==200
        assert api.patch(f'/api/v1/reservas/{rid}/cancelar',headers=headers['TURISTA']).status_code==200
        checked('hotel_reservation_payment_replay_cancel')
        activity=None;turn=None
        for row in api.get('/api/v1/actividades/').json():
            response=api.get(f"/api/v1/actividades/{row['id']}/turnos/",params={'personas':1})
            assert response.status_code==200,response.text
            available=[x for x in response.json() if x['disponible']]
            if available:activity=row['id'];turn=available[0]['id'];break
        assert activity and turn,'No future activity in copied dataset'
        command('stop','audit-worker')
        akey='macro3-'+uuid4().hex+'-activity'
        response=api.post('/api/v1/reservas/actividad',json={'actividad_id':activity,'turno_id':turn,'personas':1},headers={**headers['TURISTA'],'Idempotency-Key':akey})
        assert response.status_code==201,response.text
        arid=response.json()['id'];ids.append(arid);keys[str(arid)]=akey
        checkpoint()
        time.sleep(2)
        queues=command('exec','-T','rabbitmq','rabbitmqctl','-q','list_queues','-p','ae4','name','messages_ready','messages_unacknowledged','--formatter','json')
        queues=json.loads(queues[queues.index('['):])
        assert any(q['name']=='ae4.audit.v1' and q['messages_ready']>0 for q in queues)
        command('start','audit-worker');wait(published,60)
        checked('consumer_down_queue_retained_recovery')
        assert api.post(f'/api/v1/reservas/{arid}/pagos/simular',json={'clave_idempotencia':str(uuid4()),'resultado':'APROBADO'},headers=headers['TURISTA']).status_code==201
        assert api.patch(f'/api/v1/reservas/{arid}/cancelar',headers=headers['TURISTA']).status_code==200
        def effects():
            value=published()
            return value if value and value['notifications']==value['expected_notifications'] else None
        effects_report=wait(effects,60);checked('activity_payment_and_idempotent_effects',{'events':len(effects_report['events']),'notifications':effects_report['notifications']})
        records=[]
        for line in command('logs','--no-log-prefix','core-api','availability-api','outbox-relay','audit-worker','notifications-worker').splitlines():
            if line.startswith('{'):
                try:records.append(json.loads(line))
                except ValueError:pass
        traces=[r for r in records if r.get('trace_id')==trace_id and r.get('message')=='span']
        assert {'http.request','reservation.hotel','outbox.enqueue','messaging.publish','messaging.consume'}<={r['span_name'] for r in traces}
        assert all(r['correlation_id']==cid for r in traces)
        checked('real_cross_process_json_trace_chain',{'trace_id':trace_id,'span_count':len(traces)})
        command('stop','sqlserver')
        assert api.get('/health').status_code==200 and api.get('/ready').status_code==503
        wait(lambda:any(r['Service']=='core-api' and r.get('Health')=='unhealthy' for r in statuses()),60)
        checked('sql_dependency_down_liveness_and_unhealthy')
        command('start','sqlserver');wait(lambda:api.get('/ready').json().get('status')=='ready',60)
        wait(lambda:all(r.get('Health')=='healthy' for r in statuses()),60)
        checked('container_restart_dependency_recovery')
        wait(effects,45)
        command('stop',*workers)
        cleanup=helper('cleanup',ids=ids,keys=keys,expected=baseline);cleanup_done=True
        state_file.unlink(missing_ok=True)
        checked('temporary_bookings_cleaned',{'reservations':cleanup['removed_reservations'],'payments':cleanup['removed_payments']})
        assert cleanup['snapshot']==baseline and cleanup['dbcc_violations']==0
        results['isolated_after']=cleanup['snapshot']
    except Exception as exc:
        results['blocked'].append(type(exc).__name__+' during controlled validation')
        raise
    finally:
        # Restore every intentionally stopped dependency even after a failed assertion.
        for names in [['sqlserver','redis','rabbitmq','availability-api'],workers]:
            try:command('start',*names)
            except Exception:pass
        api.close()
        after=snapshot(engine);check_constraints(engine);assert after==original,'Windows demo changed'
        results['native_after']=after;results['dbcc_violations']=0
        event.remove(engine,'before_cursor_execute',read_only)
        if ids and not cleanup_done:
            results['blocked'].append('Temporary integration reservation IDs require guarded cleanup: '+','.join(map(str,ids)))
        path=config.BASE_DIR.parent/'docs/AE4_VALIDATION.json'
        evidence=json.loads(path.read_text(encoding='utf-8'));evidence.setdefault(evidence_section,{})['real_tests']=results
        path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    checked('native_demo_preserved_exactly')
    return results

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--real',action='store_true');parser.add_argument('--evidence-section',choices=['macro3','macro4'],default='macro3');args=parser.parse_args()
    if not args.real:parser.error('Explicit --real required')
    result=run(args.evidence_section);path=config.BASE_DIR.parent/'docs/AE4_VALIDATION.json'
    report=json.loads(path.read_text(encoding='utf-8'));report.setdefault(args.evidence_section,{})['real_tests']=result
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':len(result['checks']),'blocked':result['blocked']}))

if __name__=='__main__':main()
