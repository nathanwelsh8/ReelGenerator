from fastapi import APIRouter

from .audio_jobs import router as audio_jobs_router
from .dialogues import router as dialogues_router
from .projects import router as projects_router

router = APIRouter(prefix="/internal", tags=["internal"])
router.include_router(audio_jobs_router)
router.include_router(dialogues_router)
router.include_router(projects_router)
