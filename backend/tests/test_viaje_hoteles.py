def crear_hotel(client, nombre):
    response = client.post(
        "/api/v1/hoteles/",
        json={
            "nombre": nombre,
            "zona_id": 1,
            "precio_base": 50000,
            "descripcion": "Hotel para test",
            "direccion": "Posadas",
            "categoria": 4,
            "calificacion": 8.0,
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


def crear_viaje(client):
    response = client.post(
        "/api/v2/viajes/",
        headers=client.admin_headers,
        json={
            "nombre": "Viaje a Posadas",
            "fecha_inicio": "2026-10-10",
            "fecha_fin": "2026-10-20"
        }
    )

    assert response.status_code == 201

    return response.json()


def test_asociar_hotel_a_viaje(client):
    viaje = crear_viaje(client)
    hotel = crear_hotel(client, "Hotel Uno")

    response = client.post(
        f"/api/v2/viajes/{viaje['id']}/hoteles",
        headers=client.admin_headers,
        json={
            "hotel_id": hotel["id"],
            "fecha_desde": "2026-10-10",
            "fecha_hasta": "2026-10-14"
        }
    )

    assert response.status_code == 201

    estadia = response.json()

    assert estadia["viaje_id"] == viaje["id"]
    assert estadia["hotel_id"] == hotel["id"]
    assert estadia["estado"] == "ACTIVO"


def test_estadias_contiguas_estan_permitidas(client):
    viaje = crear_viaje(client)

    hotel_1 = crear_hotel(
        client,
        "Hotel Uno"
    )

    hotel_2 = crear_hotel(
        client,
        "Hotel Dos"
    )

    response_1 = client.post(
        f"/api/v2/viajes/{viaje['id']}/hoteles",
        headers=client.admin_headers,
        json={
            "hotel_id": hotel_1["id"],
            "fecha_desde": "2026-10-10",
            "fecha_hasta": "2026-10-14"
        }
    )

    assert response_1.status_code == 201

    # La segunda estadía empieza exactamente
    # cuando termina la primera.
    response_2 = client.post(
        f"/api/v2/viajes/{viaje['id']}/hoteles",
        headers=client.admin_headers,
        json={
            "hotel_id": hotel_2["id"],
            "fecha_desde": "2026-10-14",
            "fecha_hasta": "2026-10-20"
        }
    )

    assert response_2.status_code == 201


def test_superposicion_de_estadias_devuelve_409(client):
    viaje = crear_viaje(client)

    hotel_1 = crear_hotel(
        client,
        "Hotel Uno"
    )

    hotel_2 = crear_hotel(
        client,
        "Hotel Dos"
    )

    response_1 = client.post(
        f"/api/v2/viajes/{viaje['id']}/hoteles",
        headers=client.admin_headers,
        json={
            "hotel_id": hotel_1["id"],
            "fecha_desde": "2026-10-10",
            "fecha_hasta": "2026-10-14"
        }
    )

    assert response_1.status_code == 201

    response_2 = client.post(
        f"/api/v2/viajes/{viaje['id']}/hoteles",
        headers=client.admin_headers,
        json={
            "hotel_id": hotel_2["id"],
            "fecha_desde": "2026-10-12",
            "fecha_hasta": "2026-10-18"
        }
    )

    assert response_2.status_code == 409


def test_estadia_fuera_del_periodo_del_viaje(client):
    viaje = crear_viaje(client)
    hotel = crear_hotel(
        client,
        "Hotel Fuera Periodo"
    )

    response = client.post(
        f"/api/v2/viajes/{viaje['id']}/hoteles",
        headers=client.admin_headers,
        json={
            "hotel_id": hotel["id"],
            "fecha_desde": "2026-10-05",
            "fecha_hasta": "2026-10-12"
        }
    )

    assert response.status_code == 400


def test_hotel_inexistente_no_se_puede_asociar(client):
    viaje = crear_viaje(client)

    response = client.post(
        f"/api/v2/viajes/{viaje['id']}/hoteles",
        headers=client.admin_headers,
        json={
            "hotel_id": 99999,
            "fecha_desde": "2026-10-10",
            "fecha_hasta": "2026-10-14"
        }
    )

    assert response.status_code == 404


def test_hotel_inactivo_no_se_puede_asociar(client):
    viaje = crear_viaje(client)

    hotel = crear_hotel(
        client,
        "Hotel Inactivo"
    )

    response_estado = client.patch(
        f"/api/v1/hoteles/{hotel['id']}/estado",
        json={
            "estado": "INACTIVO"
        }
    )

    assert response_estado.status_code == 200

    response = client.post(
        f"/api/v2/viajes/{viaje['id']}/hoteles",
        headers=client.admin_headers,
        json={
            "hotel_id": hotel["id"],
            "fecha_desde": "2026-10-10",
            "fecha_hasta": "2026-10-14"
        }
    )

    assert response.status_code == 404


def test_viaje_inexistente_no_admite_hoteles(client):
    hotel = crear_hotel(
        client,
        "Hotel Test"
    )

    response = client.post(
        "/api/v2/viajes/99999/hoteles",
        headers=client.admin_headers,
        json={
            "hotel_id": hotel["id"],
            "fecha_desde": "2026-10-10",
            "fecha_hasta": "2026-10-14"
        }
    )

    assert response.status_code == 404
