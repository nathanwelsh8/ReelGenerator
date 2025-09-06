import json
import os
import sys
import pika
from typing import Any

"""Audio worker: consumes audio jobs and generates audio files."""

# Ensure project root is importable when running this file directly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from db_handler import DBOperation
from services.scrap_audio import VoiceGenerator
from utils import DialougeStatus
from services.messaging.messages import TOPIC_AUDIO_JOBS, TOPIC_VIDEO_JOBS, VideoJob
from settings import get_settings
from logging import getLogger
from services.config.logging_config import configure_logging
from services.config.job_types import JOB_TYPES
from services.messaging.factory import get_publisher

def validate_message(msg: dict) -> None:
    """Validate required fields in the message. Raises ValueError on missing keys.

    - Always require: job_type, sentence, character
    - project_dialogue requires: dialogue_id
    - character_follow requires: character_id
    """
    base_required = {"job_type", "sentence", "character"}
    missing = base_required - set(msg.keys())
    if missing:
        raise ValueError(f"Invalid message format: missing keys {missing}; got keys {set(msg.keys())}")
    jt = str(msg.get("job_type") or "").strip()
    if jt == JOB_TYPES.PROJECT_DIALOGUE:
        if msg.get("dialogue_id") is None:
            raise ValueError("project_dialogue job requires dialogue_id")
    elif jt == JOB_TYPES.CHARACTER_FOLLOW:
        if msg.get("character_id") is None:
            raise ValueError("character_follow job requires character_id")

def main():
    settings = get_settings()
    url = settings.RABBITMQ_URL

    db = DBOperation()
    vg = VoiceGenerator()

    def _parse_message(body: bytes) -> dict:
        return json.loads(body.decode("utf-8"))

    def _supported_job_type(job_type: str | None) -> bool:
        return job_type in JOB_TYPES.get_jobs()

    def _update_status_safe(did, status) -> None:
        if did is None:
            return
        try:
            db.update_status(did, status)
        except Exception:
            # Non-fatal; reconciliation can repair later
            logger.warning(f"Failed to update status for dialogue_id={did} to {status}")

    def _generate_audio(sentence: str, character: str, dialogue_id, character_id):
        return vg.generate_audio_from_sentence(
            str(sentence).strip(),
            str(character).strip().lower(),
            str(dialogue_id) if dialogue_id is not None else "follow",
            db_handler=db,
            dialogue_id=dialogue_id,
            character_id=character_id,
        )

    def _ack(ch_, method):
        ch_.basic_ack(delivery_tag=method.delivery_tag)

    def _nack_requeue(ch_, method):
        ch_.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _maybe_enqueue_video(project_id: int | None):
        """If all dialogues are completed for the project, enqueue a video job once."""
        if not project_id:
            return
        total, done = db.get_dialogue_completion_counts(project_id)
        if total == 0 or done < total:
            return
        # Try to mark as RENDERING to avoid duplicate enqueues from multiple workers
        if db.mark_project_status_if(project_id, expected_current=DialougeStatus.INPROGRESS, new_status="RENDERING"):
            try:
                publisher = get_publisher()
                vjob: VideoJob = {"project_id": project_id}
                publisher.publish(TOPIC_VIDEO_JOBS, vjob, key=str(project_id))
                logger.info(f"Enqueued video job for project_id={project_id}")
            except Exception:
                logger.exception("Failed to publish video job; reverting project status to INPROGRESS")
                # Best-effort revert so another attempt can be made later
                try:
                    db.mark_project_status_if(project_id, expected_current="RENDERING", new_status=DialougeStatus.INPROGRESS)
                except Exception:
                    pass

    def _process_message(msg: dict):
        # Validate and extract
        validate_message(msg)
        job_type = msg.get("job_type")
        dialogue_id = msg.get("dialogue_id")
        sentence = msg.get("sentence")
        character = msg.get("character")
        character_id = msg.get("character_id")
        project_id = msg.get("project_id")
        # Fallback: infer project_id from dialogue row if not provided
        if not project_id and dialogue_id:
            try:
                project_id = db.get_project_id_for_dialogue(int(dialogue_id))
            except Exception:
                project_id = None
        logger.info(f"Processing audio job: type={job_type}, dialogue_id={dialogue_id}")

        # Mark in-progress for dialogue jobs
        _update_status_safe(dialogue_id, DialougeStatus.INPROGRESS)

        try:
            path = _generate_audio(sentence, character, dialogue_id, character_id)
        except Exception:
            logger.exception(f"Failed to generate audio for dialogue_id={dialogue_id}")

        if path:
            _update_status_safe(dialogue_id, DialougeStatus.COMPLETED)
            # After completing a dialogue, check if the project is ready for video
            _maybe_enqueue_video(project_id)
        if not path:
            _update_status_safe(dialogue_id, DialougeStatus.FAILED)

    # --- Main callback ---
    def handle(ch_, method, properties, body: bytes):
        try:
            msg = _parse_message(body)
            job_type = msg.get("job_type")

            # Discard messages not in valid queues
            if not _supported_job_type(job_type):
                logger.warning(f"Message with job_type {job_type} will be discarded.")
                _ack(ch_, method)
                return

            _process_message(msg)
            _ack(ch_, method)
        except Exception:
            try:
                if method:
                    _nack_requeue(ch_, method)
                    logger.info("Message requeued due to failure")
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
        ch.basic_qos(prefetch_count=4)
        ch.queue_declare(queue=TOPIC_AUDIO_JOBS, durable=True)
        ch.basic_consume(queue=TOPIC_AUDIO_JOBS, on_message_callback=handle)
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

    # Resilient consume loop with heartbeat and timeouts
    backoff = 1
    while True:
        try:
            params = _build_params(url)
            conn, ch = _open_channel(params)
            logger.info(f"Listening on {TOPIC_AUDIO_JOBS}...")
            backoff = 1
            ch.start_consuming()
        except KeyboardInterrupt:
            logger.info("Worker interrupted, shutting down")
            try:
                _close_conn_safe(locals().get('conn'))
            finally:
                break
        except Exception as e:
            logger.warning(f"Consumer error: {type(e).__name__}: {e}. Reconnecting in {backoff}s…")
            _close_conn_safe(locals().get('conn'))
            _sleep_backoff(min(backoff, 30))
            backoff = min(backoff * 2, 30)
            continue

if __name__ == "__main__":
    configure_logging()
    logger = getLogger("Worker")
    main()
