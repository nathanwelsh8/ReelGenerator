import sqlite3
from utils import DialougeStatus

class DBOperation:
    def __init__(self, db_name="stewie_database.db"):
        """Initialize DB and run idempotent migrations."""
        self.db_name = db_name
        # Base tables
        self.create_projects_table()
        self.create_dialouge_stage_table()
        # Additive migrations for multi-character support (Step 1)
        self.create_characters_table()
        self._ensure_character_name_unique_index()
        self._ensure_project_speaker_columns()
        self._ensure_dialouge_character_id_column()
        # Seed baseline characters
        self.seed_characters()
        # Legacy support / prior migrations
        self._ensure_project_id_column()
        self._ensure_dialogue_uniqueness()

    def connect(self):
        return sqlite3.connect(self.db_name)

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
            print("Table 'projects' is ready.")
        except sqlite3.Error as e:
            print(f"SQLite error during projects table creation: {e}")
        finally:
            conn.close()
    
    # --- New multi-character schema helpers ---
    def create_characters_table(self):
        """Create characters table if not exists."""
        query = """
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            image_path TEXT NOT NULL,
            parrot_ai_path TEXT NOT NULL UNIQUE,
            active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute(query)
            conn.commit()
        except sqlite3.Error as e:
            print(f"SQLite error creating characters table: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
        # Ensure newly added follow columns exist (cannot be in original CREATE for idempotency with previous versions)
        self._ensure_character_follow_columns()

    def _ensure_character_follow_columns(self):
        """Add follow_line and follow_line_audio columns if missing (SQLite ALTER TABLE add column)."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(characters);")
            cols = [r[1] for r in cur.fetchall()]
            stmts = []
            if 'follow_line' not in cols:
                stmts.append("ALTER TABLE characters ADD COLUMN follow_line TEXT;")
            if 'follow_line_audio' not in cols:
                stmts.append("ALTER TABLE characters ADD COLUMN follow_line_audio TEXT;")
            for s in stmts:
                try:
                    cur.execute(s)
                except sqlite3.Error as ie:
                    print(f"SQLite error adding follow column: {ie}")
            if stmts:
                conn.commit()
        except sqlite3.Error as e:
            print(f"SQLite error ensuring follow columns: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _ensure_character_name_unique_index(self):
        """Ensure a case-insensitive unique index on characters.name to prevent duplicates by case."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            # Create a case-insensitive unique index; safe if already exists
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_characters_name_nocase ON characters(name COLLATE NOCASE);")
            conn.commit()
        except sqlite3.Error as e:
            # If duplicates already exist, this will fail; log and continue
            print(f"SQLite error ensuring unique name index: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _ensure_project_speaker_columns(self):
        """Add speaker1_id, speaker2_id columns to projects if missing (idempotent)."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(projects);")
            cols = [r[1] for r in cur.fetchall()]
            alters = []
            if 'speaker1_id' not in cols:
                alters.append("ALTER TABLE projects ADD COLUMN speaker1_id INTEGER;")
            if 'speaker2_id' not in cols:
                alters.append("ALTER TABLE projects ADD COLUMN speaker2_id INTEGER;")
            for stmt in alters:
                try:
                    cur.execute(stmt)
                except sqlite3.Error as ie:
                    print(f"SQLite error adding speaker column: {ie}")
            if alters:
                conn.commit()
        except sqlite3.Error as e:
            print(f"SQLite error ensuring speaker columns: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _ensure_dialouge_character_id_column(self):
        """Add character_id column to dialouge_stage if missing (idempotent)."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(dialouge_stage);")
            cols = [r[1] for r in cur.fetchall()]
            if 'character_id' not in cols:
                try:
                    cur.execute("ALTER TABLE dialouge_stage ADD COLUMN character_id INTEGER;")
                    conn.commit()
                except sqlite3.Error as ie:
                    print(f"SQLite error adding character_id: {ie}")
        except sqlite3.Error as e:
            print(f"SQLite error ensuring character_id column: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def seed_characters(self):
        """Seed baseline characters (Peter & Stewie) if not present. Safe to call repeatedly."""
        seeds = [
            {
                "name": "Peter Griffin",
                "image_path": "peter.png",
                "parrot_ai_path": "peter-griffin",
                "follow_line": "If you wanna see more of this genius stuff, follow Professor Peter Griffin. Do it. Do it now.",
                "follow_line_audio": "audio_assests/static/peter_follow_for_more.mp3"
            },
            {
                "name": "Stewie Griffin",
                "image_path": "stewie.png",
                "parrot_ai_path": "stewie-griffin",
                "follow_line": "I'll be monitoring your future transmissions. Consider yourself 'followed'.",
                "follow_line_audio": "audio_assests/static/stewie_follow_for_more.mp3"
            },
        ]
        try:
            conn = self.connect()
            cur = conn.cursor()
            for s in seeds:
                try:
                    # Upsert pattern: try insert; then update follow fields if NULL
                    cur.execute(
                        "INSERT OR IGNORE INTO characters (name, image_path, parrot_ai_path, follow_line, follow_line_audio) VALUES (?, ?, ?, ?, ?);",
                        (s["name"], s["image_path"], s["parrot_ai_path"], s.get("follow_line"), s.get("follow_line_audio"))
                    )
                    # Ensure follow lines populated if row pre-existed without them
                    cur.execute(
                        "UPDATE characters SET follow_line = COALESCE(follow_line, ?), follow_line_audio = COALESCE(follow_line_audio, ?) WHERE name = ?;",
                        (s.get("follow_line"), s.get("follow_line_audio"), s["name"]) 
                    )
                except sqlite3.Error as ie:
                    print(f"SQLite error seeding character {s['name']}: {ie}")
            conn.commit()
        except sqlite3.Error as e:
            print(f"SQLite error during character seeding: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # --- Character accessors ---
    def get_characters(self, active_only=True):
        try:
            conn = self.connect()
            cur = conn.cursor()
            if active_only:
                cur.execute("SELECT id, name, image_path, parrot_ai_path, follow_line, follow_line_audio, active FROM characters WHERE active = 1 ORDER BY name ASC;")
            else:
                cur.execute("SELECT id, name, image_path, parrot_ai_path, follow_line, follow_line_audio, active FROM characters ORDER BY name ASC;")
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
                } for r in rows
            ]
        except sqlite3.Error as e:
            print(f"SQLite error get_characters: {e}")
            return []
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get_character_by_id(self, cid:int):
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("SELECT id, name, image_path, parrot_ai_path, follow_line, follow_line_audio FROM characters WHERE id = ?;", (cid,))
            r = cur.fetchone()
            if not r:
                return None
            return {
                "id": r[0],
                "name": r[1],
                "image_path": r[2],
                "parrot_ai_path": r[3],
                "follow_line": r[4],
                "follow_line_audio": r[5]
            }
        except sqlite3.Error as e:
            print(f"SQLite error get_character_by_id: {e}")
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
            print(f"SQLite error get_character_by_name_like: {e}")
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
            print(f"SQLite error backfilling dialogue character ids: {e}")
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
            print(f"SQLite error backfilling project speakers: {e}")
            return {"projects_assigned": 0}
        finally:
            try:
                conn.close()
            except Exception:
                pass
    def get_projects(self):
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, caption, pdf_url, status, video_path FROM projects ORDER BY id ASC;")
            rows = cursor.fetchall()
            return rows
        except sqlite3.Error as e:
            print(f"SQLite error during get_projects: {e}")
            return []
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
    def create_project(self, title, caption, pdf_url, status=DialougeStatus.NEW, speaker1_id=None, speaker2_id=None):
        """Insert a new project and set current_project_id."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO projects (title, caption, pdf_url, status, speaker1_id, speaker2_id) VALUES (?, ?, ?, ?, ?, ?);",
                (title, caption, pdf_url, status, speaker1_id, speaker2_id)
            )
            conn.commit()
            pid = cursor.lastrowid
            self.current_project_id = pid
            return pid
        except sqlite3.Error as e:
            print(f"SQLite error during project creation: {e}")
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
            print("Table 'dialouge_stage' is ready.")
        except sqlite3.Error as e:
            print(f"SQLite error during table creation: {e}")
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
                print("Migrating dialouge_stage uniqueness to include project_id...")
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
                print("Migration complete: UNIQUE(sentence, character, project_id) now enforced.")
        except sqlite3.Error as e:
            try:
                cursor.execute("ROLLBACK;")
            except Exception:
                pass
            print(f"SQLite error during uniqueness migration: {e}")
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
            print(f"SQLite error during audio path update: {e}")
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
            print(f"SQLite error during upsert: {e}")
        finally:
            conn.close()

    def get_project_by_id(self, project_id:int):
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute("SELECT id, title, caption, pdf_url, status, video_path, speaker1_id, speaker2_id FROM projects WHERE id = ?;", (project_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        except sqlite3.Error as e:
            print(f"SQLite error get_project_by_id: {e}")
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
            print(f"SQLite error: {e}")
            return []
        finally:
            conn.close()

    def update_status(self, dialogue_id, status):
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE dialouge_stage SET status = ? WHERE id = ?", (status, dialogue_id))
            conn.commit()
        except sqlite3.Error as e:
            print(f"SQLite error during status update: {e}")
        finally:
            conn.close()

    def reconcile_dialogue_statuses(self, project_id=None):
        """
        Fix inconsistent statuses:
        - Mark any row with a non-empty audio path as COMPLETED.
        - Reset INPROGRESS rows that have no audio path back to NEW so they can be retried.
        Returns a dict with counts of updates performed.
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()

            params = []
            where_project = ""
            if project_id is not None:
                where_project = " AND project_id = ?"
                params.append(project_id)

            # 1) Complete rows that have audio
            sql_complete = (
                "UPDATE dialouge_stage SET status = ? "
                "WHERE status != ? "
                "AND audio IS NOT NULL AND TRIM(audio) <> ''" + where_project + ";"
            )
            cursor.execute(sql_complete, [DialougeStatus.COMPLETED, DialougeStatus.COMPLETED] + params)
            completed_fixed = cursor.rowcount

            # 2) Requeue stuck INPROGRESS without audio
            sql_requeue = (
                "UPDATE dialouge_stage SET status = ? "
                "WHERE status = ? "
                "AND (audio IS NULL OR TRIM(audio) = '')" + where_project + ";"
            )
            cursor.execute(sql_requeue, [DialougeStatus.NEW, DialougeStatus.INPROGRESS] + params)
            requeued = cursor.rowcount

            conn.commit()
            return {"completed_fixed": completed_fixed, "requeued": requeued}
        except sqlite3.Error as e:
            print(f"SQLite error during reconciliation: {e}")
            return {"completed_fixed": 0, "requeued": 0}
        finally:
            conn.close()

    
    def get_dialouge_id(self, project_id:int)->int:
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM dialouge_stage WHERE project_id = ? ORDER BY id desc LIMIT 1;", (project_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            print(f"SQLite error during get_dialouge_id: {e}")
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
    def create_character(self, name: str, parrot_ai_path: str, image_filename: str, active: int = 1):
        """Create a new character. image_filename should be just the filename (e.g., 'peter.png')."""
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO characters (name, image_path, parrot_ai_path, active) VALUES (?, ?, ?, ?);",
                (name, image_filename, parrot_ai_path, int(bool(active)))
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

    def update_character(self, character_id: int, parrot_ai_path: str | None = None, image_filename: str | None = None, active: int | None = None) -> bool:
        """Update selected fields for a character."""
        try:
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


#form  of data that  db  accepts  ...
convo= [
    {
      "audio": "C:/path/to/audio/peter_audio_0.mp3",
      "image": "peter.png",
      "dialogue": "Peter: MongoDB is a NoSQL database, like a giant bookshelf for your data. No rigid tables!",
      "image_search": "mongodb noSQL bookshelf analogy",
      "character": "Peter"
    },
    {
      "audio": "C:/path/to/audio/stewie_audio_1.mp3",
      "image": "stewie.png",
      "dialogue": "Stewie: So, no tables? Are we just piling data on a shelf like a hoarder's dream?",
      "image_search": "mongodb data hoard shelf",
      "character": "Stewie"
    },
    {
      "audio": "C:/path/to/audio/peter_audio_2.mp3",
      "image": "peter.png",
      "dialogue": "Peter: Yep, MongoDB uses collections instead of tables. Think of them as folders of data.",
      "image_search": "mongodb collections folders",
      "character": "Peter"
    },
    {
      "audio": "C:/path/to/audio/stewie_audio_3.mp3",
      "image": "stewie.png",
      "dialogue": "Stewie: So I can store anything in a folder? Sounds like the tech version of a junk drawer!",
      "image_search": "mongodb junk drawer analogy",
      "character": "Stewie"
    },
    {
      "audio": "C:/path/to/audio/peter_audio_4.mp3",
      "image": "peter.png",
      "dialogue": "Peter: Exactly! Each document in MongoDB is like a sticky note with data—no fixed format.",
      "image_search": "mongodb document sticky note",
      "character": "Peter"
    },
    {
      "audio": "C:/path/to/audio/stewie_audio_5.mp3",
      "image": "stewie.png",
      "dialogue": "Stewie: So no columns? Just random data all over the place? Sounds messy.",
      "image_search": "mongodb no columns messy",
      "character": "Stewie"
    },
    {
      "audio": "C:/path/to/audio/peter_audio_6.mp3",
      "image": "peter.png",
      "dialogue": "Peter: It’s not messy, Stewie! MongoDB is flexible. You can add data as you need it.",
      "image_search": "mongodb flexible data addition",
      "character": "Peter"
    },
    {
      "audio": "C:/path/to/audio/stewie_audio_7.mp3",
      "image": "stewie.png",
      "dialogue": "Stewie: Flexible? Sounds like the database equivalent of an open bar at a wedding.",
      "image_search": "mongodb flexible open bar wedding",
      "character": "Stewie"
    },
    {
      "audio": "C:/path/to/audio/peter_audio_8.mp3",
      "image": "peter.png",
      "dialogue": "Peter: More like a buffet, Stewie! It lets you easily scale when the data gets huge.",
      "image_search": "mongodb scaling buffet analogy",
      "character": "Peter"
    }
  ]


if __name__ == "__main__":
    db = DBOperation()
    db.truncate_dialouge_stage()
    db.add_dialogues(convo)
    print(db.get_stage_and_unprocessed_dialogue())
    db.show_all_dialogues()
    ready_assests=db.get_ready_assets()
    print(ready_assests)
    for dic in  ready_assests:
        print(dic)
    db.truncate_dialouge_stage()