import concurrent.futures
import functools
from datetime import datetime
from typing import Dict

from db_handler import DBOperation
from services.scrap_audio import VoiceGenerator
from utils import DialougeStatus
from services.messaging.factory import get_publisher
from services.messaging.messages import TOPIC_HIGGS_AUDIO_JOBS, AudioJob
from services.config.job_types import JOB_TYPES
try:
    from services.audio_job_service import AudioJobService
except ModuleNotFoundError:  # fallback if run as script with cwd=/app/services
    from audio_job_service import AudioJobService  # type: ignore
from utils import AudioJobStatus

def _process_single(row, db: DBOperation, project_id: int | None = None, user_id: int | None = None):
    # row: id, sentence, character, image, image_search, audio, status, character_id
    dialogue_id = row[0]
    sentence = row[1]
    character = row[2]
    character_id = row[7] if len(row) > 7 else None
    try:
        db.update_status(dialogue_id, DialougeStatus.INPROGRESS)
        publisher = get_publisher()
        # Create or reuse an internal audio_jobs tracking row for Higgs pipeline
        audio_job_service = AudioJobService(db)
        existing = audio_job_service.find_latest_for_dialogue(dialogue_id)
        if existing and existing.get('status') in (AudioJobStatus.QUEUED, AudioJobStatus.IN_PROGRESS):
            audio_job_row = existing
        elif existing and existing.get('status') == AudioJobStatus.FAILED:
            # Reset failed job to QUEUED for retry
            audio_job_service.update_status(existing['id'], AudioJobStatus.QUEUED, error=None)
            audio_job_row = audio_job_service.get_job(existing['id']) or existing
        else:
            payload = {
                "dialogue_id": dialogue_id,
                "project_id": project_id,
                "character": character.strip(),
            }
            audio_job_row = audio_job_service.create_job(
                text=sentence.strip(),
                voice=None,
                user_id=user_id,
                payload=payload,
            )
        higgs_job: AudioJob = {
            "job_type": JOB_TYPES.HIGGS_DIALOGUE,
            "project_id": project_id if project_id is not None else None,
            "dialogue_id": dialogue_id,
            "sentence": sentence.strip(),
            "character": character.strip(),
            "character_id": character_id,
            "audio_job_id": audio_job_row["id"],
        }  # type: ignore[typeddict-item]
        publisher.publish(TOPIC_HIGGS_AUDIO_JOBS, higgs_job, key=str(audio_job_row["id"]))
    except Exception:
        print(f"Error occurred while publishing audio job. Updating {dialogue_id} status to FAILED.")
        db.update_status(dialogue_id, DialougeStatus.FAILED)


def process_dialogues_for_project(db: DBOperation, project_id: int, max_workers: int = 4, *, user_id: int | None = None) -> Dict[str, int]:
    """Enqueue NEW or FAILED dialogues for async processing.
    Returns counts of enqueued and remaining.
    """
    # Mark the project as INPROGRESS so the worker can flip to RENDERING when done
    try:
        db.update_project_status(project_id, DialougeStatus.INPROGRESS)
    except Exception:
        pass
    # NOTE: reconcile removed from here - it was resetting INPROGRESS dialogues to NEW
    # before jobs could complete. User should call /reconcile endpoint explicitly if needed.
    rows = db.get_dialogues_for_processing(project_id)
    if not rows:
        return {"processed": 0, "remaining": 0}
    task = functools.partial(_process_single, db=db, project_id=project_id, user_id=user_id)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(task, rows))
    remaining = db.get_dialogues_for_processing(project_id)
    return {"processed": len(rows), "remaining": len(remaining)}
