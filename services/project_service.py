import time
import requests
from typing import List, Dict, Any
from db_handler import DBOperation, DialougeStatus
from services.dialouge_creator import fetch_pdf_from_url, generate_from_pdf_content
from services.character_service import CharacterService
from utils import get_datetime_str

# Custom Exceptions
class ProjectExistsError(Exception):
    pass

class DialogueGenerationError(Exception):
    pass

class ProjectValidationError(Exception):
    pass


def project_exists(db: DBOperation, project_name: str) -> bool:
    try:
        existing_projects = db.get_projects()
    except Exception:
        return False
    return any(p[1] == project_name for p in existing_projects)


def validate_dialogues(dialogues: List[Dict[str, Any]]) -> None:
    if not dialogues:
        raise ProjectValidationError("No dialogues returned from generation step.")
    required = {"dialogue", "character", "image", "image_search"}
    for idx, row in enumerate(dialogues):
        if not required.issubset(row.keys()):
            raise ProjectValidationError(f"Dialogue row missing required keys at index {idx}: {row}")
        if len(row.get("dialogue", "")) > 100:
            raise ProjectValidationError(f"Dialogue text exceeds 100 chars at index {idx}")


def add_follow_for_more_dialogue(db: DBOperation, project_id: int, primary_character_id: int):
    cs = CharacterService()
    ch = cs.get(primary_character_id) if primary_character_id else None
    if not ch:
        # fallback to Peter
        fallback = cs.get_character_by_name_like('peter') if hasattr(cs.db, 'get_character_by_name_like') else None
        primary_character_id = fallback[0] if fallback else None
        ch = cs.get(primary_character_id) if primary_character_id else None
    if not ch:
        # last resort defaults
        ch = {"name": "Peter Griffin", "image_path": "peter.png", "follow_line": "Follow for more.", "follow_line_audio": ""}
    dialogues = [{
        "dialogue": ch.get("follow_line") or "Follow for more.",
        "character": ch.get("name"),
        "character_id": ch.get("id"),
        "image": ch.get("image_path", ""),
        "image_search": ""
    }]
    db.add_or_update_dialogues(dialogues, project_id)
    # Update audio path + mark completed
    last_id = db.get_dialouge_id(project_id)
    if last_id:
        audio_path = ch.get("follow_line_audio") or ""
        db.update_audio_path(last_id, audio_path)
        db.update_status(last_id, DialougeStatus.COMPLETED)


def fetch_pdf_bytes(pdf_url: str) -> bytes:
    # Reuse existing util for consistency
    pdf_bytes = fetch_pdf_from_url(pdf_url)
    if not pdf_bytes:
        raise DialogueGenerationError("Failed to download PDF bytes")
    return pdf_bytes


def generate_dialogues_from_pdf(pdf_bytes: bytes, speaker1_id: int, speaker2_id: int, max_retries: int = 3, delay: int = 3) -> List[Dict[str, Any]]:
    last_error = None
    cs = CharacterService()
    s1 = cs.get(speaker1_id) if speaker1_id else None
    s2 = cs.get(speaker2_id) if speaker2_id else None
    # Always ensure a speaker context to allow mapping placeholders to names/ids
    if not (s1 and s2):
        fallback = cs.list_active_characters()[:2]
        if len(fallback) >= 2:
            s1, s2 = fallback[0], fallback[1]
    speaker_ctx = {"speaker1": s1, "speaker2": s2} if s1 and s2 else None
    for attempt in range(1, max_retries + 1):
        try:
            dialogue_data = generate_from_pdf_content(pdf_bytes, speaker_context=speaker_ctx)
            if not dialogue_data or "dialogue_scenes" not in dialogue_data:
                raise DialogueGenerationError("Model response missing 'dialogue_scenes'")
            dialogues = dialogue_data["dialogue_scenes"]
            # Map 'speaker1'/'speaker2' placeholders to actual names and character_ids
            if speaker_ctx:
                for d in dialogues:
                    key = str(d.get("character", "")).strip().lower()
                    if key == "speaker1" and s1:
                        d["character"] = s1.get("name")
                        d["character_id"] = s1.get("id")
                        if not d.get("image"):
                            d["image"] = s1.get("image_path", d.get("image", ""))
                    elif key == "speaker2" and s2:
                        d["character"] = s2.get("name")
                        d["character_id"] = s2.get("id")
                        if not d.get("image"):
                            d["image"] = s2.get("image_path", d.get("image", ""))
                    else:
                        # Try to resolve id if character already a name
                        name_lower = str(d.get("character", "")).strip().lower()
                        if s1 and name_lower == str(s1.get("name", "")).strip().lower():
                            d["character_id"] = s1.get("id")
                        elif s2 and name_lower == str(s2.get("name", "")).strip().lower():
                            d["character_id"] = s2.get("id")
            validate_dialogues(dialogues)
            return dialogues
        except Exception as e:
            last_error = e
            time.sleep(delay)
    raise DialogueGenerationError(f"Dialogue generation failed after {max_retries} attempts: {last_error}")


def create_project_with_dialogues(db: DBOperation, project_name: str, caption: str, pdf_url: str, speaker1_id: int, speaker2_id: int, user_id: int | None = None) -> Dict[str, Any]:
    if project_exists(db, project_name):
        raise ProjectExistsError(f"Project '{project_name}' already exists")

    pdf_bytes = fetch_pdf_bytes(pdf_url)
    dialogues = generate_dialogues_from_pdf(pdf_bytes, speaker1_id, speaker2_id)

    # Insert project first
    db.create_project(project_name, caption, pdf_url, speaker1_id=speaker1_id, speaker2_id=speaker2_id, user_id=user_id)
    # Retrieve project id
    projects = db.get_projects()
    project_id = None
    for p in projects:
        if p[1] == project_name:
            project_id = p[0]
            break
    if project_id is None:
        raise RuntimeError("Failed to retrieve newly created project ID.")

    # Add dialogues
    db.add_or_update_dialogues(dialogues, project_id)
    # Safety: normalize any placeholder speaker names and fill missing character_ids
    try:
        db.normalize_dialogue_characters(project_id)
    except Exception:
        pass
    # Add CTA line with audio
    # Add CTA based on speaker1 (primary)
    add_follow_for_more_dialogue(db, project_id, speaker1_id)

    total_count = len(db.get_all_dialogues_by_project(project_id))
    return {
        'project_id': project_id,
        'dialogue_count': total_count,
        'created_at': get_datetime_str()
    }
