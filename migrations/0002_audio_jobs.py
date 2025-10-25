"""Migration 0002: Introduce audio_jobs table for internal Higgs inference pipeline.

Idempotent creation + column adds so it can run safely multiple times.
"""
from db_handler import DBOperation
import sqlite3
from logging import getLogger

logger = getLogger(__name__)

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audio_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT NOT NULL,
    voice TEXT,
    request_payload TEXT NOT NULL,
    status TEXT NOT NULL,
    output_path TEXT,
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

ADD_COLUMNS = [
    # (column_name, alter_sql)
]

INDEXES = [
    ("idx_audio_jobs_status", "CREATE INDEX IF NOT EXISTS idx_audio_jobs_status ON audio_jobs(status);"),
    ("idx_audio_jobs_user_status", "CREATE INDEX IF NOT EXISTS idx_audio_jobs_user_status ON audio_jobs(user_id, status);")
]

def column_exists(cur, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table});")
    return any(r[1] == col for r in cur.fetchall())

def run(db: DBOperation):
    conn = None
    try:
        conn = db.connect(); cur = conn.cursor()
        cur.execute(TABLE_SQL)
        # Future-proof column adds
        for col, sql in ADD_COLUMNS:
            if not column_exists(cur, 'audio_jobs', col):
                cur.execute(sql)
        # Indexes
        for name, sql in INDEXES:
            try:
                cur.execute(sql)
            except sqlite3.Error as ie:
                logger.warning(f"Index {name} creation warning: {ie}")
        conn.commit()
    except Exception as e:
        logger.error(f"Migration 0002_audio_jobs failed: {e}")
    finally:
        try:
            if conn: conn.close()
        except Exception:
            pass
