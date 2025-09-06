from typing import Mapping, Any, Optional
from .publisher import Publisher, NoopPublisher
from settings import get_settings
from logging import getLogger

logger = getLogger(__name__)

class SafePublisher:
    """Wraps a concrete publisher and falls back to Noop on runtime failures."""
    def __init__(self, inner: Publisher):
        self._inner = inner
        self._fallback = NoopPublisher()

    def publish(self, topic: str, message: Mapping[str, Any], *, key: Optional[str] = None, headers: Optional[Mapping[str, str]] = None) -> None:
        try:
            self._inner.publish(topic, message, key=key, headers=headers)
        except Exception as e:
            logger.warning(f"[Messaging] Publish failed, falling back to NOOP: {e}")
            self._fallback.publish(topic, message, key=key, headers=headers)


def get_publisher() -> Publisher:
    backend = get_settings().MESSAGING_BACKEND.lower()
    if backend == "rabbitmq":
        try:
            from .rabbitmq_publisher import RabbitMQPublisher
            return SafePublisher(RabbitMQPublisher())
        except Exception as e:
            # Fallback to NOOP if broker/client not available
            logger.warning(f"[Messaging] RabbitMQ unavailable, falling back to NoopPublisher: {e}")
            return NoopPublisher()
    # Default fallback
    return NoopPublisher()
