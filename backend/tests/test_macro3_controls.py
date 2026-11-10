"""Security/resilience contracts; no live SQL, broker or Redis connections."""
from datetime import datetime,timedelta,timezone
import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
import httpx
import jwt
import pytest
import redis
from fastapi import HTTPException
from pydantic import TypeAdapter
from sqlalchemy.orm import sessionmaker
import config
import observability as obs
from main import app
from messaging import relay,worker
from models.messaging import OutboxEventDB
from services import availability_gateway as gateway,redis_support
from tests.test_reservas import bookings,create,cancel
from tests.test_gestion import panel
from tests.test_ae4_distribution import distributed

@pytest.mark.parametrize('path,method,body,status',[
 ('/health','GET',None,200),('/missing','GET',None,404),('/auth/me','GET',None,401),
 ('/auth/login','POST',{},400),('/ready','GET',None,503)])
def test_security_headers_all_statuses(auth_env,path,method,body,status,monkeypatch):
    if path == '/ready':
        # Exercise headers on a deliberate dependency failure, also with --sqlserver.
        monkeypatch.setattr('services.readiness.readiness', lambda engine: {
            'status':'unavailable','database':'unavailable','redis':'disabled','rabbitmq':'disabled'})
    response=auth_env['client'].request(method,path,json=body,headers={'Origin':'http://127.0.0.1:5500'})
    assert response.status_code==status
    assert response.headers['x-content-type-options']=='nosniff'
    assert response.headers['x-frame-options']=='DENY'
    assert response.headers['content-security-policy']=="default-src 'none'; frame-ancestors 'none'"
    assert response.headers['access-control-allow-origin']=='http://127.0.0.1:5500'
    assert response.headers['x-correlation-id']

def test_rate_limit_atomic_429_and_cors(auth_env,monkeypatch):
    backend=MagicMock();backend.eval.side_effect=[[1,60],[2,59]]
    monkeypatch.setattr(redis_support,'client',lambda:backend)
    monkeypatch.setattr(config,'RATE_LIMIT_ENABLED',True)
    monkeypatch.setattr(config,'LOGIN_RATE_LIMIT',1)
    c=auth_env['client'];headers={'Origin':'http://127.0.0.1:5500'}
    assert c.post('/auth/login',json={},headers=headers).status_code==400
    response=c.post('/auth/login',json={},headers=headers)
    assert response.status_code==429 and response.headers['retry-after']=='59'
    assert response.headers['access-control-allow-origin']==headers['Origin']
    assert response.headers['x-frame-options']=='DENY'
    assert 'incr' in backend.eval.call_args.args[0] and 'expire' in backend.eval.call_args.args[0]

def test_rate_limit_redis_failure_is_logged(auth_env,monkeypatch,caplog):
    backend=MagicMock();backend.eval.side_effect=redis.ConnectionError('offline')
    monkeypatch.setattr(redis_support,'client',lambda:backend)
    monkeypatch.setattr(config,'RATE_LIMIT_ENABLED',True)
    assert auth_env['client'].post('/auth/login',json={}).status_code==400
    assert 'rate_limit_unavailable' in caplog.text

def test_body_budget(auth_env,monkeypatch):
    monkeypatch.setattr(config,'MAX_REQUEST_BODY_BYTES',32)
    r=auth_env['client'].post('/auth/login',content='x'*33)
    assert r.status_code==413 and r.headers['x-content-type-options']=='nosniff'

def test_breaker_open_half_open_single_probe_and_recovery(monkeypatch):
    now=[0.0];b=gateway.CircuitBreaker(lambda:now[0])
    monkeypatch.setattr(config,'BREAKER_FAILURE_THRESHOLD',2);monkeypatch.setattr(config,'BREAKER_OPEN_SECONDS',10)
    assert b.admit();b.failure();assert b.state=='CLOSED'
    assert b.admit();b.failure();assert b.state=='OPEN' and not b.admit()
    now[0]=11;assert b.admit() and b.state=='HALF_OPEN' and not b.admit()
    b.success();assert b.state=='CLOSED' and b.admit()
    b.failure();b.failure();now[0]=22;assert b.admit();b.failure();assert b.state=='OPEN'

