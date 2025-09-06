from __future__ import annotations
from typing import Mapping, Any, Optional
import json
import pika
from settings import get_settings
from logging import getLogger

logger = getLogger(__name__)


class RabbitMQPublisher:
    def __init__(self, url: Optional[str] = None, exchange: str = "", durable_queue: bool = True):
        # Default URL uses central settings; can be overridden via parameter
        self.url = url or get_settings().RABBITMQ_URL
        self.exchange = exchange
        self.durable_queue = durable_queue
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None

    def _ensure_channel(self):
        if self._connection and self._channel and self._channel.is_open:
            return
        params = pika.URLParameters(self.url)
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()

    def publish(self, topic: str, message: Mapping[str, Any], *, key: Optional[str] = None, headers: Optional[Mapping[str, str]] = None) -> None:
        self._ensure_channel()
        assert self._channel is not None
        # Declare queue for simple default exchange usage
        self._channel.queue_declare(queue=topic, durable=self.durable_queue)
        body = json.dumps(message, ensure_ascii=False).encode("utf-8")
        props = pika.BasicProperties(
            delivery_mode=2 if self.durable_queue else 1,  # 2 makes message persistent
            headers={**(headers or {}), **({"message_key": key} if key else {})},
            content_type="application/json",
            message_id=key,
        )
        # IMPORTANT: Use the queue/topic name as routing key for default exchange routing
        routing_key = topic
        self._channel.basic_publish(
            exchange=self.exchange,
            routing_key=routing_key,
            body=body,
            properties=props,
        )
        logger.info(f"Published to {topic} rk={routing_key} msg_key={key}")

    def close(self):
        try:
            if self._channel and self._channel.is_open:
                self._channel.close()
                logger.info(f"Closed channel for {self._channel}")
        finally:
            if self._connection and self._connection.is_open:
                self._connection.close()
                logger.info(f"Closed connection for {self._connection}")
