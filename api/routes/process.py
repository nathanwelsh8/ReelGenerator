from fastapi import APIRouter, status, HTTPException, Depends
from db_handler import DBOperation
from services.audio_service import process_dialogues_for_project
from services.video_service import enqueue_video_job_if_ready
from api.routes.auth import get_current_user

router = APIRouter()


@router.post("/project/{project_id}", status_code=status.HTTP_202_ACCEPTED)
def enqueue_project_processing(project_id: int, user=Depends(get_current_user)):
    """Enqueue audio generation jobs for a project's dialogues. Returns quickly."""
    db = DBOperation()
    # Ensure user owns the project
    p = db.get_project_by_id_for_user(project_id, user.get('id'))
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    stats = process_dialogues_for_project(db, project_id, user_id=user.get('id'))
    return {"queued": stats["processed"], "remaining": stats["remaining"], "project_id": project_id}


@router.post("/project/{project_id}/reconcile", status_code=status.HTTP_200_OK)
def reconcile_project_dialogues(project_id: int, user=Depends(get_current_user)):
    """Reconcile dialogue statuses for a project (complete rows with audio; requeue stuck INPROGRESS)."""
    db = DBOperation()
    # Ownership check
    p = db.get_project_by_id_for_user(project_id, user.get('id'))
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    res = db.reconcile_dialogue_statuses(project_id)
    return {"project_id": project_id, **res}


@router.post("/project/{project_id}/enqueue-video", status_code=status.HTTP_202_ACCEPTED)
def enqueue_project_video(project_id: int, user=Depends(get_current_user)):
    """If all dialogues are COMPLETED, enqueue a video job for the project.

    Returns 202 with details. If not ready, returns 409 with counts.
    """
    db = DBOperation()
    # Ownership check
    p = db.get_project_by_id_for_user(project_id, user.get('id'))
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        result = enqueue_video_job_if_ready(db, project_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Project has no dialogues")
    if not result.get("ready"):
        raise HTTPException(status_code=409, detail={
            "message": "Project dialogues not all completed",
            "total": result.get("total", 0),
            "completed": result.get("completed", 0),
        })
    return {"project_id": project_id, "enqueued": True, **result}
