from models.hotel import HotelDB


def crear_hotel(client, nombre="Hotel Test"):
    response = client.post(
        "/api/v1/hoteles/",
        json={
            "nombre": nombre,
            "zona_id": 1,
            "precio_base": 50000,
            "descripcion": "Hotel creado para pruebas",
            "direccion": "Posadas, Misiones",
            "categoria": 4,
            "calificacion": 8.5,
            "servicio": "WiFi"
        }
    )

    assert response.status_code == 201
    approval = client.patch(
        f"/api/v1/hoteles/{response.json()['id']}/aprobacion",
        json={"aprobacion": "APROBADA"}, headers=client.admin_headers,
    )
    assert approval.status_code == 200

    return response.json()


def test_crear_y_obtener_hotel(client):
    hotel = crear_hotel(client)

    response = client.get(
        f"/api/v1/hoteles/{hotel['id']}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == hotel["id"]
    assert data["nombre"] == "Hotel Test"
    assert data["estado"] == "ACTIVO"


def test_listar_hoteles_activos(client):
    crear_hotel(client, "Hotel Uno")
    crear_hotel(client, "Hotel Dos")

    response = client.get("/api/v1/hoteles/")

    assert response.status_code == 200

    hoteles = response.json()

    assert len(hoteles) == 2


def test_baja_logica_hotel(client, db_session):
    hotel = crear_hotel(client)

    hotel_id = hotel["id"]

    response = client.patch(
        f"/api/v1/hoteles/{hotel_id}/estado",
        json={
            "estado": "INACTIVO"
        }
    )

    assert response.status_code == 200
    assert response.json()["estado"] == "INACTIVO"

    # Ya no debe aparecer mediante la API pública
    response_get = client.get(
        f"/api/v1/hoteles/{hotel_id}"
    )

    assert response_get.status_code == 404

    # Pero el registro debe seguir físicamente en la DB
    hotel_db = (
        db_session.query(HotelDB)
        .filter(HotelDB.id == hotel_id)
        .first()
    )

    assert hotel_db is not None
    assert hotel_db.estado == "INACTIVO"


def test_estado_invalido_hotel(client):
    hotel = crear_hotel(client)

    response = client.patch(
        f"/api/v1/hoteles/{hotel['id']}/estado",
        json={
            "estado": "BORRADO"
        }
    )

    assert response.status_code == 400


def test_hotel_inexistente_devuelve_404(client):
    response = client.get(
        "/api/v1/hoteles/99999"
    )

    assert response.status_code == 404


def test_delete_fisico_no_esta_disponible(client):
    hotel = crear_hotel(client)

    response = client.delete(
        f"/api/v1/hoteles/{hotel['id']}"
    )

    assert response.status_code == 405