@pytest.fixture
def remote(monkeypatch):
    monkeypatch.setattr(config,'AVAILABILITY_URL','http://availability.test')
    monkeypatch.setattr(config,'AVAILABILITY_RETRIES',1)
    monkeypatch.setattr(config,'BREAKER_FAILURE_THRESHOLD',1)
    monkeypatch.setattr(gateway,'breaker',gateway.CircuitBreaker())
    return monkeypatch

@pytest.mark.parametrize('failure',[httpx.ConnectError,httpx.ReadTimeout])
def test_safe_get_retry_breaker_bypass_and_sql_fallback(remote,failure):
    calls=[]
    def down(request):calls.append(request.method);raise failure('offline')
    with httpx.Client(transport=httpx.MockTransport(down)) as client:
        remote.setattr(gateway,'client',client)
        assert gateway.fetch('/inventory',{},TypeAdapter(dict[str,int]),lambda:{'stock':1})=={'stock':1}
        assert gateway.breaker.state=='OPEN' and calls==['GET','GET']
        assert gateway.fetch('/inventory',{},TypeAdapter(dict[str,int]),lambda:{'stock':2})=={'stock':2}
        assert len(calls)==2

def test_deadline_prevents_extra_retry_and_explicit_phase_timeouts(remote):
    clock=[0.0];seen=[]
    remote.setattr(gateway,'time',SimpleNamespace(monotonic=lambda:clock[0],sleep=lambda seconds:None))
    def slow(request):
        seen.append(request);clock[0]=5;raise httpx.ReadTimeout('controlled timeout')
    with httpx.Client(transport=httpx.MockTransport(slow)) as client:
        remote.setattr(gateway,'client',client)
        assert gateway.fetch('/inventory',{},TypeAdapter(dict),lambda:{'sql':True})=={'sql':True}
    assert len(seen)==1
    timeout=seen[0].extensions['timeout']
    assert timeout['connect']<=.3 and timeout['read']<=1 and timeout['pool']<=.2 and timeout['write']<=.5

def test_invalid_upstream_contract_falls_back_without_retry(remote):
    calls=[]
    def bad(request):calls.append(1);return httpx.Response(200,content=b'invalid-json')
    with httpx.Client(transport=httpx.MockTransport(bad)) as client:
        remote.setattr(gateway,'client',client)
        assert gateway.fetch('/inventory',{},TypeAdapter(dict),lambda:{'sql':True})=={'sql':True}
    assert calls==[1]

@pytest.mark.parametrize('status',[400,404])
def test_upstream_business_error_has_no_retry_or_open(remote,status):
    calls=[]
    def respond(request):calls.append(1);return httpx.Response(status,json={})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        remote.setattr(gateway,'client',client)
        with pytest.raises(HTTPException) as caught:gateway.fetch('/inventory',{},TypeAdapter(dict),lambda:pytest.fail('Unexpected SQL fallback'))
    assert caught.value.status_code==status and calls==[1] and gateway.breaker.state=='CLOSED'

def test_get_success_preserves_dto_and_trace_headers(remote):
    seen=[]
    def respond(request):seen.append(request);return httpx.Response(200,json={'stock':3})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        remote.setattr(gateway,'client',client)
        assert gateway.fetch('/inventory',{'personas':2},TypeAdapter(dict[str,int]),lambda:None)=={'stock':3}
    assert seen[0].method=='GET' and seen[0].url.params['personas']=='2' and seen[0].headers['x-correlation-id']

@pytest.mark.parametrize('kind',['hotel','actividad'])
def test_tourist_cannot_read_cancel_or_pay_other_booking(bookings,kind):
    e=bookings;r=create(e,'hotel' if kind=='hotel' else 'activity');rid=r.json()['id'];h=e['headers']['otro']
    for response in [e['client'].get(f'/api/v1/reservas/{rid}',headers=h),
                     e['client'].patch(f'/api/v1/reservas/{rid}/cancelar',headers=h),
                     e['client'].post(f'/api/v1/reservas/{rid}/pagos/simular',headers=h,json={'clave_idempotencia':str(uuid4()),'resultado':'APROBADO'})]:
        assert response.status_code==404 and 'total' not in response.json()

