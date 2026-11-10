POSADASTURISMO - FLUJO DE RESERVA DEMOSTRATIVO

1. index.html
   - Las tarjetas de hotel son clickeables.
   - El botón Reservar lleva a hotel.html?id=ID#reservar.
   - Las fechas y cantidad de adultos del buscador se conservan para el detalle.

2. hotel.html
   - Vista específica del alojamiento.
   - Galería, descripción, zona, recomendaciones de seguridad, movilidad, entorno y servicios.
   - Formulario de estadía: entrada, salida, adultos, niños y habitaciones.
   - Calcula noches y total estimado.

3. Cuenta obligatoria
   - Si el usuario intenta reservar sin sesión, se redirige a login.html.
   - Desde login puede ir a registro-usuario.html.
   - Las cuentas se almacenan localmente para demostración mediante localStorage.
   - No usar contraseñas reales: no reemplaza autenticación de backend.

4. Checkout simulado
   - Con sesión iniciada, Reservar ahora abre el modal de pago.
   - El pago espera 2 segundos y confirma la reserva sin transacción real.
   - Los datos de tarjeta no se guardan.
   - Sólo se almacena localmente la información no sensible de la reserva simulada.

5. Próximo paso recomendado
   - Reemplazar la autenticación local por FastAPI + SQL Server + hash seguro + JWT/sesión.
   - Persistir reservas reales en tablas Usuario y Reserva.
