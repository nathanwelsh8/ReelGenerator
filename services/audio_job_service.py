"""Service layer for audio_jobs table.

Abstraction over raw sqlite operations to be reused by API routes and workers.
"""
from __future__ import annotations
import json
import sqlite3
from typing import Any, Dict, List, Optional
from logging import getLogger

from db_handler import DBOperation
from utils import AudioJobStatus

logger = getLogger(__name__)

VALID_STATUSES = {
    AudioJobStatus.QUEUED,
    AudioJobStatus.IN_PROGRESS,
    AudioJobStatus.COMPLETED,
    AudioJobStatus.FAILED,
}

class AudioJobService:
    def __init__(self, db: DBOperation | None = None):
        self.db = db or DBOperation()

    # Internal helpers
    def _row_to_dict(self, row) -> Dict[str, Any]:
        if not row:
            return {}
        return {
            "id": row[0],
            "user_id": row[1],
            "text": row[2],
            "voice": row[3],
            "request_payload": json.loads(row[4]) if row[4] else None,
            "status": row[5],
            "output_path": row[6],
            "error": row[7],
            "created_at": row[8],
            "updated_at": row[9],
        }

    # Exceptions
    class JobNotFoundError(LookupError):
        """Raised when an audio job id does not exist."""

    class JobStateConflictError(RuntimeError):
        """Raised when the job is not in an expected state for the requested transition."""

    # Public methods
    def create_job(self, *, text: str, voice: str | None, user_id: int | None, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("text is required")
        payload_json = json.dumps(payload, ensure_ascii=False)
        conn = self.db.connect(); cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO audio_jobs (user_id, text, voice, request_payload, status) VALUES (?, ?, ?, ?, ?)",
                (user_id, text.strip(), voice, payload_json, AudioJobStatus.QUEUED)
            )
            job_id = cur.lastrowid
            conn.commit()
            cur.execute("SELECT * FROM audio_jobs WHERE id = ?", (job_id,))
            return self._row_to_dict(cur.fetchone())
        except sqlite3.Error as e:
            logger.error(f"create_job error: {e}")
            raise
        finally:
            try: conn.close()
            except Exception: pass

    def get_job(self, job_id: int | str, user_id: int | None = None) -> Optional[Dict[str, Any]]:
        # Coerce to int if a string is provided
        try:
            job_id_int = int(job_id)
        except Exception:
            return None
        conn = self.db.connect(); cur = conn.cursor()
        try:
            if user_id is not None:
                cur.execute("SELECT * FROM audio_jobs WHERE id = ? AND (user_id = ? OR user_id IS NULL)", (job_id_int, user_id))
            else:
                cur.execute("SELECT * FROM audio_jobs WHERE id = ?", (job_id_int,))
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"get_job error: {e}")
            return None
        finally:
            try: conn.close()
            except Exception: pass

    def claim_job(self, job_id: int) -> Dict[str, Any]:
        """Atomically transition a QUEUED job to IN_PROGRESS and return the updated row.

        Raises:
            JobNotFoundError: if the job id does not exist.
            JobStateConflictError: if the job is not currently QUEUED.
        """
        conn = self.db.connect(); cur = conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE;")
            cur.execute("SELECT * FROM audio_jobs WHERE id = ?;", (job_id,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                raise AudioJobService.JobNotFoundError(f"audio_job_id {job_id} not found")
            status = row[5]
            if status != AudioJobStatus.QUEUED:
                conn.rollback()
                raise AudioJobService.JobStateConflictError(
                    f"audio_job_id {job_id} expected status QUEUED, found {status}"
                )
            cur.execute(
                "UPDATE audio_jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (AudioJobStatus.IN_PROGRESS, job_id)
            )
            conn.commit()
            cur.execute("SELECT * FROM audio_jobs WHERE id = ?;", (job_id,))
            updated = cur.fetchone()
            return self._row_to_dict(updated)
        except sqlite3.Error as e:
            logger.error(f"claim_job error: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def list_jobs(self, *, user_id: int | None, status: str | None = None, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 200))
        conn = self.db.connect(); cur = conn.cursor()
        try:
            clauses = []
            params: list[Any] = []
            if user_id is not None:
                clauses.append("(user_id = ? OR user_id IS NULL)")
                params.append(user_id)
            if status:
                clauses.append("status = ?")
                params.append(status)
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            sql = f"SELECT * FROM audio_jobs{where} ORDER BY id DESC LIMIT ?";
            params.append(limit)
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [self._row_to_dict(r) for r in rows]
        except sqlite3.Error as e:
            logger.error(f"list_jobs error: {e}")
            return []
        finally:
            try: conn.close()
            except Exception: pass

    def find_latest_for_dialogue(self, dialogue_id: int) -> Optional[Dict[str, Any]]:
        """Return the most recent audio_job row that references the dialogue_id in request_payload.

        Uses SQLite json_extract if available; falls back to LIKE search.
        """
        conn = self.db.connect(); cur = conn.cursor()
        try:
            try:
                # Prefer JSON-aware query
                cur.execute(
                    "SELECT * FROM audio_jobs WHERE json_extract(request_payload, '$.dialogue_id') = ? ORDER BY id DESC LIMIT 1;",
                    (dialogue_id,)
                )
                row = cur.fetchone()
            except Exception:
                # Fallback: LIKE search
                like = f'%"dialogue_id": {dialogue_id}%'  # basic pattern
                cur.execute(
                    "SELECT * FROM audio_jobs WHERE request_payload LIKE ? ORDER BY id DESC LIMIT 1;",
                    (like,)
                )
                row = cur.fetchone()
            return self._row_to_dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"find_latest_for_dialogue error: {e}")
            return None
        finally:
            try: conn.close()
            except Exception: pass

    def update_status(self, job_id: int, status: str, *, output_path: str | None = None, error: str | None = None) -> bool:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status {status}")
        conn = self.db.connect(); cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE audio_jobs SET status = ?, output_path = COALESCE(?, output_path), error = COALESCE(?, error), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, output_path, error, job_id)
            )
            conn.commit()
            return cur.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"update_status error: {e}")
            return False
        finally:
            try: conn.close()
            except Exception: pass

    def mark_failed(self, job_id: int, error: str) -> bool:
        return self.update_status(job_id, AudioJobStatus.FAILED, error=(error[:500] if error else ''))

    def reserve_next_queued(self) -> Optional[Dict[str, Any]]:
        """Atomically fetch next QUEUED job and mark IN_PROGRESS.

        This is an alternative to queue-based consumption, can be used for polling workers.
        """
        conn = self.db.connect(); cur = conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE;")
            cur.execute("SELECT * FROM audio_jobs WHERE status = ? ORDER BY id ASC LIMIT 1;", (AudioJobStatus.QUEUED,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return None
            job_id = row[0]
            cur.execute("UPDATE audio_jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (AudioJobStatus.IN_PROGRESS, job_id))
            conn.commit()
            return self._row_to_dict(row)
        except sqlite3.Error as e:
            logger.error(f"reserve_next_queued error: {e}")
            try: conn.rollback()
            except Exception: pass
            return None
        finally:
            try: conn.close()
            except Exception: pass
