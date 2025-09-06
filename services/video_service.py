import os
from datetime import datetime
from typing import Optional, Dict

from db_handler import DBOperation
from services.editor_agent import DynamicVideoEditor
from utils import DialougeStatus
from services.messaging.factory import get_publisher
from services.messaging.messages import TOPIC_VIDEO_JOBS, VideoJob

def generate_video_if_ready(db: DBOperation, project_id: int, background_video: str | None = None) -> Optional[Dict]:
    """If all dialogues are COMPLETED, build video and transition project status.

    Pipeline of expected statuses:
        INPROGRESS -> (all dialogues done triggers enqueue) -> RENDERING -> COMPLETED -> UPLOADED

    This function should ONLY transition RENDERING -> COMPLETED.
    It must NOT overwrite a later terminal state like UPLOADED.
    If a stray / duplicate video job runs after upload, we simply no-op.
    Returns dict with output info or None if not ready / not in correct state.
    """
    # Fetch current project to inspect status before any heavy work
    project = db.get_project_by_id(project_id)
    if not project:
        return None
    current_status = project.get("status")
    # Only proceed if we're in the rendering phase; avoid regenerating after completion/upload
    if current_status not in ("RENDERING",):
        return None

    all_rows = db.get_all_dialogues_by_project(project_id)
    completed = db.get_dialogues_by_status(DialougeStatus.COMPLETED, project_id)
    if not all_rows or len(completed) < len(all_rows):
        return None

    ready_assets = db.get_ready_assets(project_id)
    if not ready_assets:
        return None

    video_dir = "video_assets"
    os.makedirs(video_dir, exist_ok=True)
    if not background_video:
        background_video = os.path.join(video_dir, "background_videos", "Minecraft Parkour Gameplay.mp4")
    if not os.path.exists(background_video):
        return None

    filename = f"output_video_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(video_dir, filename)
    editor = DynamicVideoEditor(video_path=background_video, output_path=output_path, dialogue_data=ready_assets)
    editor.edit()
    db.update_project_video_path(project_id, output_path)
    # Only flip status if it is still RENDERING (race-safe: might have been updated meanwhile)
    try:
        db.mark_project_status_if(project_id, expected_current="RENDERING", new_status=DialougeStatus.COMPLETED)
    except Exception:
        # Non-fatal; better to have video path saved than crash
        pass
    return {"video_path": output_path, "project_id": project_id}


def enqueue_video_job_if_ready(db: DBOperation, project_id: int) -> Dict:
    """If project has all dialogues COMPLETED, enqueue a video job and optionally
    move project status to RENDERING to avoid duplicate enqueues.

    Returns a dict with:
      - ready: bool (whether it was ready and job was enqueued)
      - total, completed: counts
      - status: "RENDERING" if status flipped, else "UNCHANGED" (present when ready)

    Raises LookupError if the project has no dialogues.
    """
    total, done = db.get_dialogue_completion_counts(project_id)
    if total == 0:
        raise LookupError("Project has no dialogues")
    if done < total:
        return {"ready": False, "total": total, "completed": done}

    flipped = False
    try:
        flipped = db.mark_project_status_if(project_id, expected_current=DialougeStatus.INPROGRESS, new_status="RENDERING")
    except Exception:
        flipped = False

    publisher = get_publisher()
    vjob: VideoJob = {"project_id": project_id}  # type: ignore[typeddict-item]
    publisher.publish(TOPIC_VIDEO_JOBS, vjob, key=str(project_id))
    return {
        "ready": True,
        "status": "RENDERING" if flipped else "UNCHANGED",
        "total": total,
        "completed": done,
    }
