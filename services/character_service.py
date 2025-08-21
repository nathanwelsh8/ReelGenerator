from typing import List, Optional, Dict
from db_handler import DBOperation

class CharacterService:
    """Service layer to interact with character data and provide convenience utilities."""
    def __init__(self, db: Optional[DBOperation] = None):
        self.db = db or DBOperation()

    def list_active_characters(self) -> List[Dict]:
        # Prefer DBOperation API; fall back to direct SQL for compatibility in long-running UIs
        try:
            return self.db.get_characters(active_only=True)
        except AttributeError:
            try:
                conn = self.db.connect()
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, name, image_path, parrot_ai_path, follow_line, follow_line_audio, active "
                    "FROM characters WHERE active = 1 ORDER BY name ASC;"
                )
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
                    }
                    for r in rows
                ]
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def get(self, character_id: int) -> Optional[Dict]:
        try:
            return self.db.get_character_by_id(character_id)  # type: ignore[attr-defined]
        except AttributeError:
            try:
                conn = self.db.connect()
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, name, image_path, parrot_ai_path, follow_line, follow_line_audio FROM characters WHERE id = ?;",
                    (character_id,),
                )
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
                }
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def ensure_backfill(self):
        """Run idempotent backfills for character_id and project speakers."""
        self.db.backfill_dialogue_character_ids()
        self.db.backfill_project_speakers()

    def resolve_project_speakers(self, project: Dict) -> Optional[Dict]:
        """Return a dict with speaker1 and speaker2 character dicts for a project.
        Expects project dict containing speaker1_id & speaker2_id.
        """
        if not project:
            return None
        s1 = self.get(project.get('speaker1_id')) if project.get('speaker1_id') else None
        s2 = self.get(project.get('speaker2_id')) if project.get('speaker2_id') else None
        return {"speaker1": s1, "speaker2": s2}

    def parrot_url_for(self, character: Dict) -> Optional[str]:
        if not character:
            return None
        slug = character.get('parrot_ai_path')
        if not slug:
            return None
        return f"https://www.tryparrotai.com/ai-voice/{slug}"

    # --- Uniqueness helpers ---
    def name_exists(self, name: str) -> bool:
        """Return True if a character with the same name (case-insensitive) exists."""
        if not name:
            return False
        try:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM characters WHERE lower(name) = lower(?) LIMIT 1;", (name.strip(),))
            return cur.fetchone() is not None
        except Exception:
            # Be conservative if there's an error: do not falsely block
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def ensure_unique_name(self, name: str) -> None:
        """Raise ValueError if name already exists (case-insensitive)."""
        if self.name_exists(name):
            raise ValueError(f"Character name '{name}' already exists")
