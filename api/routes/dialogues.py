from typing import List, Optional
from fastapi import APIRouter, Query, Depends, HTTPException
from db_handler import DBOperation
from api.schemas import DialogueOut
from api.routes.auth import get_current_user

router = APIRouter()
db = DBOperation()


@router.get("/", response_model=List[DialogueOut])
def list_dialogues(project_id: int, status: Optional[str] = Query(default=None), user=Depends(get_current_user)):
    # Enforce ownership
    proj = db.get_project_by_id_for_user(project_id, user.get('id'))
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if status:
        rows = db.get_dialogues_by_status(status, project_id)
    else:
        rows = db.get_all_dialogues_by_project(project_id)
    out: List[DialogueOut] = []  # type: ignore[assignment]
    for r in rows:
        out.append(DialogueOut(
            id=r[0], sentence=r[1], character=r[2], image=r[3], image_search=r[4],
            audio=r[5] if len(r) > 5 else None, status=r[6] if len(r) > 6 else "", character_id=r[7] if len(r) > 7 else None
        ))
    return out


@router.get("/ready", response_model=List[DialogueOut] | None)
def list_ready_dialogues(project_id: int, user=Depends(get_current_user)):
    proj = db.get_project_by_id_for_user(project_id, user.get('id'))
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    rows = db.get_ready_assets(project_id)
    if not rows:
        return None
    return [DialogueOut(**row) for row in rows]
