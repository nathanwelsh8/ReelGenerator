from typing import TypedDict


class _AudioJobOptional(TypedDict, total=False):
    project_id: int
    dialogue_id: int
    character_id: int
    audio_job_id: int  # reference to internal audio_jobs row (Higgs pipeline)


class AudioJob(_AudioJobOptional):
    job_type: str  # see services.config.job_types.JOB_TYPES
    sentence: str
    character: str


TOPIC_HIGGS_AUDIO_JOBS = "higgs.audio.jobs"  # unified Higgs inference queue


class VideoJob(TypedDict):
    project_id: int
    # Optional future fields (e.g., background selection) can be added here


TOPIC_VIDEO_JOBS = "video.jobs"
