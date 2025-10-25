from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.config.logging_config import configure_logging
from logging import getLogger
import sqlite3
from migrations.runner import run_all_migrations
from settings import get_settings

def create_app() -> FastAPI:
    
    configure_logging()
    logger = getLogger("app")

    app = FastAPI(title="Brainrot Factory API", version="0.1.0", swagger_ui_init_oauth={
        
    })

    # Run migrations (idempotent) before route registration
    settings = get_settings()
    # Log which DB file is being used in this runtime (helps local vs container)
    logger.info(f"Using DB at: {settings.DB_PATH}")
    try:
        run_all_migrations(db_path=settings.DB_PATH)
    except Exception as e:
        logger.error(f"Migration execution failed: {e}")
    
    # CORS (dev-friendly defaults; tighten in prod)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routes.health import router as health_router
    from .routes.auth import router as auth_router
    from .routes.characters import router as characters_router
    from .routes.projects import router as projects_router
    from .routes.dialogues import router as dialogues_router
    from .routes.internal import router as internal_router
    from .routes.process import router as process_router
    from .routes.upload import router as upload_router

    app.include_router(health_router, prefix="/health", tags=["health"]) 
    app.include_router(auth_router)  # /auth prefix inside router
    app.include_router(characters_router, prefix="/characters", tags=["characters"]) 
    app.include_router(projects_router, prefix="/projects", tags=["projects"]) 
    app.include_router(dialogues_router, prefix="/dialogues", tags=["dialogues"]) 
    app.include_router(process_router, prefix="/process", tags=["process"])
    app.include_router(upload_router, prefix="/upload", tags=["upload"]) 
    app.include_router(internal_router)

    logger.info("Application started")
    return app

app = create_app()