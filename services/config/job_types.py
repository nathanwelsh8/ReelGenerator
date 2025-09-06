class JOB_TYPES:
    PROJECT_DIALOGUE = "project_dialogue"
    CHARACTER_FOLLOW = "character_follow"

    @classmethod
    def get_jobs(cls):
        return [cls.PROJECT_DIALOGUE, cls.CHARACTER_FOLLOW]