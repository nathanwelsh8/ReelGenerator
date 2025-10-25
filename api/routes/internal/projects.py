from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool

from api.schemas import (
    DialogueOut,
    ProjectDialogueList,
    ProjectSnapshot,
    ProjectStatusTransition,
    ProjectVideoPathUpdate,
)
from services.internal.projects import InternalProjectService, ProjectNotFoundError

router = APIRouter(prefix="/projects", tags=["internal-projects"])


def get_service() -> InternalProjectService:
    return InternalProjectService()


@router.get("/{project_id}", response_model=ProjectSnapshot)
async def get_project(project_id: int, service: InternalProjectService = Depends(get_service)):
    try:
        project = await run_in_threadpool(service.get_project, project_id)
        return project
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{project_id}/dialogues", response_model=ProjectDialogueList)
async def get_project_dialogues(
    project_id: int,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    service: InternalProjectService = Depends(get_service),
):
    try:
        data = await run_in_threadpool(service.list_dialogues, project_id, status=status_filter)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    payload = {
        "project_id": project_id,
        "total": data["total"],
        "completed": data["completed"],
        "dialogues": [DialogueOut(**row) for row in data["dialogues"]],
    }
    return payload


@router.get("/{project_id}/ready-assets", response_model=list[DialogueOut] | None)
async def get_ready_assets(project_id: int, service: InternalProjectService = Depends(get_service)):
    try:
        assets = await run_in_threadpool(service.ready_assets, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not assets:
        return None
    return [DialogueOut(**row) for row in assets]


@router.post("/{project_id}/status-transition", response_model=dict)
async def transition_status(
    project_id: int,
    payload: ProjectStatusTransition,
    service: InternalProjectService = Depends(get_service),
):
    try:
        applied = await run_in_threadpool(
            service.status_transition,
            project_id,
            payload.expected,
            payload.next,
        )
        return {"project_id": project_id, "applied": applied}
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{project_id}/completion", response_model=dict)
async def completion_counts(project_id: int, service: InternalProjectService = Depends(get_service)):
    try:
        counts = await run_in_threadpool(service.completion_counts, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"project_id": project_id, **counts}


@router.patch("/{project_id}/video-path", status_code=status.HTTP_204_NO_CONTENT)
async def set_video_path(
    project_id: int,
    payload: ProjectVideoPathUpdate,
    service: InternalProjectService = Depends(get_service),
):
    try:
        await run_in_threadpool(service.update_video_path, project_id, payload.video_path)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
