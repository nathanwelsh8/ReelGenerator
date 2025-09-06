from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from services.config.logging_config import configure_logging
from logging import getLogger

from .middleware.auth import auth_middleware  # type: ignore
from .routes.health import router as health_router
from .routes.auth import router as auth_router  # helpers consumed in middleware
from .routes.characters import router as characters_router
from .routes.projects import router as projects_router
from .routes.dialogues import router as dialogues_router
from .routes.process import router as process_router
from .routes.upload import router as upload_router

def create_app() -> FastAPI:
    
    configure_logging()
    logger = getLogger("app")

    app = FastAPI(title="Brainrot Factory API", version="0.1.0")

    # CORS (restrict to configured frontend origins when using credentials)
    from settings import get_settings
    _settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_settings.FRONTEND_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(auth_router)  # /auth public endpoints
    app.include_router(health_router, prefix="/health", tags=["health"])  # public
    app.include_router(characters_router, prefix="/characters", tags=["characters"]) 
    app.include_router(projects_router, prefix="/projects", tags=["projects"]) 
    app.include_router(dialogues_router, prefix="/dialogues", tags=["dialogues"]) 
    app.include_router(process_router, prefix="/process", tags=["process"]) 
    app.include_router(upload_router, prefix="/upload", tags=["upload"]) 

    
    app.middleware("http")(auth_middleware)

    # Serve generated audio files (mounted without /api prefix; proxy should forward /api/* to this app)
    try:
        app.mount('/audio_assests', StaticFiles(directory='audio_assests'), name='audio_assests')
    except Exception as e:  # defensive: don't crash app if directory missing
        logger.warning(f"Could not mount /audio_assests: {e}")

    logger.info("Application started")
    return app

app = create_app()