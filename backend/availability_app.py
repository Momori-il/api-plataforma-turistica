"""Private read-only process: existing public inventory contracts only."""
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Annotated
from fastapi import Depends, FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from sqlalchemy.orm import Session
import config
import observability as obs
from database.connection import engine, get_db
from schemas.habitacion import DisponibilidadParams, DisponibilidadResponse, HabitacionDisponibilidadResponse
from schemas.actividad import TurnoSearchParams, TurnoSearchResponse, TurnoPublicResponse
from services.habitacion_service import HabitacionService
from services.actividad_service import ActividadService
from services.http_controls import OperationalMiddleware, metrics_response
from services.readiness import readiness

obs.configure()
@asynccontextmanager
async def lifespan(_app):
    config.validate_runtime("availability-api")
    yield

app=FastAPI(title="Availability interna",lifespan=lifespan)
app.add_middleware(OperationalMiddleware)
Id=Annotated[int,Path(gt=0,le=2147483647)]

@app.exception_handler(HTTPException)
async def http_error(request,exc):
    return JSONResponse(status_code=exc.status_code,headers=exc.headers,
        content={"error":HTTPStatus(exc.status_code).phrase,"message":exc.detail})

@app.exception_handler(RequestValidationError)
async def input_error(request,exc):
    details=" | ".join(".".join(str(v) for v in e['loc'] if v!='body')+": "+e['msg'] for e in exc.errors())
    return JSONResponse(status_code=400,content={"error":"Bad Request","message":"Faltan campos obligatorios o los datos son inválidos","details":details})

@app.get("/health")
def health():return {"status":"ok"}

@app.get("/ready")
def ready():
    value=readiness(engine,availability=True)
    return JSONResponse(status_code=200 if value['database']=='ok' else 503,content=value)

@app.get("/metrics",include_in_schema=False)
def metrics(request:Request):return metrics_response(request.headers.get("Authorization"))

@app.get("/api/v1/hoteles/{hotel_id}/habitaciones/disponibilidad",response_model=DisponibilidadResponse)
def hotel(hotel_id:Id,params:Annotated[DisponibilidadParams,Query()],db:Session=Depends(get_db)):
    return HabitacionService.availability(db,hotel_id,params)

@app.get("/api/v1/hoteles/{hotel_id}/habitaciones/{habitacion_id}/disponibilidad",response_model=HabitacionDisponibilidadResponse)
def room(hotel_id:Id,habitacion_id:Id,params:Annotated[DisponibilidadParams,Query()],db:Session=Depends(get_db)):
    return HabitacionService.availability(db,hotel_id,params,habitacion_id)

@app.get("/api/v1/actividades/{actividad_id}/turnos/",response_model=list[TurnoPublicResponse])
def turns(actividad_id:Id,params:Annotated[TurnoSearchParams,Query()],db:Session=Depends(get_db)):
    return ActividadService.search_turns(db,actividad_id,params).turnos

@app.get("/api/v1/actividades/{actividad_id}/turnos/disponibilidad",response_model=TurnoSearchResponse)
def search(actividad_id:Id,params:Annotated[TurnoSearchParams,Query()],db:Session=Depends(get_db)):
    return ActividadService.search_turns(db,actividad_id,params,available_only=True)

@app.get("/api/v1/actividades/{actividad_id}/turnos/{turno_id}",response_model=TurnoPublicResponse)
def turn(actividad_id:Id,turno_id:Id,personas:Annotated[int,Query(ge=1,le=1000)]=1,db:Session=Depends(get_db)):
    return ActividadService.public_turn(db,actividad_id,turno_id,personas)
