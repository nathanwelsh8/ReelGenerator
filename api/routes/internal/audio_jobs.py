from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from api.schemas import (
    AudioJobOut,
    AudioJobStatusUpdate,
    AudioJobFailRequest,
)
from services.audio_job_service import AudioJobService
from services.internal.audio_jobs import InternalAudioJobService

router = APIRouter(prefix="/audio-jobs", tags=["internal-audio-jobs"])


def get_service() -> InternalAudioJobService:
    return InternalAudioJobService()


@router.post("/{job_id}/claim", response_model=AudioJobOut)
async def claim_audio_job(job_id: int, service: InternalAudioJobService = Depends(get_service)):
    try:
        job = await run_in_threadpool(service.claim, job_id)
        return job
    except AudioJobService.JobNotFoundError as exc:  # type: ignore[attr-defined]
        raise HTTPException(status_code=404, detail=str(exc))
    except AudioJobService.JobStateConflictError as exc:  # type: ignore[attr-defined]
        raise HTTPException(status_code=409, detail=str(exc))


@router.patch("/{job_id}", response_model=AudioJobOut)
async def update_audio_job(
    job_id: int,
    payload: AudioJobStatusUpdate,
    service: InternalAudioJobService = Depends(get_service),
):
    try:
        job = await run_in_threadpool(
            service.update_status,
            job_id,
            status=payload.status,
            output_path=payload.output_path,
            error=payload.error,
        )
        return job
    except AudioJobService.JobNotFoundError as exc:  # type: ignore[attr-defined]
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{job_id}/fail", response_model=AudioJobOut)
async def fail_audio_job(
    job_id: int,
    payload: AudioJobFailRequest,
    service: InternalAudioJobService = Depends(get_service),
):
    try:
        job = await run_in_threadpool(service.mark_failed, job_id, payload.error)
        return job
    except AudioJobService.JobNotFoundError as exc:  # type: ignore[attr-defined]
        raise HTTPException(status_code=404, detail=str(exc))
