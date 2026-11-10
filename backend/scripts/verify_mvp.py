"""Recorrido HTTP del MVP sobre recursos demo, sin Swagger ni SQL manual."""

import argparse
from uuid import uuid4

import httpx

from config import BASE_DIR
from scripts.demo_support import DemoError, login, read_manifest, request


def ensure(condition, message):
    if not condition:
        raise DemoError(message)


def run_flow(client, manifest):
    resource = manifest["resources"]
    logins = {role: login(client, data) for role, data in manifest["accounts"].items()}
    tourist, tourist_user = logins["turista"]
    provider, _ = logins["prestador"]
    admin, _ = logins["admin"]
    request(client, "GET", "/health")
    request(client, "GET", "/openapi.json")
    room_path = f"/api/v1/hoteles/{resource['hotel_id']}/habitaciones/{resource['habitacion_id']}/disponibilidad"
    turn_path = f"/api/v1/actividades/{resource['actividad_id']}/turnos/{resource['turno_id']}"
    dates = {key: resource[key] for key in ("fecha_desde", "fecha_hasta")}
    hotel_body = dict(hotel_id=resource["hotel_id"], habitacion_id=resource["habitacion_id"], **dates, personas=2, cantidad_habitaciones=1)
    activity_body = dict(actividad_id=resource["actividad_id"], turno_id=resource["turno_id"], personas=2)
    room_before = request(client, "GET", room_path, params={**dates, "personas": 2, "cantidad_habitaciones": 1})
    turn_before = request(client, "GET", turn_path, params={"personas": 2})
    ensure(room_before["disponible"] and turn_before["disponible"], "El catálogo demo no tiene disponibilidad suficiente; revisar sus reservas existentes")
    request(client, "GET", "/api/v1/gestion/reservas", expected=401)
    request(client, "GET", "/api/v1/gestion/reservas", expected=403, headers=tourist)
    request(client, "GET", "/api/v1/admin/usuarios", expected=403, headers=provider)
    created, cancelled, payments = [], set(), []
    try:
        hotel = request(client, "POST", "/api/v1/reservas/hotel", expected=201, json=hotel_body, headers=tourist)
        created.append(hotel["id"])
        ensure(hotel["estado"] == "PENDIENTE_PAGO", "La reserva no comenzó pendiente")
        ensure(hotel["turista_id"] == tourist_user["id"], "La reserva no pertenece al turista autenticado")
        request(client, "POST", "/api/v1/reservas/hotel", expected=409, json={**hotel_body, "cantidad_habitaciones": room_before["habitaciones_disponibles"]}, headers=tourist)
        payment_path = f"/api/v1/reservas/{hotel['id']}/pagos/simular"
        request(client, "POST", payment_path, expected=403, headers=provider, json={"clave_idempotencia": str(uuid4()), "resultado": "APROBADO"})
        reject = {"clave_idempotencia": str(uuid4()), "resultado": "RECHAZADO"}
        rejected = request(client, "POST", payment_path, expected=201, headers=tourist, json=reject)
        payments.append(rejected["pago"]["id"])
        ensure(rejected["reserva"]["estado"] == "PENDIENTE_PAGO", "Un pago rechazado confirmó la reserva")
        repeat = request(client, "POST", payment_path, headers=tourist, json=reject)
        ensure(repeat["pago"] == rejected["pago"], "El reintento rechazado se duplicó")
        approve = {"clave_idempotencia": str(uuid4()), "resultado": "APROBADO"}
        approved = request(client, "POST", payment_path, expected=201, headers=tourist, json=approve)
        payments.append(approved["pago"]["id"])
        ensure(approved["reserva"]["estado"] == "CONFIRMADA", "El pago aprobado no confirmó la reserva")
        ensure(approved["pago"]["importe"] == hotel["total"], "El pago no conservó el importe de reserva")
        repeat = request(client, "POST", payment_path, headers=tourist, json=approve)
        ensure(repeat["pago"] == approved["pago"], "El reintento aprobado se duplicó")
        history = request(client, "GET", f"/api/v1/reservas/{hotel['id']}/pagos", headers=tourist)
        ensure(history["total"] == 2, "El historial de pagos no conserva los dos intentos")
        admin_history = request(client, "GET", f"/api/v1/gestion/reservas/{hotel['id']}/pagos", headers=admin)
        ensure(admin_history["items"] == history["items"], "ADMIN y turista no consultaron los mismos pagos")

        activity = request(client, "POST", "/api/v1/reservas/actividad", expected=201, headers=tourist, json=activity_body)
        created.append(activity["id"])
        request(client, "POST", "/api/v1/reservas/actividad", expected=409, headers=tourist, json={**activity_body, "personas": turn_before["cupos_disponibles"]})
        activity_payment = request(client, "POST", f"/api/v1/reservas/{activity['id']}/pagos/simular", expected=201, headers=tourist, json={"clave_idempotencia": str(uuid4()), "resultado": "APROBADO"})
        payments.append(activity_payment["pago"]["id"])
        ensure(activity_payment["reserva"]["estado"] == "CONFIRMADA", "La actividad no quedó confirmada")
        for reservation in (hotel, activity):
            booking_id = reservation["id"]
            own = request(client, "GET", f"/api/v1/reservas/{booking_id}", headers=tourist)
            received = request(client, "GET", f"/api/v1/gestion/reservas/{booking_id}", headers=provider)
            ensure(own["estado"] == received["estado"] == "CONFIRMADA", "La reserva no está visible en ambos roles")
            ensure(received["turista"]["id"] == tourist_user["id"], "Contacto incorrecto en la reserva recibida")
            cancel_path = f"/api/v1/reservas/{booking_id}/cancelar"
            cancellation = request(client, "PATCH", cancel_path, headers=tourist)
            ensure(cancellation["estado"] == "CANCELADA", "La cancelación no se persistió")
            cancelled.add(booking_id)
            ensure(request(client, "PATCH", cancel_path, headers=tourist) == cancellation, "La cancelación repetida cambió su resultado")
        room_after = request(client, "GET", room_path, params={**dates, "personas": 2, "cantidad_habitaciones": 1})
        turn_after = request(client, "GET", turn_path, params={"personas": 2})
        ensure(room_after["habitaciones_disponibles"] == room_before["habitaciones_disponibles"], "La cancelación no liberó habitaciones")
        ensure(turn_after["cupos_disponibles"] == turn_before["cupos_disponibles"], "La cancelación no liberó cupos")
        return {"reservas": created, "pagos": payments, "estado_final": "CANCELADA", "roles": ["TURISTA", "PRESTADOR", "ADMIN"], "resultado": "OK"}
    finally:
        # Si falla un paso, intenta liberar solamente las reservas creadas aquí.
        for booking_id in created:
            if booking_id not in cancelled:
                try:
                    client.patch(f"/api/v1/reservas/{booking_id}/cancelar", headers=tourist)
                except httpx.HTTPError:
                    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--manifest", default=str(BASE_DIR / ".demo" / "manifest.json"))
    args = parser.parse_args()
    try:
        manifest = read_manifest(args.manifest)
        with httpx.Client(base_url=args.base_url, timeout=30, trust_env=False) as client:
            request(client, "GET", "/health/db")
            report = run_flow(client, manifest)
    except (DemoError, httpx.HTTPError, KeyError) as error:
        print(str(error) if isinstance(error, DemoError) else "No se completó el recorrido. Revisar API, manifiesto y conexión; no se muestran credenciales.")
        return 1
    print(f"OK: HTTP -> API -> SQL Server; reservas {report['reservas']}, pagos {report['pagos']}, estado final CANCELADA.")
    print("Verificados login de tres roles, disponibilidad, rechazo/aprobación, idempotencia, paneles y liberación de inventario.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
