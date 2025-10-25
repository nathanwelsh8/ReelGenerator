"""Internal dialogue operations exposed through worker API."""

from __future__ import annotations

from typing import Dict, List, Optional

from logging import getLogger

from db_handler import DBOperation

logger = getLogger(__name__)


class DialogueNotFoundError(LookupError):
    """Raised when a dialogue row cannot be located."""


def _row_to_dict(row) -> Dict:
    return {
        "id": row[0],
        "sentence": row[1],
        "character": row[2],
        "image": row[3],
        "image_search": row[4],
        "audio": row[5] if len(row) > 5 else None,
        "status": row[6] if len(row) > 6 else None,
        "character_id": row[7] if len(row) > 7 else None,
    }


class InternalDialogueService:
    def __init__(self, db: DBOperation | None = None):
        self.db = db or DBOperation()

    def update_audio_path(self, dialogue_id: int, audio_path: str) -> None:
        conn = self.db.connect(); cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE dialouge_stage SET audio = ? WHERE id = ?;",
                (audio_path, dialogue_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise DialogueNotFoundError(f"dialogue_id {dialogue_id} not found")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def update_status(self, dialogue_id: int, status: str) -> None:
        updated = self.db.update_status(dialogue_id, status)
        if not updated:
            raise DialogueNotFoundError(f"dialogue_id {dialogue_id} not found")

    def list_dialogues(self, project_id: int, *, status: Optional[str] = None) -> List[Dict]:
        rows = self.db.get_dialogues_by_status(status, project_id) if status else self.db.get_all_dialogues_by_project(project_id)
        return [_row_to_dict(row) for row in rows]

    def ready_assets(self, project_id: int) -> Optional[List[Dict]]:
        rows = self.db.get_ready_assets(project_id)
        return rows

    def completion_counts(self, project_id: int) -> Dict[str, int]:
        total, completed = self.db.get_dialogue_completion_counts(project_id)
        return {"total": total, "completed": completed}
