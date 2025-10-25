import os
import sys
import json
import pika
from datetime import datetime
from typing import Any, Dict, Optional

"""Video worker: consumes video jobs and generates the final video when assets are ready."""

# Ensure project root is importable when running this file directly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.messaging.messages import TOPIC_VIDEO_JOBS
from settings import get_settings
from logging import getLogger
from services.config.logging_config import configure_logging
from utils import DialougeStatus
from services.editor_agent import DynamicVideoEditor
from workers.internal_api_client import InternalAPIClient, InternalAPIError, NotFoundError


def main():
    settings = get_settings()
    url = settings.RABBITMQ_URL

    api_client = InternalAPIClient(
        settings.INTERNAL_API_BASE_URL,
        timeout=float(settings.INTERNAL_API_TIMEOUT),
    )
    logger.info(f"[startup] Video worker internal API: {settings.INTERNAL_API_BASE_URL}")

    def _parse_message(body: bytes) -> dict:
        return json.loads(body.decode("utf-8"))

    def _ack(ch_, method):
        ch_.basic_ack(delivery_tag=method.delivery_tag)

    def _nack_requeue(ch_, method):
        ch_.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _attempt_video_render(project_id: int) -> Optional[Dict[str, Any]]:
        project = api_client.get_project(project_id)
        current_status = project.get("status")
        if current_status != "RENDERING":
            logger.info(f"Project {project_id} status {current_status} not ready for rendering - ACKing message to avoid infinite loop")
            # Return a special value to indicate we should ACK but not process
            return {"skipped": True, "reason": "not_rendering"}

        counts = api_client.get_completion_counts(project_id)
        total = int(counts.get("total", 0))
        completed = int(counts.get("completed", 0))
        if total == 0 or completed < total:
            logger.info(f"Project {project_id} dialogues incomplete (total={total}, completed={completed}) - ACKing message to avoid infinite loop")
            # Return a special value to indicate we should ACK but not process
            return {"skipped": True, "reason": "incomplete_dialogues"}

        ready_assets = api_client.get_ready_assets(project_id)
        if not ready_assets:
            logger.info(f"Project {project_id} has no ready assets yet - ACKing message to avoid infinite loop")
            return {"skipped": True, "reason": "no_ready_assets"}

        video_dir = "video_assets"
        os.makedirs(video_dir, exist_ok=True)
        background_video = os.path.join(video_dir, "background_videos", "Minecraft Parkour Gameplay.mp4")
        if not os.path.exists(background_video):
            logger.warning(f"Background video missing for project {project_id}; ACKing message to avoid infinite loop")
            return {"skipped": True, "reason": "missing_background_video"}

        filename = f"output_video_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = os.path.join(video_dir, filename)
        editor = DynamicVideoEditor(
            video_path=background_video,
            output_path=output_path,
            dialogue_data=ready_assets,
        )
        editor.edit()

        api_client.set_video_path(project_id, output_path)
        try:
            transition = api_client.transition_status(project_id, expected="RENDERING", new_status=DialougeStatus.COMPLETED)
            if not transition.get("applied", False):
                logger.debug(f"Project {project_id} status transition not applied (already in target state?)")
        except InternalAPIError as exc:
            logger.warning(f"Project {project_id} status transition failed: {exc}")
        return {"video_path": output_path, "project_id": project_id}

    def _process(msg: dict):
        project_id = msg.get("project_id")
        if not project_id:
            raise ValueError("video job missing project_id")
        logger.info(f"Processing video job for project_id={project_id}")

        project_id_int = int(project_id)
        try:
            result = _attempt_video_render(project_id_int)
        except NotFoundError as exc:
            logger.warning(f"Project {project_id_int} missing: {exc}")
            return True
        except InternalAPIError as exc:
            raise RuntimeError(f"Internal API failure: {exc}") from exc

        if result:
            # Check if it was skipped (not ready) or actually processed
            if result.get("skipped"):
                logger.info(f"Video job skipped for project {project_id}: {result.get('reason')}")
                return True  # ACK to remove from queue
            logger.info(f"Video generated: {result}")
            return True
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
        # Use configurable settings for heartbeat and timeouts
        p.heartbeat = settings.RABBITMQ_HEARTBEAT
        p.blocked_connection_timeout = settings.RABBITMQ_BLOCKED_CONNECTION_TIMEOUT
        p.connection_attempts = settings.RABBITMQ_CONNECTION_ATTEMPTS
        p.retry_delay = settings.RABBITMQ_RETRY_DELAY
        p.socket_timeout = 10
        # Enable TCP keepalive for better detection of broken connections
        p.tcp_options = {
            'TCP_KEEPIDLE': 60,      # Start sending keepalive probes after 60s of idle
            'TCP_KEEPINTVL': 10,     # Send keepalive probes every 10s
            'TCP_KEEPCNT': 6         # Close connection after 6 failed probes
        }
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
