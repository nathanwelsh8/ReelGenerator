import sqlite3
import time
from utils import DialougeStatus

from logging import getLogger

logger = getLogger(__name__)

class DBOperation:
    def __init__(self, db_name: str | None = None):
        """Lightweight initializer. Schema handled via migrations.

        Prefers explicit db_name argument; falls back to settings.DB_PATH so
        containerized services (API & workers) can share a mounted volume.
        """
        if db_name is not None:
            self.db_name = db_name
        else:
            try:
                from settings import get_settings  # local import to avoid cycles
                self.db_name = get_settings().DB_PATH or "stewie_database.db"
            except Exception:
                self.db_name = "stewie_database.db"

    def connect(self):
        conn = sqlite3.connect(self.db_name, timeout=30, check_same_thread=False)
        try:
            # Improve concurrency for readers/writers
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")  # milliseconds
            conn.execute("PRAGMA synchronous=NORMAL;")
        except sqlite3.Error:
            pass
        return conn

    def create_projects_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(256) NOT NULL,
            caption VARCHAR(1000) NOT NULL,
            pdf_url TEXT NOT NULL,
            status TEXT DEFAULT 'NEW',
            video_path TEXT
        );
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            logger.info("Table 'projects' is ready.")
        except sqlite3.Error as e:
            logger.critical(f"SQLite error during projects table creation: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
    
    # --- New multi-character schema helpers ---

    # (Schema / ensure / seed helpers moved to migrations modules)

    # --- Users / Auth ---
    # _ensure_users_table moved to migrations

    def upsert_user_google(self, sub: str, email: str | None):
        """Insert or update a Google user and return row dict."""
        try:
            conn = self.connect(); cur = conn.cursor()
            cur.execute("SELECT id, google_sub, email, created_at FROM users WHERE google_sub = ?", (sub,))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE users SET email = COALESCE(?, email) WHERE google_sub = ?", (email, sub))
                conn.commit()
                cur.execute("SELECT id, google_sub, email, created_at FROM users WHERE google_sub = ?", (sub,))
                row = cur.fetchone()
            else:
                cur.execute("INSERT INTO users (google_sub, email) VALUES (?, ?)", (sub, email))
                conn.commit()
                cur.execute("SELECT id, google_sub, email, created_at FROM users WHERE google_sub = ?", (sub,))
                row = cur.fetchone()
            if not row:
                return None
            return {"id": row[0], "google_sub": row[1], "email": row[2], "created_at": row[3]}
        except sqlite3.Error as e:
            logger.error(f"SQLite upsert user error: {e}")
            return None
        finally:
            try: conn.close()
            except Exception: pass

    def get_user_by_id(self, user_id: int):
        try:
            conn = self.connect(); cur = conn.cursor()
            cur.execute("SELECT id, google_sub, email, created_at FROM users WHERE id = ?", (user_id,))
            r = cur.fetchone()
            if not r: return None
            return {"id": r[0], "google_sub": r[1], "email": r[2], "created_at": r[3]}
        except sqlite3.Error as e:
            logger.error(f"SQLite get_user_by_id error: {e}")
            return None
        finally:
            try: conn.close()
            except Exception: pass

    # --- Character accessors ---
    def get_characters(self, active_only=True, user_id: int | None = None):
        try:
            conn = self.connect()
            cur = conn.cursor()
            base_select = "SELECT id, name, image_path, parrot_ai_path, follow_line, follow_line_audio, active, user_id FROM characters"
            clauses = []
            params: list = []
            if active_only:
                clauses.append("active = 1")
            if user_id is not None:
                clauses.append("user_id = ?")
                params.append(user_id)
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            cur.execute(base_select + where + " ORDER BY name ASC;", tuple(params))
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "image_path": r[2],
                    "parrot_ai_path": r[3],
                    "follow_line": r[4],
                    "follow_line_audio": r[5],
                    "active": r[6],
                    "user_id": r[7] if len(r) > 7 else None,
                } for r in rows
            ]
        except sqlite3.Error as e:
            logger.error(f"SQLite error get_characters: {e}")
            return []
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def normalize_dialogue_characters(self, project_id: int | None = None) -> dict:
        """Repair dialogues where 'character' is a placeholder ('speaker1'/'speaker2') and/or character_id is NULL.

        - For each project, read speaker1_id/speaker2_id and their names/image_paths.
        - Update dialouge_stage rows for that project:
            * character == 'speaker1' -> set to speaker1 name, character_id = speaker1_id, image = COALESCE(image, s1.image_path)
            * character == 'speaker2' -> set to speaker2 name, character_id = speaker2_id, image = COALESCE(image, s2.image_path)
            * character_id IS NULL and character (case-insensitive) matches a known name -> set character_id accordingly
        Returns a summary dict with counts.
        """
        fixed_placeholder = 0
        fixed_ids = 0
        try:
            conn = self.connect()
            cur = conn.cursor()
            # Determine projects to process
            if project_id is not None:
                proj_rows = [(project_id,)]
            else:
                cur.execute("SELECT id FROM projects;")
                proj_rows = cur.fetchall()
            for (pid,) in proj_rows:
                # Fetch project speakers
                cur.execute("SELECT speaker1_id, speaker2_id FROM projects WHERE id = ?;", (pid,))
                row = cur.fetchone()
                if not row:
                    continue
                s1_id, s2_id = row
                s1 = s2 = None
                if s1_id:
                    cur.execute("SELECT id, name, image_path FROM characters WHERE id = ?;", (s1_id,))
                    s1 = cur.fetchone()
                if s2_id:
                    cur.execute("SELECT id, name, image_path FROM characters WHERE id = ?;", (s2_id,))
                    s2 = cur.fetchone()
                # Replace placeholders
                if s1:
                    cur.execute(
                        "UPDATE dialouge_stage SET character = ?, character_id = COALESCE(character_id, ?), image = COALESCE(image, ?) "
                        "WHERE project_id = ? AND lower(character) = 'speaker1';",
                        (s1[1], s1[0], s1[2], pid)
                    )
                    fixed_placeholder += cur.rowcount or 0
                if s2:
                    cur.execute(
                        "UPDATE dialouge_stage SET character = ?, character_id = COALESCE(character_id, ?), image = COALESCE(image, ?) "
                        "WHERE project_id = ? AND lower(character) = 'speaker2';",
                        (s2[1], s2[0], s2[2], pid)
                    )
                    fixed_placeholder += cur.rowcount or 0
                # Fill missing character_id when name matches s1/s2
                if s1:
                    cur.execute(
                        "UPDATE dialouge_stage SET character_id = ? WHERE project_id = ? AND character_id IS NULL AND lower(character) = lower(?);",
                        (s1[0], pid, s1[1])
                    )
                    fixed_ids += cur.rowcount or 0
                if s2:
                    cur.execute(
                        "UPDATE dialouge_stage SET character_id = ? WHERE project_id = ? AND character_id IS NULL AND lower(character) = lower(?);",
                        (s2[0], pid, s2[1])
                    )
                    fixed_ids += cur.rowcount or 0
            conn.commit()
            return {"placeholders_fixed": fixed_placeholder, "ids_fixed": fixed_ids}
        except sqlite3.Error as e:
            logger.error(f"SQLite error normalizing dialogue characters: {e}")
            return {"placeholders_fixed": 0, "ids_fixed": 0}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get_character_by_id(self, cid:int):
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("SELECT id, name, image_path, parrot_ai_path, follow_line, follow_line_audio, user_id FROM characters WHERE id = ?;", (cid,))
            r = cur.fetchone()
            if not r:
                return None
            return {
                "id": r[0],
                "name": r[1],
                "image_path": r[2],
                "parrot_ai_path": r[3],
                "follow_line": r[4],
                "follow_line_audio": r[5],
                "user_id": r[6] if len(r) > 6 else None
            }
        except sqlite3.Error as e:
            logger.error(f"SQLite error get_character_by_id: {e}")
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get_character_by_name_like(self, fragment:str):
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM characters WHERE lower(name) LIKE ? LIMIT 1;", (f"%{fragment.lower()}%",))
            return cur.fetchone()
        except sqlite3.Error as e:
            logger.error(f"SQLite error get_character_by_name_like: {e}")
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # --- Backfill utilities ---
    def backfill_dialogue_character_ids(self):
        """Populate character_id in dialouge_stage based on text character column where NULL."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            # Fetch mapping for known seeds (simple heuristic)
            peter = self.get_character_by_name_like('peter')
            stewie = self.get_character_by_name_like('stewie')
            updates = 0
            if peter:
                cur.execute("UPDATE dialouge_stage SET character_id = ? WHERE character_id IS NULL AND lower(character) LIKE '%peter%';", (peter[0],))
                updates += cur.rowcount
            if stewie:
                cur.execute("UPDATE dialouge_stage SET character_id = ? WHERE character_id IS NULL AND lower(character) LIKE '%stewie%';", (stewie[0],))
                updates += cur.rowcount
            conn.commit()
            return {"updated_rows": updates}
        except sqlite3.Error as e:
            logger.error(f"SQLite error backfilling dialogue character ids: {e}")
            return {"updated_rows": 0}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def backfill_project_speakers(self):
        """Infer speaker1_id and speaker2_id for projects missing them based on dialogue frequency."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("SELECT id FROM projects WHERE speaker1_id IS NULL OR speaker2_id IS NULL;")
            project_rows = cur.fetchall()
            assigned = 0
            for (pid,) in project_rows:
                # Count character occurrences
                cur.execute("SELECT character_id, COUNT(*) FROM dialouge_stage WHERE project_id = ? AND character_id IS NOT NULL GROUP BY character_id ORDER BY COUNT(*) DESC;", (pid,))
                counts = cur.fetchall()
                if not counts:
                    continue
                speaker1_id = counts[0][0]
                speaker2_id = counts[1][0] if len(counts) > 1 else counts[0][0]
                cur.execute("UPDATE projects SET speaker1_id = COALESCE(speaker1_id, ?), speaker2_id = COALESCE(speaker2_id, ?) WHERE id = ?;", (speaker1_id, speaker2_id, pid))
                if cur.rowcount:
                    assigned += 1
            conn.commit()
            return {"projects_assigned": assigned}
        except sqlite3.Error as e:
            logger.error(f"SQLite error backfilling project speakers: {e}")
            return {"projects_assigned": 0}
        finally:
            try:
                conn.close()
            except Exception:
                pass
    def get_projects(self, user_id: int | None = None):
        """Return list of project tuples (legacy shape) optionally filtered by user_id.

        Diagnostic logging included to aid debugging environment/db path issues.
        """
        try:
            logger.info(f"get_projects(): db_file={self.db_name} user_filter={user_id}")
            conn = self.connect(); cursor = conn.cursor()
            if user_id is not None:
                cursor.execute("SELECT id, title, caption, pdf_url, status, video_path FROM projects WHERE user_id = ? ORDER BY id ASC;", (user_id,))
            else:
                cursor.execute("SELECT id, title, caption, pdf_url, status, video_path FROM projects ORDER BY id ASC;")
            rows = cursor.fetchall()
            logger.info(f"get_projects(): returned {len(rows)} rows")
            return rows
        except sqlite3.Error as e:
            logger.error(f"SQLite error during get_projects: {e}")
            return []
        finally:
            try: conn.close()
            except Exception: pass

    def _ensure_project_id_column(self):
        try:
            conn = self.connect()
            cursor = conn.cursor()
            # Add project_id column if missing
            cursor.execute("PRAGMA table_info(dialouge_stage);")
            cols = [col[1] for col in cursor.fetchall()]
            if 'project_id' not in cols:
                cursor.execute("ALTER TABLE dialouge_stage ADD COLUMN project_id INTEGER;")
                conn.commit()
        except sqlite3.Error:
            pass
        finally:
            conn.close()

    def create_project(self, title, caption, pdf_url, status=DialougeStatus.NEW, speaker1_id=None, speaker2_id=None, user_id: int | None = None):
        """Insert a new project and set current_project_id."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            # Attempt with user_id column first (present after migration)
            try:
                cursor.execute(
                    "INSERT INTO projects (title, caption, pdf_url, status, speaker1_id, speaker2_id, user_id) VALUES (?, ?, ?, ?, ?, ?, ?);",
                    (title, caption, pdf_url, status, speaker1_id, speaker2_id, user_id)
                )
            except sqlite3.Error as ie:
                # Fallback legacy (shouldn't normally happen once migrated)
                if 'user_id' in str(ie).lower():
                    cursor.execute(
                        "INSERT INTO projects (title, caption, pdf_url, status, speaker1_id, speaker2_id) VALUES (?, ?, ?, ?, ?, ?);",
                        (title, caption, pdf_url, status, speaker1_id, speaker2_id)
                    )
                else:
                    raise
            conn.commit()
            pid = cursor.lastrowid
            self.current_project_id = pid
            return pid
        except sqlite3.Error as e:
            logger.error(f"SQLite error during project creation: {e}")
            return None
        finally:
            conn.close()
            
    def create_dialouge_stage_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS dialouge_stage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sentence TEXT NOT NULL,
            character TEXT NOT NULL,
            image TEXT,
            image_search TEXT,
            audio TEXT,
            status TEXT DEFAULT 'NEW',
            project_id INTEGER,
            UNIQUE(sentence, character, project_id)
        );
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(query)  # <-- This line is required
            conn.commit()
            logger.info("Table 'dialouge_stage' is ready.")
        except sqlite3.Error as e:
            logger.error(f"SQLite error during table creation: {e}")
        finally:
            conn.close()

    def _ensure_dialogue_uniqueness(self):
        """Migrate UNIQUE(sentence, character) to UNIQUE(sentence, character, project_id) if not already.

        SQLite doesn't support altering constraints, so we recreate the table when needed.
        Safe to run repeatedly; it will no-op if the correct unique index already exists.
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            # Inspect existing indexes
            cursor.execute("PRAGMA index_list(dialouge_stage);")
            indexes = cursor.fetchall()  # (seq, name, unique, origin, partial)
            has_triplet = False
            for _, idx_name, unique, *_ in indexes:
                if not unique:
                    continue
                cursor.execute(f"PRAGMA index_info({idx_name});")
                cols = [r[2] for r in cursor.fetchall()]
                if cols == ['sentence', 'character', 'project_id']:
                    has_triplet = True
                    break
            if has_triplet:
                return  # Already migrated

            # Detect legacy constraint by testing duplicate insert across projects
            # If legacy, recreate table with proper constraint
            # Fetch schema to confirm legacy UNIQUE doesn't have project_id
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='dialouge_stage';")
            row = cursor.fetchone()
            if row and 'UNIQUE(sentence, character)' in row[0] and 'project_id' not in row[0].split('UNIQUE')[1]:
                logger.info("Migrating dialouge_stage uniqueness to include project_id...")
                cursor.execute("BEGIN TRANSACTION;")
                cursor.execute("""
                    CREATE TABLE dialouge_stage_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sentence TEXT NOT NULL,
                        character TEXT NOT NULL,
                        image TEXT,
                        image_search TEXT,
                        audio TEXT,
                        status TEXT DEFAULT 'NEW',
                        project_id INTEGER,
                        UNIQUE(sentence, character, project_id)
                    );
                """)
                cursor.execute("""
                    INSERT OR IGNORE INTO dialouge_stage_new (id, sentence, character, image, image_search, audio, status, project_id)
                    SELECT id, sentence, character, image, image_search, audio, status, project_id FROM dialouge_stage;
                """)
                cursor.execute("DROP TABLE dialouge_stage;")
                cursor.execute("ALTER TABLE dialouge_stage_new RENAME TO dialouge_stage;")
                cursor.execute("COMMIT;")
                logger.info("Migration complete: UNIQUE(sentence, character, project_id) now enforced.")
        except sqlite3.Error as e:
            try:
                cursor.execute("ROLLBACK;")
            except Exception:
                pass
            logger.error(f"SQLite error during uniqueness migration: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def update_audio_path(self, dialogue_id, audio_path):
        """Update the audio path for a given dialogue ID."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE dialouge_stage SET audio = ? WHERE id = ?;",
                (audio_path, dialogue_id)
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"SQLite error during audio path update: {e}")
        finally:
            conn.close()



    def add_or_update_dialogues(self, dialogues, project_id):
        """
        Upserts new dialogues (by sentence+character) with status NEW. Does not overwrite existing ones.
        """
        if not project_id:
            raise ValueError('project_id not set before adding dialogues')
        try:
            conn = self.connect()
            cursor = conn.cursor()
            for dialogue in dialogues:
                sentence = dialogue.get("dialogue")
                character = dialogue.get("character", None)
                image = dialogue.get("image", None)
                image_search = dialogue.get("image_search", None)
                character_id = dialogue.get("character_id", None)
                # Only insert if not exists for this project
                cursor.execute(
                    "INSERT OR IGNORE INTO dialouge_stage (sentence, character, image, image_search, status, project_id, character_id)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?);",
                    (sentence, character, image, image_search, DialougeStatus.NEW, project_id, character_id)
                )
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"SQLite error during upsert: {e}")
        finally:
            conn.close()

    def get_project_by_id(self, project_id:int):
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("SELECT id, title, caption, pdf_url, status, video_path, speaker1_id, speaker2_id, user_id FROM projects WHERE id = ?;", (project_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        except sqlite3.Error as e:
            logger.error(f"SQLite error get_project_by_id: {e}")
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get_project_by_id_for_user(self, project_id: int, user_id: int):
        """Fetch project only if owned by user_id."""
        p = self.get_project_by_id(project_id)
        if p and p.get('user_id') == user_id:
            return p
        return None

    def get_project_id_for_dialogue(self, dialogue_id: int) -> int | None:
        """Return the project_id for a given dialogue row id."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("SELECT project_id FROM dialouge_stage WHERE id = ?;", (dialogue_id,))
            row = cur.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"SQLite error get_project_id_for_dialogue: {e}")
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get_dialogues_by_status(self, status, project_id=None):
        try:
            conn = self.connect()
            cursor = conn.cursor()
            if project_id:
                cursor.execute(
                    "SELECT id, sentence, character, image, image_search, audio, status, character_id"
                    " FROM dialouge_stage WHERE status = ? AND project_id = ? ORDER BY id ASC;",
                    (status, project_id)
                )
            else:
                cursor.execute(
                    "SELECT id, sentence, character, image, image_search, audio, status, character_id"
                    " FROM dialouge_stage WHERE status = ? ORDER BY id ASC;",
                    (status,)
                )
            rows = cursor.fetchall()
            return rows
        except sqlite3.Error as e:
            logger.error(f"SQLite error: {e}")
            return []
        finally:
            conn.close()

    def update_status(self, dialogue_id, status):
        attempts = 0
        last_err = None
        while attempts < 5:
            try:
                conn = self.connect()
                cursor = conn.cursor()
                cursor.execute("UPDATE dialouge_stage SET status = ? WHERE id = ?", (status, dialogue_id))
                conn.commit()
                return True
            except sqlite3.OperationalError as e:
                # Retry on database is locked
                if "locked" in str(e).lower():
                    attempts += 1
                    last_err = e
                    time.sleep(0.1 * attempts)
                    continue
                else:
                    logger.error(f"SQLite error during status update: {e}")
                    break
            except sqlite3.Error as e:
                logger.error(f"SQLite error during status update: {e}")
                break
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        if last_err:
            logger.error(f"SQLite error during status update after retries: {last_err}")
        return False

    def reconcile_dialogue_statuses(self, project_id=None):
        """
        Fix inconsistent statuses:
        - Sync audio paths from completed audio_jobs to dialogues.
        - Mark any row with a non-empty audio path as COMPLETED.
        - Reset INPROGRESS rows that have no audio path AND no pending/completed job back to NEW.
        Returns a dict with counts of updates performed.
        """
        try:

            completed_reset_dict= {"completed_fixed": 0, "status_reset": 0, "audio_synced": 0}
            conn = self.connect()
            cursor = conn.cursor()

            params = []
            where_project = ""
            if project_id is not None:
                where_project = " AND d.project_id = ?"
                params.append(project_id)

            # 0) Sync audio paths from completed audio_jobs where dialogue has no audio
            # Use json_extract to find jobs by dialogue_id in request_payload
            sql_sync_audio = """
                UPDATE dialouge_stage 
                SET audio = (
                    SELECT aj.output_path 
                    FROM audio_jobs aj
                    WHERE json_extract(aj.request_payload, '$.dialogue_id') = dialouge_stage.id 
                    AND aj.status = 'COMPLETED' 
                    AND aj.output_path IS NOT NULL
                    AND TRIM(aj.output_path) <> ''
                    ORDER BY aj.id DESC 
                    LIMIT 1
                )
                WHERE (dialouge_stage.audio IS NULL OR TRIM(dialouge_stage.audio) = '')
                AND EXISTS (
                    SELECT 1 FROM audio_jobs aj2
                    WHERE json_extract(aj2.request_payload, '$.dialogue_id') = dialouge_stage.id 
                    AND aj2.status = 'COMPLETED'
                    AND aj2.output_path IS NOT NULL
                    AND TRIM(aj2.output_path) <> ''
                )
            """ + (where_project.replace("d.", "dialouge_stage.") if where_project else "") + ";"
            
            try:
                cursor.execute(sql_sync_audio, params if params else [])
                audio_synced = cursor.rowcount
            except sqlite3.Error as e:
                # Fallback: try without json_extract (older SQLite versions)
                logger.warning(f"json_extract not supported, skipping audio sync: {e}")
                audio_synced = 0

            # 1) Complete rows that have audio
            sql_complete = (
                "UPDATE dialouge_stage SET status = ? "
                "WHERE status != ? "
                "AND audio IS NOT NULL AND TRIM(audio) <> ''" + where_project.replace("d.", "dialouge_stage.") + ";"
            )
            cursor.execute(sql_complete, [DialougeStatus.COMPLETED, DialougeStatus.COMPLETED] + params)
            completed_fixed = cursor.rowcount

            # 2) Requeue stuck INPROGRESS without audio ONLY if no active/completed job exists
            # Don't reset if a job is QUEUED, IN_PROGRESS, or COMPLETED
            sql_requeue = """
                UPDATE dialouge_stage 
                SET status = ? 
                WHERE status = ? 
                AND (audio IS NULL OR TRIM(audio) = '')
                AND NOT EXISTS (
                    SELECT 1 FROM audio_jobs aj
                    WHERE json_extract(aj.request_payload, '$.dialogue_id') = dialouge_stage.id 
                    AND aj.status IN ('QUEUED', 'IN_PROGRESS', 'COMPLETED')
                )
            """ + (where_project.replace("d.", "dialouge_stage.") if where_project else "") + ";"
            
            try:
                cursor.execute(sql_requeue, [DialougeStatus.NEW, DialougeStatus.INPROGRESS] + params)
                requeued = cursor.rowcount
            except sqlite3.Error as e:
                # Fallback: use old behavior if json_extract fails
                logger.warning(f"json_extract not supported for requeue check, using simple reset: {e}")
                sql_requeue_simple = (
                    "UPDATE dialouge_stage SET status = ? "
                    "WHERE status = ? "
                    "AND (audio IS NULL OR TRIM(audio) = '')" + where_project.replace("d.", "dialouge_stage.") + ";"
                )
                cursor.execute(sql_requeue_simple, [DialougeStatus.NEW, DialougeStatus.INPROGRESS] + params)
                requeued = cursor.rowcount

            conn.commit()
            completed_reset_dict = {"completed_fixed": completed_fixed, "status_reset": requeued, "audio_synced": audio_synced}
            return completed_reset_dict
        except sqlite3.Error as e:
            logger.error(f"SQLite error during reconciliation: {e}")
            return {"completed_fixed": 0, "status_reset": 0, "audio_synced": 0}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    
    def get_dialouge_id(self, project_id:int)->int:
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM dialouge_stage WHERE project_id = ? ORDER BY id desc LIMIT 1;", (project_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"SQLite error during get_dialouge_id: {e}")
            return None
        finally:
            conn.close()

    def get_stage_and_unprocessed_dialogues(self):
        """
        Returns stage and up to 3 unprocessed dialogues (if exist):
        {
            "stage": 0 → table empty
                    1 → unprocessed dialogues exist
                    2 → table has data, but no eligible dialogues
            "dialogues": [...] or None
        }
            """
        try:
            conn = self.connect()
            cursor = conn.cursor()

            # Check if table is empty
            cursor.execute("SELECT COUNT(*) FROM dialouge_stage;")
            total_rows = cursor.fetchone()[0]
            if total_rows == 0:
                return {"stage": 0, "dialogues": None}

            # Try to fetch up to 3 unprocessed dialogues
            cursor.execute("""
                SELECT id, sentence, character, image, image_search, status
                FROM dialouge_stage
                WHERE status = ?
                ORDER BY id ASC
                LIMIT 3;
            """)
            rows = cursor.fetchall()
            if rows:
                dialogues = []
                for row in rows:
                    dialogues.append({
                        "id": row[0],
                        "sentence": row[1],
                        "character": row[2],
                        "image": row[3],
                        "image_search": row[4],
                        "status": row[5],
                    })
                return {"stage": 1, "dialogues": dialogues}

            # Table has data, but no unprocessed dialogue
            return {"stage": 2, "dialogues": None}

        except sqlite3.Error as e:
            print(f"SQLite error: {e}")
            return {"stage": -1, "dialogues": None}  # Error flag
        finally:
            conn.close()

    def get_ready_assets(self, project_id=None):
        """
        Returns all dialogues with status COMPLETED (ready for video generation).
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()

            # Check if table is empty
            cursor.execute("SELECT COUNT(*) FROM dialouge_stage;")
            total_rows = cursor.fetchone()[0]
            if total_rows == 0:
                return None

        # Fetch all dialogues with status COMPLETED
            if project_id:
                cursor.execute(
            "SELECT id, sentence, character, image, image_search, audio, status, character_id"
                    " FROM dialouge_stage"
                    " WHERE status = ? AND project_id = ? ORDER BY id ASC;",
                    (DialougeStatus.COMPLETED, project_id)
                )
            else:
                raise ValueError("project_id must be provided to fetch ready assets")
            rows = cursor.fetchall()
            if rows:
                dialogues = []
                for row in rows:
                    dialogues.append({
                        "id": row[0],
                        "sentence": row[1],
                        "character": row[2],
                        "image": row[3],
                        "image_search": row[4],
                        "audio": row[5],
                        "status": row[6],
                        "character_id": row[7] if len(row) > 7 else None
                    })
                return dialogues

            return None
        except sqlite3.Error as e:
            print(f"SQLite error: {e}")
            return None
        finally:
            conn.close()

    def show_all_dialogues(self):
        """
        Fetches all dialogues from the dialouge_stage table and prints them in a neat format.
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()

            # Fetch all rows from the dialouge_stage table
            cursor.execute("SELECT id, sentence, character, image, image_search, status FROM dialouge_stage;")
            rows = cursor.fetchall()

            # Check if the table is empty
            if not rows:
                print("No dialogues found in the database.")
                return

            # Print the table headers
            print(f"{'ID':<5} {'Sentence':<30} {'Character':<15} {'Image':<20} {'Image Search':<20} {'Audio Processed':<15} {'Retry Count':<10}")
            print("-" * 120)

            # Print each row
            for row in rows:
                print(f"{row[0]:<5} {row[1]:<30} {row[2]:<15} {row[3]:<20} {row[4]:<20} {row[5]:<15} {row[6]:<10}")
        except sqlite3.Error as e:
            print(f"SQLite error during fetching data: {e}")
        finally:
            conn.close()


    def truncate_dialouge_stage(self):
        """
        Deletes all rows from the dialouge_stage table and resets the auto-increment ID.
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()

            # Delete all records
            cursor.execute("DELETE FROM dialouge_stage;")

            # Reset auto-increment ID
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='dialouge_stage';")

            conn.commit()
            print("Table 'dialouge_stage' has been truncated and ID reset.")
        except sqlite3.Error as e:
            print(f"SQLite error during truncate: {e}")
        finally:
            conn.close()

    def get_project_by_status(self, status):
        """Fetches a project by its status."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, caption, pdf_url, status FROM projects WHERE status = ? ORDER BY id ASC LIMIT 1;",
                (status,)
            )
            project = cursor.fetchone()
            return project
        except sqlite3.Error as e:
            print(f"SQLite error during project fetch by status: {e}")
            return None
        finally:
            conn.close()

    def update_project_status(self, project_id, status):
        """Updates the status of a project."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE projects SET status = ? WHERE id = ?;",
                (status, project_id)
            )
            conn.commit()
        except sqlite3.Error as e:
            print(f"SQLite error during project status update: {e}")
        finally:
            conn.close()

    def get_dialogues_for_processing(self, project_id):
        """Fetches NEW or FAILED dialogues for a project."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, sentence, character, image, image_search, audio, status, character_id"
                " FROM dialouge_stage WHERE project_id = ? AND (status = ? OR status = ?) ORDER BY id ASC;",
                (project_id, DialougeStatus.NEW, DialougeStatus.FAILED)
            )
            rows = cursor.fetchall()
            return rows
        except sqlite3.Error as e:
            print(f"SQLite error: {e}")
            return []
        finally:
            conn.close()

    def get_all_dialogues_by_project(self, project_id):
        """ Fetches all dialogues for a given project ID. """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, sentence, character, image, image_search, audio, status, character_id"
                " FROM dialouge_stage WHERE project_id = ? ORDER BY id ASC;",
                (project_id,)
            )
            rows = cursor.fetchall()
            return rows
        except sqlite3.Error as e:
            print(f"SQLite error: {e}")
            return []
        finally:
            conn.close()

    def get_dialogue_completion_counts(self, project_id: int) -> tuple[int, int]:
        """Return (total, completed) dialogue counts for a project."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM dialouge_stage WHERE project_id = ?;", (project_id,))
            total = cur.fetchone()[0] or 0
            cur.execute(
                "SELECT COUNT(*) FROM dialouge_stage WHERE project_id = ? AND status = ?;",
                (project_id, DialougeStatus.COMPLETED),
            )
            completed = cur.fetchone()[0] or 0
            return int(total), int(completed)
        except sqlite3.Error as e:
            logger.error(f"SQLite error during completion counts: {e}")
            return 0, 0
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def mark_project_status_if(self, project_id: int, expected_current: str, new_status: str) -> bool:
        """Atomically set project status to new_status if current matches expected_current."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute(
                "UPDATE projects SET status = ? WHERE id = ? AND status = ?;",
                (new_status, project_id, expected_current),
            )
            conn.commit()
            return cur.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"SQLite error during conditional status update: {e}")
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get_projects_by_status(self, status):
        """Fetches all projects by their status."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, caption, pdf_url, status, video_path FROM projects WHERE status = ? ORDER BY id ASC;",
                (status,)
            )
            projects = cursor.fetchall()
            # Returning as a list of dictionaries for easier use
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, project)) for project in projects]
        except sqlite3.Error as e:
            print(f"SQLite error during project fetch by status: {e}")
            return []
        finally:
            conn.close()

    def update_project_video_path(self, project_id, video_path):
        """Updates the video_path of a project."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE projects SET video_path = ? WHERE id = ?;",
                (video_path, project_id)
            )
            conn.commit()
        except sqlite3.Error as e:
            print(f"SQLite error during project video_path update: {e}")
        finally:
            conn.close()

    # --- Characters CRUD helpers ---
    def create_character(self, name: str, parrot_ai_path: str, image_filename: str, active: int = 1,
                         follow_line: str | None = None, follow_line_audio: str | None = None, user_id: int | None = None):
        """Create a new character. image_filename should be just the filename (e.g., 'peter.png').
        Optionally accepts follow_line and follow_line_audio for initial seed.
        """
        try:
            # Validate follow_line length (<= 100)
            if follow_line is not None and len(follow_line.strip()) > 100:
                print("Validation error: follow_line must be at most 100 characters.")
                return None
            conn = self.connect()
            cur = conn.cursor()
            columns = ["name", "image_path", "parrot_ai_path", "active"]
            values = [name, image_filename, parrot_ai_path, int(bool(active))]
            if follow_line is not None:
                columns.append("follow_line")
                values.append(follow_line)
            if follow_line_audio is not None:
                columns.append("follow_line_audio")
                values.append(follow_line_audio)
            if user_id is not None:
                columns.append("user_id")
                values.append(user_id)
            else:
                raise ValueError("user_id must be provided when creating a character")
            placeholders = ", ".join(["?"] * len(values))
            cur.execute(
                f"INSERT INTO characters ({', '.join(columns)}) VALUES ({placeholders});",
                tuple(values)
            )
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError as e:
            # Likely UNIQUE violation on name (case-insensitive idx) or parrot_ai_path
            print(f"Integrity error during character creation (duplicate?): {e}")
            return None
        except sqlite3.Error as e:
            print(f"SQLite error during character creation: {e}")
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def update_character(self, character_id: int, parrot_ai_path: str | None = None, image_filename: str | None = None,
                         active: int | None = None, follow_line: str | None = None, follow_line_audio: str | None = None) -> bool:
        """Update selected fields for a character, including follow_line and follow_line_audio when provided."""
        try:
            # Validate follow_line length (<= 100)
            if follow_line is not None and len(follow_line.strip()) > 100:
                print("Validation error: follow_line must be at most 100 characters.")
                return False
            sets = []
            params = []
            if parrot_ai_path is not None:
                sets.append("parrot_ai_path = ?")
                params.append(parrot_ai_path)
            if image_filename is not None:
                sets.append("image_path = ?")
                params.append(image_filename)
            if active is not None:
                sets.append("active = ?")
                params.append(int(bool(active)))
            if follow_line is not None:
                sets.append("follow_line = ?")
                params.append(follow_line)
            if follow_line_audio is not None:
                sets.append("follow_line_audio = ?")
                params.append(follow_line_audio)
            if not sets:
                return False
            params.append(character_id)
            conn = self.connect()
            cur = conn.cursor()
            cur.execute(f"UPDATE characters SET {', '.join(sets)} WHERE id = ?;", params)
            conn.commit()
            return cur.rowcount > 0
        except sqlite3.Error as e:
            print(f"SQLite error during character update: {e}")
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def delete_character(self, character_id: int) -> bool:
        """Delete a character by id."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("DELETE FROM characters WHERE id = ?;", (character_id,))
            conn.commit()
            return cur.rowcount > 0
        except sqlite3.Error as e:
            print(f"SQLite error during character deletion: {e}")
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def character_has_active_projects(self, character_id: int) -> bool:
        """Return True if any project with status NEW or INPROGRESS uses this character as speaker1 or speaker2."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM projects WHERE (speaker1_id = ? OR speaker2_id = ?) AND status IN (?, ?) LIMIT 1;",
                (character_id, character_id, DialougeStatus.NEW, DialougeStatus.INPROGRESS),
            )
            row = cur.fetchone()
            return row is not None
        except sqlite3.Error as e:
            print(f"SQLite error checking character active projects: {e}")
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass
