from __future__ import annotations
import os
from typing import Optional, Dict, List
from instagrapi import Client
from settings import get_settings
from db_handler import DBOperation
from utils import DialougeStatus
from services.thumbnail_generator import generate as generate_thumbnail
from services.caption_generator import generate_caption


def _login_client() -> Client:
    settings = get_settings()
    username = settings.INSTAGRAM_USERNAME
    password = settings.INSTAGRAM_PASSWORD
    if not username or not password:
        raise ValueError("INSTAGRAM_USERNAME/INSTAGRAM_PASSWORD not configured")
    cl = Client()
    cl.login(username, password)
    return cl


def _build_caption(project: Dict) -> str:
    return generate_caption(project['title'], project['caption'], project['pdf_url'])


def _build_thumbnail(project: Dict) -> Optional[str]:
    video_path = project.get('video_path')
    if not video_path or not os.path.isfile(video_path):
        return None
    return generate_thumbnail(project['title'], f"thumbnail_{project['id']}", video_path)


def upload_project(project_id: int) -> Dict:
    db = DBOperation()
    proj = db.get_project_by_id(project_id)
    if not proj:
        return {"project_id": project_id, "error": "Project not found"}
    if proj.get('status') != DialougeStatus.COMPLETED:
        return {"project_id": project_id, "error": f"Project not COMPLETED (status={proj.get('status')})"}

    video_path = proj.get('video_path')
    if not video_path or not os.path.isfile(video_path):
        return {"project_id": project_id, "error": f"Video file not found: {video_path}"}

    try:
        caption = _build_caption(proj)
    except Exception as e:
        return {"project_id": project_id, "error": f"Caption generation failed: {e}"}

    thumb = None
    try:
        thumb = _build_thumbnail(proj)
    except Exception as e:
        # Thumbnail is optional; proceed without it
        thumb = None

    try:
        cl = _login_client()
        media = cl.clip_upload(video_path, caption=caption, thumbnail=thumb)
        db.update_project_status(project_id, DialougeStatus.UPLOADED)
        return {"project_id": project_id, "uploaded": True, "media_id": getattr(media, 'pk', None)}
    except Exception as e:
        db.update_project_status(project_id, DialougeStatus.FAILED)
        return {"project_id": project_id, "uploaded": False, "error": str(e)}


def upload_completed_projects() -> Dict:
    db = DBOperation()
    projects = db.get_projects_by_status(DialougeStatus.COMPLETED)
    if not projects:
        return {"attempted": 0, "uploaded": 0, "failed": 0, "results": []}
    try:
        cl = _login_client()
    except Exception as e:
        # If login fails, mark all as failed without attempting uploads
        results = [{"project_id": p['id'], "uploaded": False, "error": f"login failed: {e}"} for p in projects]
        return {"attempted": len(projects), "uploaded": 0, "failed": len(projects), "results": results}

    uploaded = 0
    failed = 0
    results: List[Dict] = []
    for p in projects:
        pid = p['id']
        video_path = p.get('video_path')
        if not video_path or not os.path.isfile(video_path):
            failed += 1
            results.append({"project_id": pid, "uploaded": False, "error": f"Video not found: {video_path}"})
            continue
        try:
            caption = _build_caption(p)
            thumb = _build_thumbnail(p)
            media = cl.clip_upload(video_path, caption=caption, thumbnail=thumb)
            DBOperation().update_project_status(pid, DialougeStatus.UPLOADED)
            uploaded += 1
            results.append({"project_id": pid, "uploaded": True, "media_id": getattr(media, 'pk', None)})
        except Exception as e:
            DBOperation().update_project_status(pid, DialougeStatus.FAILED)
            failed += 1
            results.append({"project_id": pid, "uploaded": False, "error": str(e)})

    return {"attempted": len(projects), "uploaded": uploaded, "failed": failed, "results": results}
