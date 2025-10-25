class JOB_TYPES:
    HIGGS_DIALOGUE = "higgs_dialogue"  # Dialogue audio generation via Higgs
    HIGGS_FOLLOW = "higgs_follow"      # Character follow-line generation via Higgs

    @classmethod
    def get_jobs(cls):
        return [cls.HIGGS_DIALOGUE, cls.HIGGS_FOLLOW]