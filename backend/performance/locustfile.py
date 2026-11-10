"""Local integration scenarios; credentials/IDs are supplied through an ignored fixture file."""
import json
import os
from datetime import date,timedelta
from pathlib import Path
from collections import Counter
from urllib.parse import urlparse
from locust import HttpUser, task, between, events
from locust.exception import StopUser
import gevent

FIXTURE=json.loads(Path(os.environ['AE4_QA_STATE']).read_text(encoding='utf-8'))
F=FIXTURE['fixture']
SCENARIO=os.environ.get('AE4_SCENARIO','availability')
created_requests=0
response_statuses=Counter()
busy_messages=Counter()

@events.quitting.add_listener
def final_statistics(environment, **kwargs):
    filename=os.environ.get('AE4_FINAL_STATS')
    if not filename:return
    stats=environment.stats.total
    result={'requests':stats.num_requests,'failures':stats.num_failures,
            'average_ms':stats.avg_response_time,'median_ms':stats.median_response_time,
            'p95_ms':stats.get_response_time_percentile(.95),'p99_ms':stats.get_response_time_percentile(.99),
            'max_ms':stats.max_response_time,'requests_per_second':stats.total_rps,
            'response_statuses':dict(response_statuses),'busy_messages':dict(busy_messages)}
    Path(filename).write_text(json.dumps(result,indent=2),encoding='utf-8')

@events.init.add_listener
def guard(environment, **kwargs):
    assert urlparse(environment.host).hostname in {'127.0.0.1','localhost'}, 'Local integration only'
    assert F['tag'].startswith('macro4-')

class DemoUser(HttpUser):
    wait_time=between(.05,.1)

    @task
    def scenario(self):
        global created_requests
        headers={'Authorization':'Bearer '+FIXTURE['sessions']['TURISTA']['accessToken']}
        query={'fecha_desde':F['fecha_desde'],'fecha_hasta':F['fecha_hasta'],'personas':1,'cantidad_habitaciones':1}
        if SCENARIO=='reservation_create':
            if created_requests>=20:raise StopUser()
            created_requests+=1
            day=date.fromisoformat(F['fecha_desde'])+timedelta(days=created_requests*3)
            query.update(fecha_desde=str(day),fecha_hasta=str(day+timedelta(days=1)))
            response=self.client.post('/api/v1/reservas/hotel',json={'hotel_id':F['hotel'],'habitacion_id':F['room'],**query},
                headers={**headers,'Idempotency-Key':F['tag']+'-fresh-'+FIXTURE.get('fresh_run','initial')+'-'+str(created_requests)},name='reservation_create',catch_response=True)
            if created_requests==20:gevent.spawn_later(.1,self.environment.runner.quit)
        elif SCENARIO=='login':
            path='/auth/login';body={'email':F['users']['TURISTA']['email'],'password':FIXTURE['password']}
            response=self.client.post(path,json=body,name='login',catch_response=True)
        elif SCENARIO=='hotels':
            response=self.client.get('/api/v1/hoteles/',name='hotels',catch_response=True)
        elif SCENARIO=='reservation':
            response=self.client.post('/api/v1/reservas/hotel',json={'hotel_id':F['hotel'],'habitacion_id':F['room'],**query},
                headers={**headers,'Idempotency-Key':F['tag']+'-load'},name='reservation_replay',catch_response=True)
        elif SCENARIO=='payment':
            response=self.client.post(f"/api/v1/reservas/{FIXTURE['load_reservation']}/pagos/simular",
                json={'clave_idempotencia':FIXTURE['payment_key'],'resultado':'APROBADO'},headers=headers,name='payment_replay',catch_response=True)
        else:
            response=self.client.get(f"/api/v1/hoteles/{F['hotel']}/habitaciones/disponibilidad",params=query,name=SCENARIO,catch_response=True)
        with response as r:
            response_statuses[str(r.status_code)]+=1
            if r.status_code==503:
                try:busy_messages[r.json().get('message','unavailable')]+=1
                except ValueError:busy_messages['non-JSON unavailable']+=1
            expected={201} if SCENARIO in {'reservation','reservation_create'} else {200,201} if SCENARIO=='payment' else {200}
            if r.status_code not in expected:r.failure('unexpected HTTP '+str(r.status_code));return
            try:
                data=r.json()
                if SCENARIO=='reservation':assert data['id']==FIXTURE['load_reservation']
                if SCENARIO=='payment':assert data['reserva']['id']==FIXTURE['load_reservation'] and data['pago']['estado']=='APROBADO'
                if SCENARIO.startswith('availability'):assert data['hotel_id']==F['hotel']
            except (ValueError,KeyError,AssertionError):r.failure('Contract/invariant mismatch')
