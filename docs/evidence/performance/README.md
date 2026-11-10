# AE4 — performance medida (10/11/2026)

Locust 2.47.0 sobre Docker Desktop/WSL2 local. Core y Availability: un proceso por servicio; SQL Server 17 aislado. Cliente en Windows, Intel i5-12450HX, RAM host 7,73GiB, Docker12 CPU lógicas/3,69GiB; límites por servicio en Compose. Pausas de 50–100 ms. Fixture exclusiva, sin escrituras en SQL Windows. No se ejecutaron suites pesadas simultáneamente con las ventanas medidas.

| Escenario | VUs | Requests | Fallos | Media ms | Mediana ms | P95 ms | P99 ms | Máx ms | req/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| availability_miss | 10 | 12785 | 0 | 60.47 | 44.00 | 180 | 240 | 391.69 | 71.39 |
| availability_hit | 10 | 15753 | 0 | 34.11 | 25.00 | 96 | 180 | 319.76 | 88.00 |
| availability_fallback | 10 | 4486 | 0 | 52.94 | 37.00 | 170 | 230 | 355.40 | 75.56 |
| hotels | 10 | 5754 | 0 | 23.83 | 14.00 | 92 | 180 | 337.06 | 97.02 |
| login | 2 | 689 | 0 | 90.27 | 88.00 | 120 | 130 | 266.12 | 11.61 |
| reservation | 5 | 1234 | 2 | 37.65 | 25.00 | 95 | 130 | 188.11 | 42.36 |
| payment | 5 | 1234 | 0 | 37.87 | 34.00 | 69 | 100 | 154.99 | 42.28 |
| stress_25 | 25 | 3566 | 0 | 126.33 | 99.00 | 300 | 390 | 504.71 | 122.35 |
| stress_50 | 50 | 3691 | 0 | 314.17 | 290.00 | 530 | 670 | 816.12 | 126.73 |
| stress_75 | 75 | 3834 | 32 | 486.39 | 460.00 | 800 | 1300 | 1488.19 | 131.68 |
| reservation_create | 1 | 20 | 0 | 52.22 | 51.00 | 84 | 84 | 84.12 | 7.67 |

## Comparación controlada

Mismo hotel, fechas, personas, inventario, 10 VUs, warmup de 30s y ventana de 180s. MISS: TTL=0, Redis accesible pero sin almacenar respuestas. HIT: TTL=10s. El control MISS conserva el costo de leer Redis; no equivale a Redis caído. El tercer escenario mide esa caída por separado.

| Métrica | MISS (TTL=0) | HIT (TTL=10s) | Cambio |
|---|---:|---:|---:|
| Media | 60.47 ms | 34.11 ms | −43.60% |
| P95 | 180 ms | 96 ms | −46.67% |
| Throughput | 71.39 req/s | 88.00 req/s | +23.28% |

Cuello medido: el camino de recálculo de disponibilidad sin cachear realiza consultas/agrupación de reservas en SQL en cada request. La optimización evaluada consiste en activar la caché ya implementada, sin reescribir Macrofase 2. Los contadores prueban 0 HIT / 12.818 MISS en el control y 15.757 HIT / 46 MISS con TTL=10. Elegibilidad pública sigue leyendo SQL; nunca se reserva usando stock de caché. La atribución al camino de recálculo combina inspección de código y experimento; no se midió un plan SQL ni espera física por consulta.

## Errores y límite de capacidad

- 2/1234 respuestas 503 en replay de reservas con 5 VUs; se conservan como backpressure observado. La API permite 503 + Retry-After bajo contención, con repetición de la misma clave. No hubo doble reserva. No se transformaron errores en 2xx para limpiar cifras.
- 32/3834 respuestas 503 en estrés de 75 VUs (0,835%); P95 800ms. Es una prueba de saturación, no el punto operativo recomendado.
- 25 VUs: 0 fallos, P95 300ms; 50 VUs: 0 fallos pero P95 530ms y throughput casi estancado. El objetivo inicial de GET P95<=500ms ya no se cumple a 50 VUs en esta PC. Pools/servicios únicos y límites del host son candidatos a perfilar; no se atribuye a un componente físico sin más evidencia.
- Altas nuevas controladas: 20 requests, 20 respuestas 201, 20 filas nuevas, cero sobreventa. Media/P95 de la tabla proceden de JSON final de Locust. Se repitió una tanda de veinte al corregir la captura del último intervalo CSV; ambas se limpiaron.
- Login/pago: cuotas elevadas solo en override temporal de integración para medir el servicio, limitador siempre activo; defaults restaurados y 429 real validado aparte. No es un benchmark de brute force.

## Reproducción y límites

Preparar fixture con `python -m scripts.qa_prepare --real`, autenticar/auditar con `scripts.qa_browser`, ejecutar `python -m scripts.qa_load --real` y luego `scripts.qa_fresh_load --real`. Ver README raíz. No correr carga y fallos simultáneamente. `qa_cleanup --real` retira únicamente esa fixture después de entregar eventos.

CSV originales: snapshots periódicos; el último intervalo/in-flight puede quedar fuera del CSV. Los números de cada fila reflejan esa muestra, no una cuenta exhaustiva del tráfico. Percentiles de Locust están agrupados en buckets. El runner actualizado guarda además estadísticas finales al shutdown; el perfil acotado usa ese JSON (20 completadas). Contadores de servidor pueden incluir requests fuera de la última muestra CSV.

Una ejecución por perfil, sin intervalos de confianza ni garantía productiva. Los perfiles normales principales tuvieron cero fallos; se publican también todos los resultados de contención/estrés. Las comparaciones son locales, con carga de lazo cerrado y think time; req/s no es capacidad máxima sin pausas. Sin HA/P95 productivo/deploy remoto. Fuente estructurada: [summary.json](summary.json).
