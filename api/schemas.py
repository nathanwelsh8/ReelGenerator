from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl


class ProjectCreate(BaseModel):
    title: str = Field(..., max_length=256)
    caption: str = Field(..., max_length=1000)
    pdf_url: HttpUrl
    speaker1_id: Optional[int] = None
    speaker2_id: Optional[int] = None


class ProjectOut(BaseModel):
    id: int
    title: str
    caption: str
    pdf_url: str
    status: str
    video_path: Optional[str] = None
    speaker1_id: Optional[int] = None
    speaker2_id: Optional[int] = None


class CharacterCreate(BaseModel):
    name: str
    parrot_ai_path: str
    image_filename: str
    active: bool = True
    follow_line: Optional[str] = Field(default=None, max_length=100)
    follow_line_audio: Optional[str] = None


class CharacterUpdate(BaseModel):
    parrot_ai_path: Optional[str] = None
    image_filename: Optional[str] = None
    active: Optional[bool] = None
    follow_line: Optional[str] = Field(default=None, max_length=100)
    follow_line_audio: Optional[str] = None


class CharacterOut(BaseModel):
    id: int
    name: str
    image_path: str
    parrot_ai_path: str
    active: int
    follow_line: Optional[str] = None
    follow_line_audio: Optional[str] = None


class DialogueOut(BaseModel):
    id: int
    sentence: str
    character: str
    image: Optional[str] = None
    image_search: Optional[str] = None
    audio: Optional[str] = None
    status: str
    character_id: Optional[int] = None
