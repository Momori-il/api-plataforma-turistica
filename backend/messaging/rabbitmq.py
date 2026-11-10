import json

import pika
import config


EXCHANGE_NAME = "turismo.events"
QUEUE_NAME = "hotel.deactivated"
ROUTING_KEY = "hotel.deactivated"


def get_connection():
    if not config.RABBITMQ_URL:
        raise RuntimeError("RABBITMQ_URL is not configured")
    parameters = pika.URLParameters(config.RABBITMQ_URL)
    parameters.socket_timeout = config.RABBITMQ_SOCKET_TIMEOUT
    parameters.stack_timeout = config.RABBITMQ_STACK_TIMEOUT
    parameters.blocked_connection_timeout = config.RABBITMQ_BLOCKED_TIMEOUT
    parameters.heartbeat = config.RABBITMQ_HEARTBEAT
    parameters.connection_attempts = 1
    return pika.BlockingConnection(parameters)


def configurar_canal(channel):
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type="topic",
        durable=True
    )

    channel.queue_declare(
        queue=QUEUE_NAME,
        durable=True
    )

    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=QUEUE_NAME,
        routing_key=ROUTING_KEY
    )
    from messaging.worker import declare_queues
    declare_queues(channel)


def publicar_evento(evento: dict):
    connection = get_connection()

    try:
        channel = connection.channel()

        configurar_canal(channel)

        mensaje = json.dumps(
            evento,
            ensure_ascii=False
        )

        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=ROUTING_KEY,
            body=mensaje,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2
            )
        )

        print(
            f"Evento publicado: {evento['event']}"
        )

    finally:
        if connection.is_open:
            connection.close()
