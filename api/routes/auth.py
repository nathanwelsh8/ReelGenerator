from fastapi import APIRouter, HTTPException, Response, Depends, Request
from pydantic import BaseModel
from typing import Optional
import os, time
from jose import jwt, JWTError
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from db_handler import DBOperation

from settings import get_settings
_settings = get_settings()
GOOGLE_CLIENT_ID = _settings.GOOGLE_CLIENT_ID
SESSION_SECRET = _settings.SESSION_SECRET
SESSION_ALG = _settings.SESSION_ALG
SESSION_TTL = _settings.SESSION_TTL

db = DBOperation()
router = APIRouter(prefix="/auth", tags=["auth"])

class GoogleAuthIn(BaseModel):
    id_token: str

class UserOut(BaseModel):
    id: int
    email: Optional[str] = None
    name: Optional[str] = None  # transient from session claims


def verify_google_token(token: str):
    try:
        payload = id_token.verify_oauth2_token(token, grequests.Request(), GOOGLE_CLIENT_ID)
        # Basic checks
        if payload.get('aud') != GOOGLE_CLIENT_ID:
            raise ValueError('Invalid audience')
        return payload
    except Exception as e:  # broad for clarity to caller
        raise HTTPException(status_code=401, detail=f'Invalid Google token: {e}')


def create_session_jwt(user_id: int, email: str | None, name: str | None):
    now = int(time.time())
    payload = {"sub": str(user_id), "email": email, "name": name, "iat": now, "exp": now + SESSION_TTL}
    return jwt.encode(payload, SESSION_SECRET, algorithm=SESSION_ALG)


def decode_session(token: str):
    try:
        data = jwt.decode(token, SESSION_SECRET, algorithms=[SESSION_ALG])
        return data
    except JWTError:
        raise HTTPException(status_code=401, detail='Invalid session')


def get_current_user(request: Request):
    tok = request.cookies.get('session')
    if not tok:
        raise HTTPException(status_code=401, detail='Not authenticated')
    sess = decode_session(tok)
    user = db.get_user_by_id(int(sess.get('sub')))
    if not user:
        raise HTTPException(status_code=401, detail='User not found')
    # Merge transient claims
    return {**user, 'email': sess.get('email'), 'name': sess.get('name')}

@router.post('/google', response_model=UserOut)
def google_login(payload: GoogleAuthIn, response: Response):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail='Server missing GOOGLE_CLIENT_ID')
    gp = verify_google_token(payload.id_token)
    user = db.upsert_user_google(
        sub=gp.get('sub'),
        email=gp.get('email')
    )
    if not user:
        raise HTTPException(status_code=500, detail='Failed to persist user')
    sess = create_session_jwt(user['id'], gp.get('email'), gp.get('name'))
    # Secure flag left off for dev (localhost); set via proxy in prod
    response.set_cookie('session', sess, httponly=True, samesite='lax', path='/')
    return { 'id': user['id'], 'email': gp.get('email'), 'name': gp.get('name') }

@router.get('/me', response_model=UserOut)
def me(user=Depends(get_current_user)):
    return { 'id': user.get('id'), 'email': user.get('email'), 'name': user.get('name') }

@router.post('/logout')
def logout(response: Response):
    response.delete_cookie('session', path='/')
    return {"ok": True}
