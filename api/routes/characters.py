from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from services.character_service import CharacterService
from db_handler import DBOperation
from api.schemas import CharacterCreate, CharacterUpdate, CharacterOut
from api.routes.auth import get_current_user

router = APIRouter()
cs = CharacterService()
db = cs.db if isinstance(cs.db, DBOperation) else DBOperation()


@router.get("/", response_model=List[CharacterOut])
def list_characters(user=Depends(get_current_user)):
    # Filter characters by user ownership
    chars = db.get_characters(active_only=True, user_id=user.get('id'))
    return [CharacterOut(**{
        'id': c['id'],
        'name': c['name'],
        'image_path': c['image_path'],
        'parrot_ai_path': c['parrot_ai_path'],
        'follow_line': c.get('follow_line'),
        'follow_line_audio': c.get('follow_line_audio'),
        'active': bool(c['active'])
    }) for c in chars]


@router.post("/", response_model=int)
def create_character(payload: CharacterCreate, user=Depends(get_current_user)):
    # Enforce unique name
    cs.ensure_unique_name(payload.name)
    new_id = db.create_character(
        name=payload.name,
        parrot_ai_path=payload.parrot_ai_path,
        image_filename=payload.image_filename,
        active=1 if payload.active else 0,
        follow_line=payload.follow_line,
        follow_line_audio=payload.follow_line_audio,
    user_id=user.get('id')
    )
    if not new_id:
        raise HTTPException(status_code=400, detail="Failed to create character")
    return int(new_id)


@router.patch("/{character_id}")
def update_character(character_id: int, payload: CharacterUpdate, user=Depends(get_current_user)):
    ch = db.get_character_by_id(character_id)
    if not ch or ch.get('user_id') != user.get('id'):
        raise HTTPException(status_code=404, detail="Character not found")
    ok = db.update_character(
        character_id,
        parrot_ai_path=payload.parrot_ai_path,
        image_filename=payload.image_filename,
        active=(1 if payload.active else 0) if payload.active is not None else None,
        follow_line=payload.follow_line,
        follow_line_audio=payload.follow_line_audio,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"updated": True}


@router.delete("/{character_id}")
def delete_character(character_id: int, user=Depends(get_current_user)):
    ch = db.get_character_by_id(character_id)
    if not ch or ch.get('user_id') != user.get('id'):
        raise HTTPException(status_code=404, detail="Character not found")
    # Prevent deletion if character used in active projects
    if db.character_has_active_projects(character_id):
        raise HTTPException(status_code=409, detail="Character is used in active projects")
    ok = db.delete_character(character_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"deleted": True}


@router.post("/{character_id}/follow-audio", status_code=status.HTTP_202_ACCEPTED)
def enqueue_follow_audio(character_id: int, user=Depends(get_current_user)):
    ch = db.get_character_by_id(character_id)
    if not ch or ch.get('user_id') != user.get('id'):
        raise HTTPException(status_code=404, detail="Character not found")
    path = cs.generate_follow_audio(character_id, overwrite=False)
    return {"enqueued": True, "target_path": path}