@pytest.mark.parametrize('resource',['hotel','activity'])
def test_provider_bola_managed_parent(panel,resource):
    e=panel;obj=e['second_hotel'] if resource=='hotel' else e['second_activity']
    path='/api/v1/hoteles/gestion/' if resource=='hotel' else '/api/v1/actividades/gestion/'
    r=e['client'].get(path+str(obj.id),headers=e['headers']['p1'])
    assert r.status_code==404 and obj.nombre not in r.text

@pytest.mark.parametrize('actor,path',[('p1','/api/v1/admin/usuarios'),('turista','/api/v1/gestion/reservas')])
def test_role_cannot_elevate(bookings,actor,path):
    assert bookings['client'].get(path,headers=bookings['headers'][actor]).status_code==403

def test_admin_account_stays_protected(bookings):
    e=bookings;uid=e['actors']['admin'].id
    assert e['client'].patch(f'/api/v1/admin/usuarios/{uid}/estado',json={'activo':False},headers=e['headers']['admin']).status_code==409
    assert e['db'].get(type(e['actors']['admin']),uid).activo

@pytest.mark.parametrize('case',['invalid','expired','none_algorithm'])
def test_invalid_tokens_rejected(bookings,case):
    now=datetime.now(timezone.utc)
    payload={'sub':str(bookings['actors']['turista'].id),'iat':now-timedelta(hours=2),'nbf':now-timedelta(hours=2),
             'exp':now-timedelta(hours=1),'iss':config.JWT_ISSUER,'aud':config.JWT_AUDIENCE,'jti':uuid4().hex}
    token='invalid' if case=='invalid' else jwt.encode(payload,config.JWT_SECRET_KEY,algorithm='HS256') if case=='expired' else jwt.encode(payload,key='',algorithm='none')
    assert bookings['client'].get('/auth/me',headers={'Authorization':'Bearer '+token}).status_code==401

@pytest.mark.parametrize('name',["Hotel '; DROP TABLE usuarios;--",'<script>alert(1)</script>'])
def test_injection_values_remain_json_data(bookings,name):
    e=bookings;response=e['client'].post('/api/v1/hoteles/',json={'nombre':name,'zona_id':1,'precio_base':100},headers=e['headers']['p1'])
    assert response.status_code==201 and response.json()['nombre']==name
    assert response.headers['content-type'].startswith('application/json')
    assert response.headers['x-content-type-options']=='nosniff'
    assert e['client'].get('/auth/me',headers=e['headers']['turista']).status_code==200

@pytest.mark.parametrize('extra',[{'turista_id':999},{'estado':'CONFIRMADA'},{'total':'.01'}])
def test_server_owned_payload_rejected(bookings,extra):
    assert create(bookings,**extra).status_code==400

def test_excessive_string_rejected(bookings):
    e=bookings;r=e['client'].post('/api/v1/hoteles/',json={'nombre':'x'*101,'zona_id':1,'precio_base':100},headers=e['headers']['p1'])
    assert r.status_code==400

def test_metrics_private_and_bounded_labels(bookings,monkeypatch):
    e=bookings;token='fake-test-metrics-key-'+('x'*32);monkeypatch.setattr(config,'METRICS_TOKEN',token)
    assert e['client'].get('/metrics').status_code==403
    r=create(e);rid=r.json()['id'];e['client'].get(f'/api/v1/reservas/{rid}',headers=e['headers']['turista'])
    response=e['client'].get('/metrics',headers={'Authorization':'Bearer '+token})
    assert response.status_code==200 and 'text/plain' in response.headers['content-type']
    for name in ['requests_total','request_duration_seconds_bucket','reservations_created_total','payments_total','cache_hits_total','events_published_total']:
        assert name in response.text
    assert f'route="/api/v1/reservas/{rid}"' not in response.text and token not in response.text

def test_non_ascii_metrics_credential_is_forbidden_not_exception(monkeypatch):
    from services.http_controls import metrics_response
    monkeypatch.setattr(config,'METRICS_TOKEN','fake-test-metrics-token-'+('x'*32))
    assert metrics_response('Bearer \u00ff').status_code==403

