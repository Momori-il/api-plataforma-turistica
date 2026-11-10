"""Configuración compartida por la API, las pruebas y el consumidor."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# Las variables del proceso tienen prioridad sobre el archivo local.
load_dotenv(BASE_DIR / ".env")

def secret(name, default=""):
    """Docker secret files take precedence; never copy their values into logs."""
    filename = os.getenv(name + "_FILE")
    return Path(filename).read_text(encoding="utf-8").strip() if filename else os.getenv(name, default)

APP_ENV = os.getenv("APP_ENV", "development")
SERVICE_NAME = os.getenv("SERVICE_NAME", "core-api")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_JSON = os.getenv("LOG_JSON", "true").lower() == "true"
TRACING_ENABLED = os.getenv("TRACING_ENABLED", "true").lower() == "true"
TRACE_SAMPLE_RATIO = float(os.getenv("TRACE_SAMPLE_RATIO", "1"))
METRICS_TOKEN = secret("METRICS_TOKEN")
METRICS_PORT = int(os.getenv("METRICS_PORT", "0"))
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", "65536"))
LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "10"))
REGISTER_RATE_LIMIT = int(os.getenv("REGISTER_RATE_LIMIT", "5"))
PAYMENT_RATE_LIMIT = int(os.getenv("PAYMENT_RATE_LIMIT", "30"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
AVAILABILITY_URL = os.getenv("AVAILABILITY_URL", "").rstrip("/")
AVAILABILITY_CONNECT_TIMEOUT = float(os.getenv("AVAILABILITY_CONNECT_TIMEOUT", "0.3"))
AVAILABILITY_READ_TIMEOUT = float(os.getenv("AVAILABILITY_READ_TIMEOUT", "1"))
AVAILABILITY_DEADLINE_SECONDS = float(os.getenv("AVAILABILITY_DEADLINE_SECONDS", "1.5"))
AVAILABILITY_RETRIES = int(os.getenv("AVAILABILITY_RETRIES", "1"))
BREAKER_FAILURE_THRESHOLD = int(os.getenv("BREAKER_FAILURE_THRESHOLD", "5"))
BREAKER_OPEN_SECONDS = float(os.getenv("BREAKER_OPEN_SECONDS", "10"))
RABBITMQ_SOCKET_TIMEOUT = float(os.getenv("RABBITMQ_SOCKET_TIMEOUT", "2"))
RABBITMQ_STACK_TIMEOUT = float(os.getenv("RABBITMQ_STACK_TIMEOUT", "5"))
RABBITMQ_BLOCKED_TIMEOUT = float(os.getenv("RABBITMQ_BLOCKED_TIMEOUT", "3"))
RABBITMQ_HEARTBEAT = int(os.getenv("RABBITMQ_HEARTBEAT", "30"))
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = secret("DB_PASSWORD")
DB_PORT = int(os.getenv("DB_PORT", "0")) or None
DB_ENCRYPT = os.getenv("DB_ENCRYPT", "true").lower() == "true"
DB_TRUST_SERVER_CERTIFICATE = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "false").lower() == "true"
DB_QUERY_TIMEOUT = int(os.getenv("DB_QUERY_TIMEOUT", "5"))
DB_LOCK_TIMEOUT_MS = int(os.getenv("DB_LOCK_TIMEOUT_MS", "2000"))
DB_POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "2"))

# Optional local infrastructure; endpoints and credentials come from the environment.
REDIS_URL = secret("REDIS_URL")
REDIS_TIMEOUT_SECONDS = float(os.getenv("REDIS_TIMEOUT_SECONDS", "0.2"))
AVAILABILITY_CACHE_TTL_SECONDS = float(os.getenv("AVAILABILITY_CACHE_TTL_SECONDS", "10"))
REDIS_LOCK_TTL_MS = int(os.getenv("REDIS_LOCK_TTL_MS", "5000"))
REDIS_LOCK_WAIT_SECONDS = float(os.getenv("REDIS_LOCK_WAIT_SECONDS", "0.15"))
RABBITMQ_URL = secret("RABBITMQ_URL")
AE4_MESSAGING_ENABLED = os.getenv("AE4_MESSAGING_ENABLED", "true").lower() == "true"
AE4_RETRY_DELAYS_MS = tuple(int(x) for x in os.getenv("AE4_RETRY_DELAYS_MS", "5000,30000,120000").split(","))
OUTBOX_LEASE_SECONDS = int(os.getenv("OUTBOX_LEASE_SECONDS", "15"))
OUTBOX_MAX_ATTEMPTS = int(os.getenv("OUTBOX_MAX_ATTEMPTS", "10"))
AE4_QUEUE_PREFIX = os.getenv("AE4_QUEUE_PREFIX", "ae4")

DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_NAME = os.getenv("DB_NAME", "TurismoPosadas")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"
APP_PORT = int(os.getenv("APP_PORT", "8000"))
JWT_SECRET_KEY = secret("JWT_SECRET_KEY")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_ISSUER = os.getenv("JWT_ISSUER", "turismo-posadas-api")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "turismo-posadas-client")
RESERVA_PAGO_MINUTOS = int(os.getenv("RESERVA_PAGO_MINUTOS", "15"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500"
    ).split(",")
    if origin.strip()
]

def validate_runtime(service=None):
    if APP_ENV not in {"production", "integration"}:
        return
    from urllib.parse import urlsplit
    role = service or SERVICE_NAME
    problems = []
    if "core" in role and (len(JWT_SECRET_KEY.encode()) < 32 or any(x in JWT_SECRET_KEY.lower() for x in ("change-me", "changeme", "replace-me")) or not 1<=JWT_ACCESS_TOKEN_EXPIRE_MINUTES<=120 or not JWT_ISSUER.strip() or not JWT_AUDIENCE.strip()):
        problems.append("JWT_SECRET_KEY")
    if not CORS_ORIGINS or any("*" in value or not value.startswith(("http://", "https://")) for value in CORS_ORIGINS):
        problems.append("CORS_ORIGINS")
    if APP_ENV == "production" and any(not value.startswith("https://") for value in CORS_ORIGINS):
        problems.append("CORS_ORIGINS HTTPS")
    if not METRICS_TOKEN or len(METRICS_TOKEN) < 32:
        problems.append("METRICS_TOKEN")
    if not DB_USER or not DB_PASSWORD:
        problems.append("SQL credentials")
    if APP_ENV == "production" and (not DB_ENCRYPT or DB_TRUST_SERVER_CERTIFICATE):
        problems.append("SQL TLS certificate validation")
    if APP_ENV == "production" and (len(DB_PASSWORD)<16 or DB_USER.lower()=='sa'):
        problems.append("SQL least-privilege credentials")
    broker = urlsplit(RABBITMQ_URL)
    if "availability-api" not in role and (not broker.username or broker.username == "guest" or not broker.password):
        problems.append("RabbitMQ credentials")
    if APP_ENV == "production":
        cache=urlsplit(REDIS_URL)
        if not cache.password or len(cache.password)<16:problems.append("Redis credentials")
        if "availability-api" not in role and (not broker.password or len(broker.password)<16):problems.append("RabbitMQ password strength")
    if problems:
        raise RuntimeError("Unsafe runtime configuration: " + ", ".join(problems))
