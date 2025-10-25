"""Higgs inference worker
Consumes higgs.audio.jobs messages, updates audio_jobs + dialogue rows.
Current implementation generates a placeholder silent file (to be replaced by real model inference).
"""
from __future__ import annotations
import json
import os
import sys
import time
import wave
import gc
from logging import getLogger, StreamHandler, Formatter

import pika

# Ensure project root import path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from settings import get_settings
from utils import AudioJobStatus, DialougeStatus
from services.messaging.messages import TOPIC_HIGGS_AUDIO_JOBS, TOPIC_VIDEO_JOBS
from workers.internal_api_client import (
    InternalAPIClient,
    InternalAPIError,
    ConflictError,
    NotFoundError,
)

logger = getLogger(__name__)

def _ensure_console_logging():
    """Attach a stdout stream handler if none (useful when running under debugger)."""
    if not any(isinstance(h, StreamHandler) for h in logger.handlers):
        sh = StreamHandler()
        sh.setFormatter(Formatter('%(asctime)s %(levelname)s %(name)s - %(message)s'))
        logger.addHandler(sh)
        logger.setLevel(os.getenv('LOG_LEVEL', 'INFO').upper())

_ensure_console_logging()

def _declare_queue(ch):
    ch.queue_declare(queue=TOPIC_HIGGS_AUDIO_JOBS, durable=True)


def _connect_with_backoff(url: str, *, max_attempts: int, base_delay: float, max_delay: float) -> pika.BlockingConnection:
    attempt = 0
    while True:
        attempt += 1
        try:
            params = pika.URLParameters(url)
            settings = get_settings()
            
            # Configure heartbeat to detect dead connections
            # Heartbeat interval - server will expect heartbeat frames from client
            params.heartbeat = settings.RABBITMQ_HEARTBEAT
            
            # Timeout for when RabbitMQ blocks connection (e.g., memory/disk alarms)
            params.blocked_connection_timeout = settings.RABBITMQ_BLOCKED_CONNECTION_TIMEOUT
            
            # Connection attempts and retry delay
            params.connection_attempts = settings.RABBITMQ_CONNECTION_ATTEMPTS
            params.retry_delay = settings.RABBITMQ_RETRY_DELAY
            
            # Socket timeout - how long to wait for socket operations
            params.socket_timeout = 10
            
            # Enable TCP keepalive for better detection of broken connections
            params.tcp_options = {
                'TCP_KEEPIDLE': 60,      # Start sending keepalive probes after 60s of idle
                'TCP_KEEPINTVL': 10,     # Send keepalive probes every 10s
                'TCP_KEEPCNT': 6         # Close connection after 6 failed probes
            }
            
            conn = pika.BlockingConnection(params)
            if attempt > 1:
                logger.info(f"[startup] Connected to RabbitMQ after {attempt} attempts")
            else:
                logger.info(f"[startup] Connected to RabbitMQ (heartbeat={params.heartbeat}s, blocked_timeout={params.blocked_connection_timeout}s)")
            return conn
        except Exception as e:
            if max_attempts and attempt >= max_attempts:
                logger.error(f"[startup] Failed to connect to RabbitMQ at {url} after {attempt} attempts: {e}")
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            logger.warning(f"[startup] RabbitMQ connection attempt {attempt} failed ({e}); retrying in {delay:.1f}s")
            time.sleep(delay)

