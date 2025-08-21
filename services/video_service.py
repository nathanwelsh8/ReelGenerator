import os
from datetime import datetime
from typing import Optional, Dict

from db_handler import DBOperation
from services.editor_agent import DynamicVideoEditor
from utils import DialougeStatus

def generate_video_if_ready(db: DBOperation, project_id: int, background_video: str | None = None) -> Optional[Dict]:
    """If all dialogues are COMPLETED, build video and update project status.
    Returns dict with output info or None if not ready.
    """
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
    db.update_project_status(project_id, DialougeStatus.COMPLETED)
    return {"video_path": output_path, "project_id": project_id}