def test_json_log_redacts_credentials(monkeypatch):
    key='fake-secret-do-not-log-'+('z'*32);monkeypatch.setattr(config,'JWT_SECRET_KEY',key)
    record=logging.LogRecord('test',logging.ERROR,__file__,1,'oops '+key+' Bearer jwt-value',(),None)
    data=json.loads(obs.JsonFormatter().format(record))
    assert key not in data['message'] and 'jwt-value' not in data['message']
    assert {'timestamp','level','service','message','correlation_id'}<=set(data)

def test_http_outbox_publish_consume_trace_chain(distributed,monkeypatch,caplog):
    e,_=distributed;monkeypatch.setattr(config,'TRACING_ENABLED',True);caplog.set_level(logging.INFO)
    trace_id='1234567890abcdef1234567890abcdef';cid=str(uuid4())
    response=e['client'].post('/api/v1/reservas/hotel',json=e['hotel_payload'],headers={**e['headers']['turista'],'X-Correlation-ID':cid,'traceparent':f'00-{trace_id}-0123456789abcdef-01'})
    assert response.status_code==201
    event=e['db'].query(OutboxEventDB).one();assert json.loads(event.envelope)['traceparent'].split('-')[1]==trace_id
    connection=MagicMock();channel=connection.channel.return_value
    monkeypatch.setattr(relay,'get_connection',lambda:connection)
    factory=sessionmaker(bind=e['db'].bind)
    assert relay.run_once(factory,relay.publish)
    args=channel.basic_publish.call_args.kwargs;properties=args['properties']
    worker.handle(MagicMock(),SimpleNamespace(delivery_tag=1),properties,args['body'],'audit',factory)
    traces=[r for r in caplog.records if r.getMessage()=='span']
    assert {'http.request','reservation.hotel','outbox.enqueue','messaging.publish','messaging.consume'}<={r.span_name for r in traces}
    assert all(r.trace_id==trace_id and r.correlation_id==cid for r in traces)

@pytest.mark.parametrize('origins',[[],['*'],['https://*.example.com']])
def test_unsafe_production_cors_rejected(monkeypatch,origins):
    monkeypatch.setattr(config,'APP_ENV','production');monkeypatch.setattr(config,'CORS_ORIGINS',origins)
    with pytest.raises(RuntimeError,match='CORS_ORIGINS'):config.validate_runtime('core-api')

def test_secret_file_loader_and_no_implicit_production_defaults(monkeypatch,tmp_path):
    path=tmp_path/'secret';path.write_text('file-value',encoding='utf-8')
    monkeypatch.setenv('UNIT_SECRET','env-value');monkeypatch.setenv('UNIT_SECRET_FILE',str(path))
    assert config.secret('UNIT_SECRET')=='file-value'
    monkeypatch.setattr(config,'APP_ENV','production');monkeypatch.setattr(config,'JWT_SECRET_KEY','changeme')
    with pytest.raises(RuntimeError,match='JWT_SECRET_KEY'):config.validate_runtime('core-api')

def test_valid_production_settings_and_reject_integration_tls(monkeypatch):
    values=dict(APP_ENV='production',JWT_SECRET_KEY='fake-production-test-key-'+('x'*32),
        CORS_ORIGINS=['https://tourism.example.com'],METRICS_TOKEN='x'*40,DB_USER='ae4_core',
        DB_PASSWORD='fake-test-password-12345',DB_ENCRYPT=True,DB_TRUST_SERVER_CERTIFICATE=False,
        REDIS_URL='rediss://:fake-password-123456789@cache.example.com:6379/0',
        RABBITMQ_URL='amqps://ae4:fake-password-123456789@broker.example.com:5671/ae4')
    for name,value in values.items():monkeypatch.setattr(config,name,value)
    config.validate_runtime('core-api')
    monkeypatch.setattr(config,'DB_TRUST_SERVER_CERTIFICATE',True)
    with pytest.raises(RuntimeError,match='SQL TLS'):config.validate_runtime('core-api')
