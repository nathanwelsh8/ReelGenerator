"""High level orchestration for processing a project (audio + video)."""
from typing import Optional, Dict, Any

from db_handler import DBOperation
from utils import DialougeStatus
from services.audio_service import process_dialogues_for_project
from services.video_service import generate_video_if_ready

def select_project(db: DBOperation) -> Optional[int]:
    project = db.get_project_by_status(DialougeStatus.INPROGRESS)
    if project:
        return project[0]
    project = db.get_project_by_status(DialougeStatus.NEW)
    if project:
        db.update_project_status(project[0], DialougeStatus.INPROGRESS)
        return project[0]
    return None

def process_project(project_id: int | None = None) -> Dict[str, Any]:
    db = DBOperation()
    if project_id is None:
        project_id = select_project(db)
    if project_id is None:
        return {"status": "noop", "reason": "no project available"}

    audio_stats = process_dialogues_for_project(db, project_id)
    video_info = generate_video_if_ready(db, project_id)
    result: Dict[str, Any] = {"status": "inprogress", "project_id": project_id, "audio": audio_stats}
    if video_info:
        result["status"] = "completed"
        result["video"] = video_info["video_path"]
    return result
