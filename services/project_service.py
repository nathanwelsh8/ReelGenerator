import time
import requests
from typing import List, Dict, Any
from db_handler import DBOperation, DialougeStatus
from services.dialouge_creator import fetch_pdf_from_url, generate_from_pdf_content
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


def add_follow_for_more_dialogue(db: DBOperation, project_id: int, primary_character: str):
    # Choose character for CTA; default to provided primary
    char = "Stewie" if primary_character.lower().startswith("stew") else "Peter"
    follow_for_more_dialogue = "If you wanna see more of this genius stuff, follow Professor Peter Griffin. Do it. Do it now." if char == "Peter" else "I'll be following your future transmissions... consider yourself... followed."
    dialogues = [{
        "dialogue": follow_for_more_dialogue,
        "character": char,
        "image": f"{char.lower()}.png",
        "image_search": ""
    }]
    db.add_or_update_dialogues(dialogues, project_id)
    # Update audio path + mark completed
    last_id = db.get_dialouge_id(project_id)
    if last_id:
        audio_path = (
            "audio_assests/static/stewie_follow_for_more.mp3"
            if char.lower().startswith("stew")
            else "audio_assests/static/peter_follow_for_more.mp3"
        )
        db.update_audio_path(last_id, audio_path)
        db.update_status(last_id, DialougeStatus.COMPLETED)


def fetch_pdf_bytes(pdf_url: str) -> bytes:
    # Reuse existing util for consistency
    pdf_bytes = fetch_pdf_from_url(pdf_url)
    if not pdf_bytes:
        raise DialogueGenerationError("Failed to download PDF bytes")
    return pdf_bytes


def generate_dialogues_from_pdf(pdf_bytes: bytes, max_retries: int = 3, delay: int = 3) -> List[Dict[str, Any]]:
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            dialogue_data = generate_from_pdf_content(pdf_bytes)
            if not dialogue_data or "dialogue_scenes" not in dialogue_data:
                raise DialogueGenerationError("Model response missing 'dialogue_scenes'")
            dialogues = dialogue_data["dialogue_scenes"]
            validate_dialogues(dialogues)
            return dialogues
        except Exception as e:
            last_error = e
            time.sleep(delay)
    raise DialogueGenerationError(f"Dialogue generation failed after {max_retries} attempts: {last_error}")


def create_project_with_dialogues(db: DBOperation, project_name: str, caption: str, pdf_url: str, character: str) -> Dict[str, Any]:
    if project_exists(db, project_name):
        raise ProjectExistsError(f"Project '{project_name}' already exists")

    pdf_bytes = fetch_pdf_bytes(pdf_url)
    dialogues = generate_dialogues_from_pdf(pdf_bytes)

    # Insert project first
    db.create_project(project_name, caption, pdf_url)
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
    # Add CTA line with audio
    add_follow_for_more_dialogue(db, project_id, character)

    total_count = len(db.get_all_dialogues_by_project(project_id))
    return {
        'project_id': project_id,
        'dialogue_count': total_count,
        'created_at': get_datetime_str()
    }
