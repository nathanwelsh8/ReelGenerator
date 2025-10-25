from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from api.schemas import DialogueAudioUpdate, DialogueStatusUpdate
from services.internal.dialogues import InternalDialogueService, DialogueNotFoundError

router = APIRouter(prefix="/dialogues", tags=["internal-dialogues"])


def get_service() -> InternalDialogueService:
    return InternalDialogueService()


@router.patch("/{dialogue_id}/audio", status_code=status.HTTP_204_NO_CONTENT)
async def set_dialogue_audio(
    dialogue_id: int,
    payload: DialogueAudioUpdate,
    service: InternalDialogueService = Depends(get_service),
):
    try:
        await run_in_threadpool(service.update_audio_path, dialogue_id, payload.audio_path)
    except DialogueNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{dialogue_id}/status", status_code=status.HTTP_204_NO_CONTENT)
async def set_dialogue_status(
    dialogue_id: int,
    payload: DialogueStatusUpdate,
    service: InternalDialogueService = Depends(get_service),
):
    try:
        await run_in_threadpool(service.update_status, dialogue_id, payload.status)
    except DialogueNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
