"""GET-only boundary. SQL fallback is advisory; writes never use this client."""
import logging
from threading import Lock
import time
import httpx
from fastapi import HTTPException
import config
import observability as obs
from messaging.correlation import current

logger=logging.getLogger(__name__)

class CircuitBreaker:
    def __init__(self,clock=time.monotonic):
        self.clock=clock; self.lock=Lock(); self.state="CLOSED"; self.failures=0; self.opened_at=0; self.probing=False
    def admit(self):
        with self.lock:
            if self.state=="OPEN":
                if self.clock()-self.opened_at < max(.01,config.BREAKER_OPEN_SECONDS): return False
                self.state="HALF_OPEN"; self.probing=False
                obs.circuit_state.state(self.state)
                logger.info("availability_circuit_half_open")
            if self.state=="HALF_OPEN":
                if self.probing:return False
                self.probing=True
            return True
    def success(self):
        with self.lock:
            was=self.state;self.state="CLOSED";self.failures=0;self.probing=False
            obs.circuit_state.state(self.state)
            if was!="CLOSED":logger.info("availability_circuit_closed")
    def failure(self):
        with self.lock:
            self.failures+=1
            if self.state=="HALF_OPEN" or self.failures>=max(1,config.BREAKER_FAILURE_THRESHOLD):
                self.state="OPEN";self.opened_at=self.clock();self.probing=False
                obs.circuit_state.state(self.state)
                logger.warning("availability_circuit_open")

breaker=CircuitBreaker()
client=httpx.Client(limits=httpx.Limits(max_connections=20,max_keepalive_connections=10),trust_env=False)

def fetch(path,params,adapter,fallback):
    if not config.AVAILABILITY_URL:return fallback()
    if not breaker.admit():
        logger.info("availability_circuit_bypass_sql")
        return fallback()
    deadline=time.monotonic()+max(.05,config.AVAILABILITY_DEADLINE_SECONDS)
    for attempt in range(min(1,max(0,config.AVAILABILITY_RETRIES))+1):
        remaining=deadline-time.monotonic()
        if remaining<=0:break
        timeout=httpx.Timeout(connect=min(remaining,max(.01,config.AVAILABILITY_CONNECT_TIMEOUT)),
            read=min(remaining,max(.01,config.AVAILABILITY_READ_TIMEOUT)),write=min(remaining,.5),pool=min(remaining,.2))
        try:
            with obs.span("availability.get",kind=obs.trace.SpanKind.CLIENT):
                headers={**obs.carrier(),"X-Correlation-ID":current()}
                with client.stream("GET",config.AVAILABILITY_URL+path,params=params,headers=headers,timeout=timeout) as response:
                    if response.status_code in {400,404}:
                        breaker.success()
                        raise HTTPException(response.status_code,"Datos inválidos" if response.status_code==400 else "Publicación no disponible")
                    response.raise_for_status()
                    body=bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body)>262144 or time.monotonic()>deadline:raise ValueError("Availability response budget exceeded")
                    value=adapter.validate_json(bytes(body))
                    breaker.success()
                    return value
        except HTTPException:raise
        except ValueError:break
        except httpx.HTTPError as exc:
            if isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code<500:break
            if attempt==0 and time.monotonic()+.025<deadline:
                time.sleep(.025)
                continue
            break
    breaker.failure()
    logger.warning("availability_unavailable_using_sql")
    with obs.span("availability.sql_fallback"):
        return fallback()
