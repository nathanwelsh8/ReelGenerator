"""Deprecated legacy audio worker.

All functionality replaced by `higgs_infer_worker` using TOPIC_HIGGS_AUDIO_JOBS.
This file is intentionally inert and will be removed in a future cleanup.
"""

if __name__ == "__main__":
    raise SystemExit("audio_worker deprecated. Use higgs_infer_worker instead.")
