"""Internal-facing audio job service used by worker API routes."""

from __future__ import annotations

from typing import Dict, Optional

from logging import getLogger

from services.audio_job_service import AudioJobService
from utils import AudioJobStatus

logger = getLogger(__name__)


class InternalAudioJobService:
    def __init__(self, job_service: AudioJobService | None = None):
        self.job_service = job_service or AudioJobService()

    def claim(self, job_id: int) -> Dict:
        """Transition a queued job to in-progress and return its payload."""
        return self.job_service.claim_job(job_id)

    def update_status(
        self,
        job_id: int,
        *,
        status: str,
        output_path: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Dict:
        if status not in {AudioJobStatus.QUEUED, AudioJobStatus.IN_PROGRESS, AudioJobStatus.COMPLETED, AudioJobStatus.FAILED}:
            raise ValueError(f"Unsupported audio job status: {status}")
        updated = self.job_service.update_status(job_id, status, output_path=output_path, error=error)
        if not updated:
            raise AudioJobService.JobNotFoundError(f"audio_job_id {job_id} not found")
        snapshot = self.job_service.get_job(job_id)
        if not snapshot:
            raise AudioJobService.JobNotFoundError(f"audio_job_id {job_id} not found after update")
        return snapshot

    def mark_failed(self, job_id: int, error: Optional[str]) -> Dict:
        message = (error or "")[:500] if error else None
        updated = self.job_service.mark_failed(job_id, message or "")
        if not updated:
            raise AudioJobService.JobNotFoundError(f"audio_job_id {job_id} not found")
        snapshot = self.job_service.get_job(job_id)
        if not snapshot:
            raise AudioJobService.JobNotFoundError(f"audio_job_id {job_id} not found after failure update")
        return snapshot

    def get(self, job_id: int) -> Dict:
        job = self.job_service.get_job(job_id)
        if not job:
            raise AudioJobService.JobNotFoundError(f"audio_job_id {job_id} not found")
        return job
