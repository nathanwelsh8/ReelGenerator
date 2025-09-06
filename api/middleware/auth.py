from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Callable, Awaitable
from ..routes.auth import decode_session

# Paths that are allowed without authentication (besides /auth/* and root /)
ALLOW_UNAUTH = {"/health", "/docs", "/openapi.json"}

async def auth_middleware(request: Request, call_next: Callable[[Request], Awaitable]):
    path = request.url.path
    # Public endpoints: root, auth routes, explicitly allowed paths
    if path == "/" or any(path.startswith(p) for p in ("/auth",)) or path in ALLOW_UNAUTH:
        return await call_next(request)
    # Static audio assets bypass
    if path.startswith('/audio_assests'):
        return await call_next(request)

    token = request.cookies.get('session')
    if not token:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    try:
        decode_session(token)
    except Exception:
        return JSONResponse({"detail": "Invalid session"}, status_code=401)
    return await call_next(request)
