"""Real local HTTP system/security/concurrency checks on the tagged Docker fixture."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from threading import Barrier
from uuid import uuid4
import httpx
import jwt
from scripts.macro4_support import ROOT,STATE,state,evidence,helper


def run():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');args=parser.parse_args()
    if not args.real:parser.error('--real required')
    s=state();f=s['fixture'];report={'checks':[],'concurrency':[],'security':[]}
    api=httpx.Client(base_url='http://127.0.0.1:8000',timeout=15,trust_env=False)
    headers={}
    def check(name,response,status,group='checks'):
        assert response.status_code in ([status] if isinstance(status,int) else status),(name,response.status_code,response.text[:200])
        report[group].append({'name':name,'status':response.status_code,'passed':True})
        return response.json() if response.content else None
    def race(requests):
        barrier=Barrier(len(requests))
        def invoke(item):
            barrier.wait(timeout=10)
            with httpx.Client(base_url='http://127.0.0.1:8000',timeout=15,trust_env=False) as client:
                return client.request(**item)
        with ThreadPoolExecutor(max_workers=len(requests)) as pool:return list(pool.map(invoke,requests))
    try:
        for role,user in f['users'].items():
            result=check('login_'+role,api.post('/auth/login',json={'email':user['email'],'password':s['password']}),200)
            headers[role]={'Authorization':'Bearer '+result['access_token']}
            s['sessions'][role]['accessToken']=result['access_token']
            check('me_'+role,api.get('/auth/me',headers=headers[role]),200)
        STATE.write_text(json.dumps(s),encoding='utf-8')
        for path in ['/api/v1/hoteles/','/api/v1/actividades/']:
            check('public_'+path,api.get(path),200)
        for role in ['PRESTADOR','ADMIN']:
            for path in ['/api/v1/hoteles/gestion','/api/v1/actividades/gestion','/api/v1/gestion/reservas',
                         f"/api/v1/hoteles/{f['hotel']}/habitaciones/gestion",f"/api/v1/actividades/{f['activity']}/turnos/gestion"]:
                data=check(role+'_'+path,api.get(path,headers=headers[role]),200)
                if role=='PRESTADOR' and path=='/api/v1/hoteles/gestion':
                    rows=data if isinstance(data,list) else data['items']
                    assert {r['id'] for r in rows}=={f['hotel']}
        check('admin_users',api.get('/api/v1/admin/usuarios',headers=headers['ADMIN']),200)
        query={'fecha_desde':f['fecha_desde'],'fecha_hasta':f['fecha_hasta'],'personas':1,'cantidad_habitaciones':1}
        body={'hotel_id':f['hotel'],'habitacion_id':f['room'],**query}
        for kind,payload in [('hotel',body),('actividad',{'actividad_id':f['activity'],'turno_id':f['turn'],'personas':1})]:
            path='/api/v1/reservas/'+kind
            reservation=check(kind+'_create',api.post(path,json=payload,headers={**headers['TURISTA'],'Idempotency-Key':f['tag']+'-system-'+kind}),201)
            rid=reservation['id'];pay=f'/api/v1/reservas/{rid}/pagos/simular'
            paid=check(kind+'_pay',api.post(pay,json={'clave_idempotencia':str(uuid4()),'resultado':'APROBADO'},headers=headers['TURISTA']),201)
            assert paid['reserva']['estado']=='CONFIRMADA' and paid['pago']['importe']==reservation['total']
            for role in ['PRESTADOR','ADMIN']:
                check(kind+'_received_'+role,api.get(f'/api/v1/gestion/reservas/{rid}',headers=headers[role]),200)
            check(kind+'_admin_payments',api.get(f'/api/v1/gestion/reservas/{rid}/pagos',headers=headers['ADMIN']),200)
            check(kind+'_confirmation',api.get(f'/api/v1/reservas/{rid}',headers=headers['TURISTA']),200)
            check(kind+'_cancel',api.patch(f'/api/v1/reservas/{rid}/cancelar',headers=headers['TURISTA']),200)
        for kind,payload in [('hotel',{**body,'habitacion_id':f['last_room']}),('actividad',{'actividad_id':f['activity'],'turno_id':f['last_turn'],'personas':1})]:
            requests=[dict(method='POST',url='/api/v1/reservas/'+kind,json=payload,headers={**headers['TURISTA'],'Idempotency-Key':f['tag']+'-last-'+kind+'-'+str(i)}) for i in range(2)]
            responses=race(requests);statuses=sorted(r.status_code for r in responses)
            assert statuses==[201,409],(kind,statuses)
            report['concurrency'].append({'name':'last_'+kind,'statuses':statuses,'passed':True})
        key=f['tag']+'-same-key'
        responses=race([dict(method='POST',url='/api/v1/reservas/hotel',json=body,headers={**headers['TURISTA'],'Idempotency-Key':key}) for _ in range(2)])
        assert all(r.status_code==201 for r in responses)
        rid=responses[0].json()['id'];assert {r.json()['id'] for r in responses}=={rid}
        report['concurrency'].append({'name':'same_idempotency_key','statuses':[r.status_code for r in responses],'unique_reservations':1,'passed':True})
        check('different_payload_same_key',api.post('/api/v1/reservas/hotel',json={**body,'personas':2},headers={**headers['TURISTA'],'Idempotency-Key':key}),409,'security')
        pay=f'/api/v1/reservas/{rid}/pagos/simular';payload={'clave_idempotencia':str(uuid4()),'resultado':'APROBADO'}
        responses=race([dict(method='POST',url=pay,json=payload,headers=headers['TURISTA']) for _ in range(2)])
        assert sorted(r.status_code for r in responses)==[200,201]
        assert len({r.json()['pago']['id'] for r in responses})==1
        report['concurrency'].append({'name':'duplicate_payment','statuses':[r.status_code for r in responses],'approved_payments':1,'passed':True})
        # Separate pending booking: both valid serializations must end CANCELADA, at most one approval.
        r=api.post('/api/v1/reservas/hotel',json=body,headers={**headers['TURISTA'],'Idempotency-Key':f['tag']+'-cancel-pay'});assert r.status_code==201
        rid=r.json()['id'];responses=race([
            dict(method='POST',url=f'/api/v1/reservas/{rid}/pagos/simular',json={'clave_idempotencia':str(uuid4()),'resultado':'APROBADO'},headers=headers['TURISTA']),
            dict(method='PATCH',url=f'/api/v1/reservas/{rid}/cancelar',headers=headers['TURISTA'])])
        assert responses[0].status_code in [201,409] and responses[1].status_code==200
        assert api.get(f'/api/v1/reservas/{rid}',headers=headers['TURISTA']).json()['estado']=='CANCELADA'
        report['concurrency'].append({'name':'cancel_vs_payment','statuses':[r.status_code for r in responses],'final_state':'CANCELADA','passed':True})
        for token in [None,'invalid']:
            check('jwt_missing' if token is None else 'jwt_invalid',api.get('/auth/me',headers={} if token is None else {'Authorization':'Bearer '+token}),401,'security')
        claims=jwt.decode(s['sessions']['TURISTA']['accessToken'],options={'verify_signature':False})
        claims['exp']=claims['iat']-1
        secret=(ROOT/'backend/.demo/ae4-docker/jwt_secret').read_text(encoding='utf-8').strip()
        expired=jwt.encode(claims,secret,algorithm='HS256')
        check('jwt_expired',api.get('/auth/me',headers={'Authorization':'Bearer '+expired}),401,'security')
        check('wrong_role',api.get('/api/v1/admin/usuarios',headers=headers['PRESTADOR']),403,'security')
        # Prove ownership denial against rows known to exist; never mutate them.
        foreign=helper({'action':'inspect','tag':f['tag'],'fixture':f})
        assert foreign['foreign_reservation_id'] and foreign['foreign_hotel_id']
        check('IDOR_other_tourist',api.get(f"/api/v1/reservas/{foreign['foreign_reservation_id']}",headers=headers['TURISTA']),404,'security')
        check('BOLA_other_provider',api.get(f"/api/v1/hoteles/gestion/{foreign['foreign_hotel_id']}",headers=headers['PRESTADOR']),404,'security')
        check('extra_fields',api.post('/api/v1/reservas/hotel',json={**body,'total':1},headers=headers['TURISTA']),400,'security')
        check('sql_injection_email',api.post('/auth/login',json={'email':"' OR 1=1 --",'password':'x'}),400,'security')
        check('oversized_body',api.post('/auth/login',content='x'*70000,headers={'Content-Type':'application/json'}),413,'security')
        response=api.get('/api/v1/hoteles/',params={'nombre':'<script>alert(1)</script>'})
        check('json_not_html',response,200,'security')
        assert 'application/json' in response.headers['content-type'] and response.headers['x-content-type-options']=='nosniff'
        # Current 10/min quota includes the earlier three role logins and the invalid email.
        statuses=[]
        for _ in range(12):
            response=api.post('/auth/login',json={});statuses.append(response.status_code)
            if response.status_code==429:assert response.headers.get('Retry-After');break
        assert 429 in statuses
        report['security'].append({'name':'real_redis_rate_limit','statuses':statuses,'passed':True})
        report['integrity']=helper({'action':'inspect','tag':f['tag'],'fixture':f})
        evidence('system/http.json',report)
        print(json.dumps({'checks':len(report['checks']),'concurrency':len(report['concurrency']),'security':len(report['security'])}))
    finally:api.close()

if __name__=='__main__':run()
