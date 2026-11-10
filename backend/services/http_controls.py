"""ASGI controls also cover preflight and controlled error responses."""
from hmac import compare_digest
from contextlib import nullcontext
import hashlib
import logging
import re
import time
from uuid import uuid4
import redis
from starlette.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
import config
import observability as obs
from messaging.correlation import correlation_id, normalize
from services import redis_support

LIMIT_SCRIPT = "local n=redis.call('incr',KEYS[1]); if n==1 then redis.call('expire',KEYS[1],ARGV[1]); end; return {n,redis.call('ttl',KEYS[1])}"

def rate_limit(path, method, address):
    if not config.RATE_LIMIT_ENABLED or method != "POST": return None
    limit = config.LOGIN_RATE_LIMIT if path == "/auth/login" else config.REGISTER_RATE_LIMIT if path == "/auth/register" else config.PAYMENT_RATE_LIMIT if re.fullmatch(r"/api/v1/reservas/[0-9]+/pagos/simular", path) else None
    if limit is None or limit <= 0: return None
    backend = redis_support.client()
    if backend is None: return None
    bucket = "login" if path == "/auth/login" else "register" if path == "/auth/register" else "payment"
    key = "pt:rate:v1:" + hashlib.sha256((config.DB_NAME+":"+bucket+":"+address).encode()).hexdigest()
    try:
        count, ttl = backend.eval(LIMIT_SCRIPT, 1, key, max(1, config.RATE_LIMIT_WINDOW_SECONDS))
        return max(1, int(ttl)) if int(count)>limit else None
    except redis.RedisError:
        logging.getLogger(__name__).warning("rate_limit_unavailable_fail_open")
        return None

def metrics_response(authorization):
    if not config.METRICS_TOKEN or not compare_digest((authorization or "").encode('utf-8'),("Bearer "+config.METRICS_TOKEN).encode('utf-8')):
        return JSONResponse(status_code=403, content={"error":"Forbidden", "message":"Métricas privadas"})
    return Response(obs.generate_latest(obs.registry), media_type="text/plain; version=0.0.4; charset=utf-8")

class OperationalMiddleware:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode("latin1").lower():v.decode("latin1") for k,v in scope.get("headers",[])}
        cid = normalize(headers.get("x-correlation-id"))
        token = correlation_id.set(cid)
        started, status, request_id = time.monotonic(), 500, str(uuid4())
        received=0
        async def bounded_receive():
            nonlocal received
            message=await receive()
            received+=len(message.get('body',b''))
            if received>max(1,config.MAX_REQUEST_BODY_BYTES):raise HTTPException(413,'Cuerpo de petición excesivo')
            return message
        async def secured(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                additions = {"x-correlation-id":cid, "x-content-type-options":"nosniff", "x-frame-options":"DENY",
                    "referrer-policy":"strict-origin-when-cross-origin", "permissions-policy":"camera=(), microphone=()"}
                if scope["path"] not in {"/docs","/redoc","/docs/oauth2-redirect"}:
                    additions["content-security-policy"] = "default-src 'none'; frame-ancestors 'none'"
                message["headers"] = [(k,v) for k,v in message.get("headers",[]) if k.decode().lower() not in additions]
                message["headers"].extend((k.encode(),v.encode()) for k,v in additions.items())
            await send(message)
        try:
            trace_context=obs.span("http.request",headers,obs.trace.SpanKind.SERVER) if scope['path'] not in {'/health','/health/db','/ready','/metrics'} else nullcontext(obs.trace.get_current_span())
            with trace_context as active:
                client = scope.get("client") or ("unknown",0)
                limited = await run_in_threadpool(rate_limit,scope["path"],scope["method"],client[0])
                try:oversized=int(headers.get('content-length','0'))>max(1,config.MAX_REQUEST_BODY_BYTES)
                except ValueError:oversized=False
                if oversized or limited:
                    response = JSONResponse(status_code=429, content={"error":"Too Many Requests", "message":"Demasiados intentos; esperá para reintentar"}, headers={"Retry-After":str(limited)})
                    if oversized:response=JSONResponse(status_code=413,content={'error':'Content Too Large','message':'Cuerpo de petición excesivo'})
                    if headers.get("origin") in config.CORS_ORIGINS:
                        response.headers.update({"Access-Control-Allow-Origin":headers["origin"],"Access-Control-Allow-Credentials":"true","Vary":"Origin"})
                    await response(scope,receive,secured)
                else:
                    await self.app(scope,bounded_receive,secured)
                active.set_attribute("http.response.status_code",status)
                if status>=500:active.set_status(obs.trace.StatusCode.ERROR)
        finally:
            route = getattr(scope.get("route"),"path",None) or (scope["path"] if scope["path"] in {"/auth/login","/auth/register"} else "unmatched")
            elapsed=time.monotonic()-started
            if route not in {"/health","/health/db","/ready","/metrics"}:
                obs.requests.labels(scope["method"],route,str(status)).inc()
                obs.duration.labels(scope["method"],route).observe(elapsed)
                if status>=500: obs.errors.labels(route).inc()
                logging.getLogger("ae4.http").info("http_request",extra=dict(request_id=request_id,method=scope["method"],route=route,
                    status_code=status,duration_ms=round(elapsed*1000,3),correlation_id=cid))
            correlation_id.reset(token)
