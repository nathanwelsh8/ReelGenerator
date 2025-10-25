"""Internal project operations for worker coordination."""

from __future__ import annotations

from typing import Dict, List, Optional

from db_handler import DBOperation

from .dialogues import InternalDialogueService


class ProjectNotFoundError(LookupError):
    """Raised when a project cannot be located."""


class InternalProjectService:
    def __init__(
        self,
        db: DBOperation | None = None,
        dialogue_service: InternalDialogueService | None = None,
    ):
        self.db = db or DBOperation()
        self.dialogues = dialogue_service or InternalDialogueService(self.db)

    def get_project(self, project_id: int) -> Dict:
        project = self.db.get_project_by_id(project_id)
        if not project:
            raise ProjectNotFoundError(f"project_id {project_id} not found")
        return project

    def list_dialogues(self, project_id: int, *, status: Optional[str] = None) -> Dict:
        self.get_project(project_id)
        data = self.dialogues.list_dialogues(project_id, status=status)
        counts = self.dialogues.completion_counts(project_id)
        return {"project_id": project_id, "dialogues": data, **counts}

    def ready_assets(self, project_id: int) -> Optional[List[Dict]]:
        self.get_project(project_id)
        return self.dialogues.ready_assets(project_id)

    def status_transition(self, project_id: int, expected_current: str, new_status: str) -> bool:
        project = self.get_project(project_id)
        if project.get("status") == new_status:
            return True
        return self.db.mark_project_status_if(project_id, expected_current=expected_current, new_status=new_status)

    def update_video_path(self, project_id: int, video_path: str) -> None:
        self.get_project(project_id)
        self.db.update_project_video_path(project_id, video_path)

    def completion_counts(self, project_id: int) -> Dict[str, int]:
        self.get_project(project_id)
        return self.dialogues.completion_counts(project_id)
