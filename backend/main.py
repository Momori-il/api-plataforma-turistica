from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
from http import HTTPStatus
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.exc import OperationalError, TimeoutError as SQLPoolTimeout
from database.connection import engine
from config import APP_PORT, CORS_ORIGINS
from routes.hotel_routes import router as hotel_router
from routes.viaje_routes import router as viaje_router
from routes.auth_routes import router as auth_router
from routes.habitacion_routes import router as habitacion_router
from routes.actividad_routes import router as actividad_router, turno_router
from routes.reserva_routes import router as reserva_router
from routes.pago_routes import router as pago_router
from routes.gestion_routes import router as gestion_router, admin_router
from schemas.error import HTTPError
from fastapi.middleware.cors import CORSMiddleware
from messaging import transactional  # Register SQL unit-of-work hooks once.
from contextlib import asynccontextmanager
import config
import observability as obs
from services.http_controls import OperationalMiddleware, metrics_response

obs.configure()

@asynccontextmanager
async def lifespan(_app):
    config.validate_runtime()
    yield

# El esquema se prepara con el script base y scripts.migrate --apply.
# Importar la API y consultar OpenAPI no abre conexiones ni modifica tablas.

app = FastAPI(
    title="API - Plataforma Turística",
    description="MVP de turismo: hoteles, habitaciones, actividades, reservas, pagos simulados y gestión por rol.",
    version="2.0", lifespan=lifespan
)

# 1. MANEJADOR DE VALIDACIONES: Convierte el 422 en 400 (Requerimiento AE1)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errores = []
    for error in exc.errors():
        campo = ".".join(str(loc) for loc in error.get("loc", []) if loc != "body")
        mensaje = error.get("msg", "")
        errores.append(f"{campo}: {mensaje}")
    
    detalle_errores = " | ".join(errores)

    # Retorna 400 Bad Request con estructura estandarizada
    return JSONResponse(
        status_code=400,
        content={
            "error": "Bad Request",
            "message": "Faltan campos obligatorios o los datos son inválidos",
            "details": detalle_errores
        }
    )

# 1.5. MANEJADOR DE EXCEPCIONES HTTP: Estandariza el 404 y otros (Requerimiento AE1)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    try:
        error_name = HTTPStatus(exc.status_code).phrase
    except ValueError:
        error_name = "HTTP Error"

    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "error": error_name,
            "message": exc.detail
        }
    )

@app.exception_handler(OperationalError)
@app.exception_handler(SQLPoolTimeout)
async def sql_unavailable(request,exc):
    logging.getLogger(__name__).warning('sql_operation_unavailable',extra={'exception_type':type(exc).__name__})
    return JSONResponse(status_code=503,headers={'Retry-After':'1'},content={'error':'Service Unavailable','message':'Base de datos ocupada o temporalmente no disponible'})

# 2. MIDDLEWARE DE ERRORES CENTRALIZADO: Captura fallos imprevistos (500)
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logging.getLogger(__name__).error("http_unhandled_error",extra={"exception_type":type(exc).__name__})
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "Ha ocurrido un fallo imprevisto en el servidor."
            }
        )

# CORS envuelve también las respuestas 500 del manejador de errores.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET","POST","PUT","PATCH","HEAD","OPTIONS"],
    allow_headers=["Authorization","Content-Type","Accept","Idempotency-Key","X-Correlation-ID","traceparent","tracestate"],
    expose_headers=["X-Correlation-ID", "Retry-After"],
)
app.add_middleware(OperationalMiddleware)

@app.get("/metrics", include_in_schema=False)
def metrics(request: Request):
    return metrics_response(request.headers.get("Authorization"))

# Contratos del MVP y compatibilidad de Viajes AE2.
app.include_router(hotel_router)
app.include_router(viaje_router)
app.include_router(auth_router)
app.include_router(habitacion_router)
app.include_router(actividad_router)
app.include_router(turno_router)
app.include_router(reserva_router)
app.include_router(pago_router)
app.include_router(gestion_router)
app.include_router(admin_router)


def openapi_contract():
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
        schema.setdefault("components", {}).setdefault("schemas", {})["HTTPError"] = HTTPError.model_json_schema()
        error_content = {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPError"}}}
        for url, path in schema["paths"].items():
            for method, operation in path.items():
                if method not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                    continue
                responses = operation["responses"]
                if "422" in responses:
                    responses.pop("422")
                    responses.setdefault("400", {"description": "Datos o parámetros inválidos"})
                responses.setdefault("500", {"description": "Fallo interno sin detalles sensibles"})
                if url.startswith(("/auth/", "/api/")):
                    responses.setdefault("503", {"description": "Dependencia o recurso temporalmente no disponible; Retry-After cuando corresponda"})
                if method in {"post", "put", "patch"}:
                    responses.setdefault("413", {"description": "El cuerpo excede el límite configurado"})
                if url in {"/auth/login", "/auth/register"} or url.endswith("/pagos/simular") and method == "post":
                    responses.setdefault("429", {"description": "Cuota excedida; reintentar después de Retry-After"})
                if url in {"/api/v2/viajes/{id}", "/api/v2/viajes/{id}/hoteles"}:
                    responses.setdefault("404", {"description": "Viaje o alojamiento no encontrado"})
                    if method == "post":
                        responses.setdefault("409", {"description": "Estadía solapada o regla de negocio"})
                for status, response in responses.items():
                    if status in {"400", "401", "403", "404", "409", "413", "429", "500", "503"} and not (status == "503" and url in {"/health/db", "/ready"}):
                        response["content"] = error_content
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = openapi_contract

@app.get("/ready", tags=["Entorno"], responses={503: {"description": "Dependencia crítica no disponible"}})
def ready():
    from services.readiness import readiness
    result = readiness(engine)
    return JSONResponse(status_code=503 if result["database"] != "ok" else 200, content=result)


@app.get("/health", tags=["Entorno"])
def health():
    return {"status": "ok"}


@app.get("/health/db", tags=["Entorno"], responses={
    503: {
        "description": "SQL Server no disponible",
        "content": {"application/json": {"schema": {
            "type": "object",
            "properties": {"status": {"const": "unavailable"}, "database": {"const": "sqlserver"}},
            "required": ["status", "database"],
        }}},
    },
})
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "sqlserver"},
        )
    return {"status": "ok", "database": "sqlserver"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=APP_PORT, reload=True)
