from typing import TypedDict, NotRequired


class AudioJob(TypedDict):
    job_type: str  # see services.config.job_types.JOB_TYPES
    project_id: NotRequired[int]
    dialogue_id: NotRequired[int]
    sentence: str
    character: str
    character_id: NotRequired[int]


TOPIC_AUDIO_JOBS = "audio.jobs"


class VideoJob(TypedDict):
    project_id: int
    # Optional future fields (e.g., background selection) can be added here


TOPIC_VIDEO_JOBS = "video.jobs"
