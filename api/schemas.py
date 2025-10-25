from datetime import datetime
from typing import Optional, List, Dict
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


class AudioJobOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    text: str
    voice: Optional[str] = None
    request_payload: Optional[Dict] = None
    status: str
    output_path: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AudioJobStatusUpdate(BaseModel):
    status: str = Field(..., description="New status for the audio job")
    output_path: Optional[str] = Field(default=None, description="Relative path to synthesized audio")
    error: Optional[str] = Field(default=None, description="Optional error message when marking failed")


class AudioJobFailRequest(BaseModel):
    error: Optional[str] = Field(default=None, description="Error details to persist when marking job failed")


class DialogueAudioUpdate(BaseModel):
    audio_path: str = Field(..., description="Relative path to generated audio asset")


class DialogueStatusUpdate(BaseModel):
    status: str = Field(..., description="New dialogue status")


class ProjectSnapshot(BaseModel):
    id: int
    title: str
    caption: str
    pdf_url: str
    status: str
    video_path: Optional[str] = None
    speaker1_id: Optional[int] = None
    speaker2_id: Optional[int] = None
    user_id: Optional[int] = None


class ProjectDialogueList(BaseModel):
    project_id: int
    total: int
    completed: int
    dialogues: List[DialogueOut]


class ProjectStatusTransition(BaseModel):
    expected: str = Field(..., description="Status required before applying transition")
    next: str = Field(..., description="Status to set when expected matches")


class ProjectVideoPathUpdate(BaseModel):
    video_path: str = Field(..., description="Absolute or relative output video path")
