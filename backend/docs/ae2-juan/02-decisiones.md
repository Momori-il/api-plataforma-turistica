# Decisiones técnicas - AE2

## 1. Definición de Viaje

Se definió Viaje como una planificación turística y no como un traslado o medio de transporte.

El Viaje posee:

- nombre;
- fecha de inicio;
- fecha de finalización;
- estado.

Estados definidos inicialmente:

- PLANIFICADO;
- EN_CURSO;
- FINALIZADO;
- CANCELADO.

---

## 2. Relación entre Hotel y Viaje

Se analizaron dos alternativas.

### Alternativa A — Un único Hotel por Viaje

Cada Viaje tendría una referencia directa a un Hotel.

Ventajas:

- menor complejidad;
- menos tablas;
- consultas sencillas.

Limitación:

- no permite representar un Viaje con diferentes alojamientos durante distintos períodos.

### Alternativa B — Varios Hoteles por Viaje

Un Viaje puede contener diferentes Hoteles y un Hotel puede aparecer en distintos Viajes.

Para resolver esta relación se utiliza ViajeHotel.

### Decisión adoptada

Se seleccionó la alternativa B.

La decisión permite representar, por ejemplo:

- Hotel A: 10/10 al 14/10.
- Hotel B: 14/10 al 20/10.

dentro de un único Viaje.

La entidad ViajeHotel almacena los atributos propios de cada estadía.

---

## 3. Tratamiento de superposiciones

Se decidió que dos estadías activas dentro de un mismo Viaje no pueden superponerse temporalmente.

Se permite:

Hotel A: 10/10 al 14/10  
Hotel B: 14/10 al 20/10

No se permite:

Hotel A: 10/10 al 17/10  
Hotel B: 14/10 al 20/10

Una superposición genera una respuesta HTTP 409 Conflict.

---

## 4. Baja lógica de Hoteles

En AE1 la eliminación utilizaba borrado físico.

Se analizaron dos alternativas:

### Alternativa A — Mantener DELETE físico

El registro desaparece definitivamente de la base de datos.

### Alternativa B — Utilizar estados

El registro permanece almacenado pero cambia de ACTIVO a INACTIVO.

### Decisión adoptada

Se seleccionó la baja lógica.

Esto permite conservar el historial de información y evitar que registros previamente utilizados desaparezcan de SQL Server.

Las consultas públicas muestran únicamente Hoteles con estado ACTIVO.