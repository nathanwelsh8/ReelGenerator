"""Initial schema and idempotent migration helpers extracted from DBOperation.__init__.
Run via: from migrations.runner import run_all_migrations()
"""
from db_handler import DBOperation
import sqlite3
from logging import getLogger

logger = getLogger(__name__)

def run(db: DBOperation):
    conn = None
    try:
        # Recreate logic formerly in methods (kept idempotent)
        db.create_projects_table()
        db.create_dialouge_stage_table()
        # characters table
        try:
            conn = db.connect(); cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                image_path TEXT NOT NULL,
                parrot_ai_path TEXT NOT NULL UNIQUE,
                active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()
        finally:
            try: conn.close()
            except Exception: pass
        # follow columns
        try:
            conn = db.connect(); cur = conn.cursor()
            cur.execute("PRAGMA table_info(characters);")
            cols = [r[1] for r in cur.fetchall()]
            if 'follow_line' not in cols:
                cur.execute("ALTER TABLE characters ADD COLUMN follow_line TEXT;")
            if 'follow_line_audio' not in cols:
                cur.execute("ALTER TABLE characters ADD COLUMN follow_line_audio TEXT;")
            conn.commit()
        finally:
            try: conn.close()
            except Exception: pass
        # unique index on name (case-insensitive)
        try:
            conn = db.connect(); cur = conn.cursor()
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_characters_name_nocase ON characters(name COLLATE NOCASE);")
            conn.commit()
        finally:
            try: conn.close()
            except Exception: pass
        # project speaker columns
        try:
            conn = db.connect(); cur = conn.cursor()
            cur.execute("PRAGMA table_info(projects);")
            cols = [r[1] for r in cur.fetchall()]
            if 'speaker1_id' not in cols:
                cur.execute("ALTER TABLE projects ADD COLUMN speaker1_id INTEGER;")
            if 'speaker2_id' not in cols:
                cur.execute("ALTER TABLE projects ADD COLUMN speaker2_id INTEGER;")
            conn.commit()
        finally:
            try: conn.close()
            except Exception: pass
        # dialogue character_id column
        try:
            conn = db.connect(); cur = conn.cursor()
            cur.execute("PRAGMA table_info(dialouge_stage);")
            cols = [r[1] for r in cur.fetchall()]
            if 'character_id' not in cols:
                cur.execute("ALTER TABLE dialouge_stage ADD COLUMN character_id INTEGER;")
                conn.commit()
        finally:
            try: conn.close()
            except Exception: pass
        # users table
        try:
            conn = db.connect(); cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                google_sub TEXT NOT NULL UNIQUE,
                email TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()
        finally:
            try: conn.close()
            except Exception: pass
        # multi-tenancy user_id columns
        for (table,) in [("projects",), ("characters",)]:
            try:
                conn = db.connect(); cur = conn.cursor()
                cur.execute(f"PRAGMA table_info({table});")
                cols = [r[1] for r in cur.fetchall()]
                if 'user_id' not in cols:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER;")
                    conn.commit()
            finally:
                try: conn.close()
                except Exception: pass
        # seed characters
        seeds = [
            {"name": "Peter Griffin", "image_path": "peter.png", "parrot_ai_path": "peter-griffin", "follow_line": "If you wanna see more of this genius stuff, follow Professor Peter Griffin. Do it. Do it now.", "follow_line_audio": "audio_assests/static/peter_follow_for_more.mp3"},
            {"name": "Stewie Griffin", "image_path": "stewie.png", "parrot_ai_path": "stewie-griffin", "follow_line": "I'll be monitoring your future transmissions. Consider yourself 'followed'.", "follow_line_audio": "audio_assests/static/stewie_follow_for_more.mp3"},
        ]
        try:
            conn = db.connect(); cur = conn.cursor()
            for s in seeds:
                cur.execute(
                    "INSERT OR IGNORE INTO characters (name, image_path, parrot_ai_path, follow_line, follow_line_audio) VALUES (?, ?, ?, ?, ?);",
                    (s['name'], s['image_path'], s['parrot_ai_path'], s['follow_line'], s['follow_line_audio'])
                )
                cur.execute(
                    "UPDATE characters SET follow_line = COALESCE(follow_line, ?), follow_line_audio = COALESCE(follow_line_audio, ?) WHERE name = ?;",
                    (s['follow_line'], s['follow_line_audio'], s['name'])
                )
            conn.commit()
        finally:
            try: conn.close()
            except Exception: pass
        # ensure project_id column on dialogues
        try:
            conn = db.connect(); cur = conn.cursor()
            cur.execute("PRAGMA table_info(dialouge_stage);")
            cols = [r[1] for r in cur.fetchall()]
            if 'project_id' not in cols:
                cur.execute("ALTER TABLE dialouge_stage ADD COLUMN project_id INTEGER;")
                conn.commit()
        finally:
            try: conn.close()
            except Exception: pass
        # dialogue uniqueness migration (reuse existing method)
        db._ensure_dialogue_uniqueness()
        # backfill user ids
        try:
            conn = db.connect(); cur = conn.cursor()
            cur.execute("UPDATE projects SET user_id = 1 WHERE user_id IS NULL;")
            cur.execute("UPDATE characters SET user_id = 1 WHERE user_id IS NULL;")
            conn.commit()
        finally:
            try: conn.close()
            except Exception: pass
    except Exception as e:
        logger.error(f"Migration 0001 failed: {e}")
