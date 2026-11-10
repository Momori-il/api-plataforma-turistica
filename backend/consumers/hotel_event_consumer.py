import json

from sqlalchemy.exc import IntegrityError

from database.connection import SessionLocal
from messaging.rabbitmq import (
    QUEUE_NAME,
    configurar_canal,
    get_connection,
)
from models.evento_procesado import EventoProcesadoDB


def procesar_evento(ch, method, properties, body):
    db = SessionLocal()

    try:
        evento = json.loads(
            body.decode("utf-8")
        )

        event_id = evento.get("event_id")
        event_type = evento.get("event")
        hotel_id = evento.get("hotel_id")
        timestamp = evento.get("timestamp")

        print("\nEvento recibido")
        print("----------------------------")
        print(f"event_id: {event_id}")
        print(f"event: {event_type}")
        print(f"hotel_id: {hotel_id}")
        print(f"timestamp: {timestamp}")
        print("----------------------------")

        if not event_id:
            print(
                "Evento inválido: no contiene event_id."
            )

            ch.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=False
            )

            return

        evento_existente = (
            db.query(EventoProcesadoDB)
            .filter(
                EventoProcesadoDB.event_id == event_id
            )
            .first()
        )

        if evento_existente:
            print(
                f"Evento {event_id} ya procesado. "
                "Se ignora el duplicado."
            )

            ch.basic_ack(
                delivery_tag=method.delivery_tag
            )

            return

        print(
            f"Procesando HotelDeactivated "
            f"para Hotel {hotel_id}..."
        )

        registro = EventoProcesadoDB(
            event_id=event_id,
            event_type=event_type
        )

        db.add(registro)
        db.commit()

        ch.basic_ack(
            delivery_tag=method.delivery_tag
        )

        print(
            "Evento procesado correctamente "
            "y registrado en SQL Server."
        )

    except IntegrityError:
        db.rollback()

        print(
            "El event_id ya fue registrado. "
            "Se ignora el mensaje duplicado."
        )

        ch.basic_ack(
            delivery_tag=method.delivery_tag
        )

    except json.JSONDecodeError:
        db.rollback()

        print(
            "Mensaje inválido: no contiene JSON válido."
        )

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=False
        )

    except Exception as error:
        db.rollback()

        print(
            f"Error al procesar evento: {error}"
        )

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True
        )

    finally:
        db.close()


def iniciar_consumidor():
    connection = get_connection()
    channel = connection.channel()

    configurar_canal(channel)

    channel.basic_qos(
        prefetch_count=1
    )

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=procesar_evento,
        auto_ack=False
    )

    print("Consumidor iniciado.")
    print(
        f"Esperando mensajes en: {QUEUE_NAME}"
    )
    print(
        "Presioná CTRL+C para detenerlo."
    )

    try:
        channel.start_consuming()

    except KeyboardInterrupt:
        print("\nConsumidor detenido.")

        channel.stop_consuming()

    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    iniciar_consumidor()