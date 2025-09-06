import os
import sys
import json
import pika
from typing import Any

"""Video worker: consumes video jobs and generates the final video when assets are ready."""

# Ensure project root is importable when running this file directly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from db_handler import DBOperation
from services.video_service import generate_video_if_ready
from services.messaging.messages import TOPIC_VIDEO_JOBS
from settings import get_settings
from logging import getLogger
from services.config.logging_config import configure_logging
from utils import DialougeStatus


def main():
    settings = get_settings()
    url = settings.RABBITMQ_URL

    db = DBOperation()

    def _parse_message(body: bytes) -> dict:
        return json.loads(body.decode("utf-8"))

    def _ack(ch_, method):
        ch_.basic_ack(delivery_tag=method.delivery_tag)

    def _nack_requeue(ch_, method):
        ch_.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _process(msg: dict):
        project_id = msg.get("project_id")
        if not project_id:
            raise ValueError("video job missing project_id")
        logger.info(f"Processing video job for project_id={project_id}")

        # Try to generate video if assets ready; if not, we'll requeue for later
        result = generate_video_if_ready(db, int(project_id))
        if result:
            logger.info(f"Video generated: {result}")
            return True
        # Not ready yet; requeue so it can be tried again later
        return False

    def handle(ch_, method, properties, body: bytes):
        try:
            msg = _parse_message(body)
            ok = _process(msg)
            if ok:
                _ack(ch_, method)
            else:
                _nack_requeue(ch_, method)
        except Exception as e:
            logger.warning(f"Video job failed: {type(e).__name__}: {e}")
            try:
                _nack_requeue(ch_, method)
            except Exception:
                pass

    # --- Connection helpers ---
    def _build_params(url: str) -> pika.URLParameters:
        p = pika.URLParameters(url)
        p.heartbeat = 30
        p.socket_timeout = 15
        try:
            p.connection_attempts = max(1, getattr(p, 'connection_attempts', 1))
            p.retry_delay = max(1, getattr(p, 'retry_delay', 5))
            p.blocked_connection_timeout = max(60, getattr(p, 'blocked_connection_timeout', 300))
        except Exception:
            pass
        return p

    def _open_channel(params: pika.URLParameters):
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.basic_qos(prefetch_count=2)
        ch.queue_declare(queue=TOPIC_VIDEO_JOBS, durable=True)
        ch.basic_consume(queue=TOPIC_VIDEO_JOBS, on_message_callback=handle)
        return conn, ch

    def _close_conn_safe(conn):
        try:
            if conn and getattr(conn, 'is_open', False):
                conn.close()
        except Exception:
            pass

    def _sleep_backoff(seconds: int):
        try:
            import time
            time.sleep(seconds)
        except Exception:
            pass

    # Resilient consume loop
    backoff = 1
    while True:
        try:
            params = _build_params(url)
            conn, ch = _open_channel(params)
            logger.info(f"Listening on {TOPIC_VIDEO_JOBS}...")
            backoff = 1
            ch.start_consuming()
        except KeyboardInterrupt:
            logger.info("Video worker interrupted, shutting down")
            try:
                _close_conn_safe(locals().get('conn'))
            finally:
                break
        except Exception as e:
            logger.warning(f"Video consumer error: {type(e).__name__}: {e}. Reconnecting in {backoff}s…")
            _close_conn_safe(locals().get('conn'))
            _sleep_backoff(min(backoff, 30))
            backoff = min(backoff * 2, 30)
            continue


if __name__ == "__main__":
    configure_logging()
    logger = getLogger("Worker")
    main()
