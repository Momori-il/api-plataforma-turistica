def crear_viaje(client, nombre="Viaje Test"):
    response = client.post(
        "/api/v2/viajes/",
        headers=client.admin_headers,
        json={
            "nombre": nombre,
            "fecha_inicio": "2026-10-10",
            "fecha_fin": "2026-10-20"
        }
    )

    assert response.status_code == 201

    return response.json()


def test_crear_viaje(client):
    viaje = crear_viaje(client)

    assert viaje["nombre"] == "Viaje Test"
    assert viaje["estado"] == "PLANIFICADO"
    assert viaje["fecha_inicio"] == "2026-10-10"
    assert viaje["fecha_fin"] == "2026-10-20"


def test_obtener_viaje(client):
    viaje = crear_viaje(client)

    response = client.get(
        f"/api/v2/viajes/{viaje['id']}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == viaje["id"]
    assert data["nombre"] == "Viaje Test"


def test_listar_viajes(client):
    crear_viaje(client, "Viaje Uno")
    crear_viaje(client, "Viaje Dos")

    response = client.get("/api/v2/viajes/")

    assert response.status_code == 200

    viajes = response.json()

    assert len(viajes) == 2


def test_viaje_con_fechas_invalidas(client):
    response = client.post(
        "/api/v2/viajes/",
        headers=client.admin_headers,
        json={
            "nombre": "Viaje inválido",
            "fecha_inicio": "2026-10-20",
            "fecha_fin": "2026-10-10"
        }
    )

    # Contrato de errores real de la aplicación (AE1/AE2).
    assert response.status_code == 400


def test_viaje_inexistente_devuelve_404(client):
    response = client.get(
        "/api/v2/viajes/99999"
    )

    assert response.status_code == 404
