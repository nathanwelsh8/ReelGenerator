from fastapi import APIRouter
import os
from typing import Any, Dict
try:
    import pika  # type: ignore
except Exception:  # pragma: no cover
    pika = None  # fallback if not installed
from services.messaging.messages import TOPIC_HIGGS_AUDIO_JOBS
from settings import get_settings
from urllib.parse import urlparse, unquote

router = APIRouter()


@router.get("/", summary="Health check")
def health() -> Dict[str, Any]:
    settings = get_settings()
    backend = settings.MESSAGING_BACKEND.lower()
    queue_ok = None
    reason = None
    broker = None
    vhost = None
    if backend == "rabbitmq":
        if pika is None:
            queue_ok = False
            reason = "pika not installed"
        else:
            url = settings.RABBITMQ_URL
            try:
                p = urlparse(url)
                broker = p.hostname
                vhost = unquote(p.path or '/').lstrip('/') or '/'
                port = p.port or 5672
            except Exception:
                broker = None
                port = None
            try:
                params = pika.URLParameters(url)
                conn = pika.BlockingConnection(params)
                ch = conn.channel()
                # Passive declare to check existence without creating; if it doesn't exist, this raises
                try:
                    q = ch.queue_declare(queue=TOPIC_HIGGS_AUDIO_JOBS, passive=True)
                    queue_ok = True
                    message_count = getattr(q.method, 'message_count', None)
                    consumer_count = getattr(q.method, 'consumer_count', None)
                except Exception as e:
                    # Queue not present or other channel error; consider broker reachable but queue missing
                    queue_ok = False
                    reason = f"queue check failed: {type(e).__name__}"
                finally:
                    try:
                        ch.close()
                    except Exception:
                        pass
                    try:
                        conn.close()
                    except Exception:
                        pass
            except Exception as e:
                queue_ok = False
                reason = f"broker unreachable: {type(e).__name__}"
    return {
        "app": "ok",
        "queue": {
            "backend": backend,
            "available": queue_ok,
            "topic": TOPIC_HIGGS_AUDIO_JOBS,
            "message_count": locals().get("message_count"),
            "consumer_count": locals().get("consumer_count"),
            "reason": reason,
        },
    }

