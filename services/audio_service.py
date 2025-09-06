import concurrent.futures
import functools
from datetime import datetime
from typing import Dict

from db_handler import DBOperation
from services.scrap_audio import VoiceGenerator
from utils import DialougeStatus
from services.messaging.factory import get_publisher
from services.messaging.messages import TOPIC_AUDIO_JOBS, AudioJob
from services.config.job_types import JOB_TYPES

def _process_single(row, db: DBOperation, project_id: int | None = None):
    # row: id, sentence, character, image, image_search, audio, status, character_id
    dialogue_id = row[0]
    sentence = row[1]
    character = row[2]
    character_id = row[7] if len(row) > 7 else None
    try:
        db.update_status(dialogue_id, DialougeStatus.INPROGRESS)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        # In async mode, push to queue instead of generating here
        publisher = get_publisher()
        job: AudioJob = {
            "job_type": JOB_TYPES.PROJECT_DIALOGUE,
            "project_id": project_id if project_id is not None else None,
            "dialogue_id": dialogue_id,
            "sentence": sentence.strip(),
            "character": character.strip(),
            "character_id": character_id,
        }  # type: ignore[typeddict-item]
        publisher.publish(TOPIC_AUDIO_JOBS, job, key=str(dialogue_id))
    except Exception:
        print(f"Error occurred while publishing audio job. Updating {dialogue_id} status to FAILED.")
        db.update_status(dialogue_id, DialougeStatus.FAILED)


def process_dialogues_for_project(db: DBOperation, project_id: int, max_workers: int = 4) -> Dict[str, int]:
    """Enqueue NEW or FAILED dialogues for async processing.
    Returns counts of enqueued and remaining.
    """
    # Mark the project as INPROGRESS so the worker can flip to RENDERING when done
    try:
        db.update_project_status(project_id, DialougeStatus.INPROGRESS)
    except Exception:
        pass
    db.reconcile_dialogue_statuses(project_id)
    rows = db.get_dialogues_for_processing(project_id)
    if not rows:
        return {"processed": 0, "remaining": 0}
    task = functools.partial(_process_single, db=db, project_id=project_id)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(task, rows))
    remaining = db.get_dialogues_for_processing(project_id)
    return {"processed": len(rows), "remaining": len(remaining)}