def _convert_wav_to_mp3_stub(wav_path: str, mp3_path: str):
    """Attempt ffmpeg conversion else fallback to wav path."""
    try:
        import subprocess, shutil
        if shutil.which('ffmpeg'):
            # Speed up audio by 1.2x using FFmpeg's atempo filter
            subprocess.run(['ffmpeg','-y','-i', wav_path,
                           '-filter:a', 'atempo=1.2',  # Speed up audio by 1.2x
                           '-codec:a','libmp3lame','-qscale:a','4', mp3_path],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return mp3_path
        shutil.copyfile(wav_path, mp3_path)
        return mp3_path
    except Exception as e:
        logger.warning(f"MP3 conversion failed, using wav directly: {e}")
        return wav_path

def _process_message(body: bytes, api: InternalAPIClient):
    msg = json.loads(body.decode('utf-8'))
    audio_job_id = msg.get('audio_job_id')
    try:
        audio_job_id_int = int(audio_job_id)
    except Exception:
        logger.error(f"Invalid audio_job_id: {audio_job_id!r}")
        return
    dialogue_id = msg.get('dialogue_id')
    if audio_job_id is None or dialogue_id is None:
        raise ValueError("Missing audio_job_id or dialogue_id in message")
    try:
        dialogue_id_int = int(dialogue_id)
    except Exception:
        raise ValueError(f"Invalid dialogue_id: {dialogue_id!r}")
    try:
        job = api.claim_audio_job(audio_job_id_int)
    except ConflictError as exc:
        logger.info(f"audio_job_id {audio_job_id_int} already claimed elsewhere: {exc}")
        return
    except NotFoundError as exc:
        logger.warning(f"audio_job_id {audio_job_id_int} missing; dropping message: {exc}")
        return
    except InternalAPIError as exc:
        logger.error(f"Failed to claim audio_job_id {audio_job_id_int}: {exc}")
        raise
    # Model inference (currently uses abstraction stub)
    output_dir = os.path.join('audio_assests', 'generated')
    os.makedirs(output_dir, exist_ok=True)
    base_name = f"higgs_job_{audio_job_id}.wav"
    wav_path = os.path.join(output_dir, base_name)
    # Lazy import to avoid static import path issues in some environments
    try:
        from services.higgs_model_loader import get_higgs_model  # type: ignore
    except ModuleNotFoundError:  # fallback if run differently
        from higgs_model_loader import get_higgs_model  # type: ignore
    model = get_higgs_model()
    character_name = ''
    req_payload = job.get('request_payload')
    if isinstance(req_payload, dict):
        character_name = req_payload.get('character', '') or ''
    metrics = model.synthesize_to_wav(job['text'], character_name, wav_path)
    mp3_path = _convert_wav_to_mp3_stub(wav_path, wav_path.replace('.wav', '.mp3'))
    # Update job + dialogue
    rel_path = mp3_path  # already relative under project root
    api.update_audio_job(audio_job_id_int, status=AudioJobStatus.COMPLETED, output_path=rel_path)
    try:
        api.set_dialogue_audio(dialogue_id_int, rel_path)
        api.set_dialogue_status(dialogue_id_int, DialougeStatus.COMPLETED)
    except Exception as e:
        logger.error(f"Failed to update dialogue {dialogue_id}: {e}")
    
    # Check if all dialogues for this project are complete and auto-trigger video job
    project_id = msg.get('project_id')
    if project_id:
        try:
            counts = api.get_completion_counts(project_id)
            total = counts.get('total', 0)
            completed = counts.get('completed', 0)
            
            if total > 0 and completed == total:
                # All dialogues completed! Transition to RENDERING and enqueue video job
                logger.info(f"All dialogues complete for project {project_id} ({completed}/{total}). Triggering video generation.")
                
                transition = api.transition_status(project_id, expected=DialougeStatus.INPROGRESS, new_status="RENDERING")
                
                if transition.get('applied', False):
                    # Status successfully flipped, publish video job
                    # Get publisher from factory (need to import)
                    try:
                        import pika
                        settings = get_settings()
                        params = pika.URLParameters(settings.RABBITMQ_URL)
                        conn = pika.BlockingConnection(params)
                        ch = conn.channel()
                        ch.queue_declare(queue=TOPIC_VIDEO_JOBS, durable=True)
                        
                        video_job = json.dumps({"project_id": project_id})
                        ch.basic_publish(
                            exchange='',
                            routing_key=TOPIC_VIDEO_JOBS,
                            body=video_job.encode('utf-8'),
                            properties=pika.BasicProperties(delivery_mode=2)  # persistent
                        )
                        conn.close()
                        logger.info(f"Video job enqueued for project {project_id}")
                    except Exception as pub_err:
                        logger.error(f"Failed to publish video job for project {project_id}: {pub_err}")
                else:
                    logger.debug(f"Project {project_id} status already RENDERING or beyond, skipping video enqueue")
        except Exception as check_err:
            logger.warning(f"Failed to check/trigger video for project {project_id}: {check_err}")
    
    logger.info(f"Inference metrics job_id={audio_job_id} dialogue_id={dialogue_id} {metrics}")
    
    # Clean up memory after each inference to prevent accumulation
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

def main():
    settings = get_settings()
    url = settings.RABBITMQ_URL
    logger.info(f"[startup] Higgs worker internal API: {settings.INTERNAL_API_BASE_URL}")
    api_client = InternalAPIClient(
        settings.INTERNAL_API_BASE_URL,
        timeout=float(settings.INTERNAL_API_TIMEOUT),
    )

    logger.info(f"[startup] Higgs worker initializing. RabbitMQ={url}")
    try:
        conn = _connect_with_backoff(
            url,
            max_attempts=settings.RABBITMQ_CONNECT_MAX_ATTEMPTS,
            base_delay=max(settings.RABBITMQ_CONNECT_BASE_DELAY, 0.5),
            max_delay=max(settings.RABBITMQ_CONNECT_MAX_DELAY, settings.RABBITMQ_CONNECT_BASE_DELAY),
        )
    except Exception:
        return
    ch = conn.channel()
    _declare_queue(ch)
    ch.basic_qos(prefetch_count=1)

    def _ack(m):
        try:
            ch.basic_ack(delivery_tag=m.delivery_tag)
        except (pika.exceptions.ChannelWrongStateError, pika.exceptions.StreamLostError) as e:
            logger.warning(f"Failed to ack message (connection lost): {e}")

    def _nack(m, requeue=False):
        try:
            ch.basic_nack(delivery_tag=m.delivery_tag, requeue=requeue)
        except (pika.exceptions.ChannelWrongStateError, pika.exceptions.StreamLostError) as e:
            logger.warning(f"Failed to nack message (connection lost): {e}")

    def callback(ch_, method, properties, body):
        # ACK immediately to prevent redelivery
        _ack(method)
        
        msg = None
        audio_job_id = None
        dialogue_id = None
        
        try:
            # Parse message first to extract IDs for error handling
            msg = json.loads(body.decode('utf-8'))
            audio_job_id = msg.get('audio_job_id')
            dialogue_id = msg.get('dialogue_id')
            
            # Validate message structure
            if audio_job_id is None or dialogue_id is None:
                logger.error(f"Invalid message missing audio_job_id or dialogue_id: {body!r}")
                return
            
            # Process message (no heartbeat needed since already acked)
            _process_message(body, api_client)
                    
        except ValueError as ve:
            logger.error(f"Bad message format: {ve}; body={body!r}")
            gc.collect()  # Clean up memory even on error
        except Exception as e:
            # Mark job FAILED - don't requeue since we already acked
            logger.error(f"Processing failed for job {audio_job_id}, dialogue {dialogue_id}: {e}")
            try:
                if audio_job_id is not None:
                    try:
                        api_client.mark_audio_job_failed(int(audio_job_id), str(e)[:500])
                        logger.info(f"Marked audio_job {audio_job_id} as FAILED")
                    except InternalAPIError as api_err:
                        logger.error(f"Failed to mark audio job {audio_job_id} failed: {api_err}")
                
                if dialogue_id is not None:
                    try:
                        api_client.set_dialogue_status(int(dialogue_id), DialougeStatus.FAILED)
                        logger.info(f"Marked dialogue {dialogue_id} as FAILED")
                    except InternalAPIError as api_err:
                        logger.error(f"Failed to mark dialogue {dialogue_id} failed: {api_err}")
            except Exception as cleanup_err:
                logger.error(f"Error during failure cleanup: {cleanup_err}")
            finally:
                # Always clean up memory on error
                gc.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass

    ch.basic_consume(queue=TOPIC_HIGGS_AUDIO_JOBS, on_message_callback=callback)
    logger.info(f"Higgs inference worker listening on {TOPIC_HIGGS_AUDIO_JOBS} ...")
    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        try: conn.close()
        except Exception: pass

if __name__ == '__main__':
    main()
