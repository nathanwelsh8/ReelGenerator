from fastapi import APIRouter, HTTPException, status
from services.instagram_uploader import upload_project, upload_completed_projects

router = APIRouter()


@router.post("/project/{project_id}", status_code=status.HTTP_202_ACCEPTED)
def upload_single_project(project_id: int):
    res = upload_project(project_id)
    if res.get("error"):
        raise HTTPException(status_code=400, detail=res)
    return res


@router.post("/projects/completed", status_code=status.HTTP_202_ACCEPTED)
def upload_all_completed():
    return upload_completed_projects()
