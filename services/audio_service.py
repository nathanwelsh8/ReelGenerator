import concurrent.futures
import functools
from datetime import datetime
from typing import Dict

from db_handler import DBOperation
from services.scrap_audio import VoiceGenerator
from utils import DialougeStatus

def _process_single(row, db: DBOperation, voice_gen: VoiceGenerator):
    # row: id, sentence, character, image, image_search, audio, status, character_id
    dialogue_id = row[0]
    sentence = row[1]
    character = row[2]
    character_id = row[7] if len(row) > 7 else None
    try:
        db.update_status(dialogue_id, DialougeStatus.INPROGRESS)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        path = voice_gen.generate_audio_from_sentence(
            sentence.strip(),
            character.strip().lower(),
            f"{dialogue_id}_{timestamp}",
            db_handler=db,
            dialogue_id=dialogue_id,
            character_id=character_id,
        )
        if path:
            db.update_status(dialogue_id, DialougeStatus.COMPLETED)
    except Exception:
        db.update_status(dialogue_id, DialougeStatus.FAILED)


def process_dialogues_for_project(db: DBOperation, project_id: int, max_workers: int | None = None) -> Dict[str, int]:
    """Process NEW or FAILED dialogues for a project in parallel.
    Returns counts of processed and remaining.
    """
    voice_gen = VoiceGenerator()
    db.reconcile_dialogue_statuses(project_id)
    rows = db.get_dialogues_for_processing(project_id)
    if not rows:
        return {"processed": 0, "remaining": 0}
    task = functools.partial(_process_single, db=db, voice_gen=voice_gen)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(task, rows))
    remaining = db.get_dialogues_for_processing(project_id)
    return {"processed": len(rows), "remaining": len(remaining)}
