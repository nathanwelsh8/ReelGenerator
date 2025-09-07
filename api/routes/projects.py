from typing import List
from fastapi import APIRouter, HTTPException, Depends
from db_handler import DBOperation
from services.project_service import create_project_with_dialogues, ProjectExistsError
from api.schemas import ProjectCreate, ProjectOut
from api.routes.auth import get_current_user

router = APIRouter()
db = DBOperation()


@router.get("/", response_model=List[ProjectOut])
def list_projects(user=Depends(get_current_user)):
    rows = db.get_projects(user_id=user.get('id'))
    out: List[ProjectOut] = []  # type: ignore[assignment]
    for r in rows:
        # id, title, caption, pdf_url, status, video_path
        out.append(ProjectOut(
            id=r[0], title=r[1], caption=r[2], pdf_url=r[3], status=r[4], video_path=r[5],
            speaker1_id=None, speaker2_id=None
        ))
    return out


@router.post("/", response_model=dict)
def create_project(payload: ProjectCreate, user=Depends(get_current_user)):
    try:
        res = create_project_with_dialogues(
            db,
            project_name=payload.title,
            caption=payload.caption,
            pdf_url=str(payload.pdf_url),
            speaker1_id=payload.speaker1_id or 0,
            speaker2_id=payload.speaker2_id or 0,
            user_id=user.get('id')
        )
        return res
    except ProjectExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, user=Depends(get_current_user)):
    p = db.get_project_by_id_for_user(project_id, user.get('id'))
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectOut(**p)
