import sqlite3
from utils import DialougeStatus

class DBOperation:
    def __init__(self, db_name="stewie_database.db"):
        self.db_name = db_name
        # Initialize tables
        self.create_projects_table()
        self.create_dialouge_stage_table()
        # Ensure project_id column exists
        self._ensure_project_id_column()

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
    def create_project(self, title, caption, pdf_url, status=DialougeStatus.NEW):
        """Insert a new project and set current_project_id."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO projects (title, caption, pdf_url, status) VALUES (?, ?, ?, ?);",
                (title, caption, pdf_url, status)
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
            UNIQUE(sentence, character)
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
                # Only insert if not exists for this project
                cursor.execute(
                    "INSERT OR IGNORE INTO dialouge_stage (sentence, character, image, image_search, status, project_id)"
                    " VALUES (?, ?, ?, ?, ?, ?);",
                    (sentence, character, image, image_search, DialougeStatus.NEW, project_id)
                )
            conn.commit()
        except sqlite3.Error as e:
            print(f"SQLite error during upsert: {e}")
        finally:
            conn.close()

    def get_dialogues_by_status(self, status, project_id=None):
        try:
            conn = self.connect()
            cursor = conn.cursor()
            if project_id:
                cursor.execute(
                    "SELECT id, sentence, character, image, image_search, audio, status"
                    " FROM dialouge_stage WHERE status = ? AND project_id = ? ORDER BY id ASC;",
                    (status, project_id)
                )
            else:
                cursor.execute(
                    "SELECT id, sentence, character, image, image_search, audio, status"
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
                    "SELECT id, sentence, character, image, image_search, audio, status"
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
                        "status": row[6]
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
                "SELECT id, sentence, character, image, image_search, audio, status"
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
                "SELECT id, sentence, character, image, image_search, audio, status"
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