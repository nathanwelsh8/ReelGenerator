from __future__ import annotations
from typing import Protocol, Mapping, Any, Optional
import json
from logging import getLogger

logger = getLogger(__name__)

class Publisher(Protocol):
    def publish(self, topic: str, message: Mapping[str, Any], *, key: Optional[str] = None, headers: Optional[Mapping[str, str]] = None) -> None:
        """Publish a message to a given topic/queue.

        - topic: routing key / queue name
        - message: JSON-serializable dict
        - key: optional routing key/partition key
        - headers: optional string headers
        """
        ...


class NoopPublisher:
    """Fallback publisher that logs to stdout; useful in dev when broker isn't running."""
    def publish(self, topic: str, message: Mapping[str, Any], *, key: Optional[str] = None, headers: Optional[Mapping[str, str]] = None) -> None:  # type: ignore[override]
        payload = json.dumps(message, ensure_ascii=False)
        logger.info(f"[NOOP PUBLISH] topic={topic} key={key} headers={headers} payload={payload}")
