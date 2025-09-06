#!/usr/bin/env bash
set -euo pipefail

# Start API and Worker in parallel for dev container

export PYTHONUNBUFFERED=1

echo "[dev] Starting audio worker"
python workers/audio_worker.py &
WORKER_PID=$!

echo "[dev] Starting video worker"
python workers/video_worker.py &
VIDEO_WORKER_PID=$!

trap 'echo "[dev] Stopping..."; kill $WORKER_PID $VIDEO_WORKER_PID 2>/dev/null || true; wait $WORKER_PID $VIDEO_WORKER_PID 2>/dev/null || true' EXIT

wait $WORKER_PID $VIDEO_WORKER_PID
