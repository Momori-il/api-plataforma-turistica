# AE4 — índice técnico de Macrofase 4

Fecha: 10/11/2026. Fuente de estado y archivos exactos: [AE4_VALIDATION.json](AE4_VALIDATION.json), sección `macro4`. No se inició Macrofase 5.

| Área | Evidencia | Resultado |
|---|---|---|
| Suites | [Resumen](evidence/tests/summary.json) | Frontend138/0/0; backend Windows/Linux643/0/15; SQL opt-in1245/0/0 |
| Deuda frontend | [28 clasificados](evidence/tests/frontend-debt.json) | No se eliminaron tests ni se cambió funcionalidad válida para satisfacer mocks antiguos |
| Sistema / roles / seguridad | [HTTP real](evidence/system/http.json) | 33 checks,5 carreras,12 controles de seguridad |
| Navegador | [Flujos Chromium](evidence/system/browser-flows.json) | Hotel y actividad, pago/confirmación/cancelación, XSS DOM escapado, sin errores HTTP/JS |
| Distribución | [SQL/Redis/RabbitMQ](evidence/integration/distributed.json) | 23 checks, confirms/Inbox/idempotencia/retry/DLQ reales; base SQL y colas exclusivas |
| Resiliencia / métricas / trazas | [Fallos Compose](evidence/resilience/faults.json) | 18 checks: Availability/Redis/broker/worker/SQL caídos y recuperados; trace_id/correlation_id entre procesos |
| Performance | [Análisis](evidence/performance/README.md), [JSON](evidence/performance/summary.json), CSV adyacentes | Media/P95/throughput, comparación real, fallos de contención y saturación conservados |
| Accesibilidad / responsive | [Axe y anchos](evidence/accessibility/browser.json), [correcciones](evidence/accessibility/fixes.json), [teclado](evidence/accessibility/keyboard.json) | 25 páginas,125 anchos,30 estados adicionales de flujo real, sin infracciones detectadas/desbordes tras correcciones |
| OpenAPI | [Contrato capturado](evidence/openapi/openapi.json) | 51 paths/61 operaciones; JWT, schemas, tags, errores y header de idempotencia revisados |
| Diagramas | [Mermaid](AE4_DIAGRAMS.md) | Arquitectura, flujo reserva, propiedad de datos, secuencia HIT/MISS/fallback |
| Reproducción | [README raíz](../README.md) | Requisitos, entorno, datos, migraciones, ejecución y pruebas |
| SQL / limpieza | [Cleanup QA](evidence/system/cleanup.json), [preservación final](evidence/system/final.json) | Hashes originales/restaurados, DBCC, estado final y secretos no modificados |
| Docker | [Compose](../compose.yml), [validación final](AE4_VALIDATION.json) | Diez servicios healthy; sql-init termina0; solo loopback5500/8000 |

## Ejecutar suites sin escribir en la demo

Desde `backend`, con Docker Desktop/Compose sano:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m scripts.qa_backend --real
.venv/Scripts/python.exe -m scripts.qa_backend --real --sqlserver
cd ../frontend
npm test
```

`qa_backend --sqlserver` configura una base generada `TurismoPosadas_Test_<uuid>` incluso para los tests que normalmente consultan el engine configurado. Fixtures adicionales crean otras bases de prueba con el mismo guard y las eliminan al terminar. Los 15 skips aislados son 4 carreras de stock/inventario y 11 de pago/cancelación; se ejecutaron en el perfil SQL. El total1245 incluye variantes SQLite y SQL, no1245 casos exclusivamente SQL.

## Ejecutar integración y carga

Herramientas opcionales y comandos en README. Orden: `qa_prepare --real` -> `qa_browser --real` -> `qa_load --real` -> `qa_fresh_load --real` -> `qa_ui_flow --real` -> `qa_system --real` -> `qa_cleanup --real`. Usar `.demo/qa/Scripts/python.exe` para programas Playwright; `.venv/Scripts/python.exe` para operadores y HTTP/SQL. No ejecutar perfiles a la vez. Los JWT/pending bookings vencen: si una interrupción es larga, limpiar la fixture antes de preparar otra. No publicar `.demo/macro4-run.json`.

La evidencia final de 23 checks usa `scripts.validate_ae4.run()` dentro de una tarea Compose con `DB_USER=sa`, secreto admin montado de solo lectura, tests montados y `AVAILABILITY_URL` vacía para que los GET lean su SQL temporal. Usa exchanges/colas propios y elimina únicamente sus recursos; no invocar su `main` para sobrescribir evidencia histórica sin intención. La regresión de sistema sí usa Core -> Availability real.

Con la fixture ya retirada:

```powershell
cd backend
.venv/Scripts/python.exe -m scripts.validate_macro3 --real --evidence-section macro4
.demo/qa/Scripts/python.exe -m scripts.qa_keyboard
```

El primer comando detiene/recupera dependencias locales, crea dos reservas temporales en la copia, comprueba entrega/trazas y limpia. Conserva evidencia histórica Macro3. No ejecutarlo durante carga, una demo o trabajo concurrente de otro usuario.

## Lectura de resultados

No sumar cifras de suites Windows/Linux/SQL como casos únicos. No ocultar skips, los34 HTTP503 de perfiles de contención/estrés, el warning histórico Starlette/httpx ni la precisión por buckets/intervalos de Locust. Axe no equivale a certificación WCAG manual ni estas pruebas a un pentest/HA productivo. Límites específicos y punto operativo medido en el resumen de performance. Sin GitHub, CI/CD, registry ni despliegue en esta fase.
