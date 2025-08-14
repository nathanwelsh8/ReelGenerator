import os
import logging
import json
from typing import List, Dict, Tuple
from db_handler import DBOperation
from services.dialouge_creator import fetch_pdf_from_url, generate_from_pdf_content
from utils import DialougeStatus

def add_project_flow():
    # Setup logging
    os.makedirs("runtime_logs", exist_ok=True)
    logging.basicConfig(
        filename="runtime_logs/flow_log.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    chat_json_path = "chat.json"

    # 1. Read chat.json
    if not os.path.exists(chat_json_path):
        logging.critical(f"Input file {chat_json_path} not found.")
        print(f"Input file {chat_json_path} not found.")
        return
    with open(chat_json_path, "r", encoding="utf-8") as f:
        try:
            projects = json.load(f)
        except Exception as e:
            logging.critical(f"Failed to parse {chat_json_path}: {e}")
            print(f"Failed to parse {chat_json_path}: {e}")
            return

    db = DBOperation()

    def validate_dialogues(dialogues: List[Dict]) -> Tuple[bool, List[int]]:
        """Validate dialogue entries: each 'dialogue' field must be <= 100 characters.
        Returns (is_valid, indices_of_failures)."""
        failing = []
        for idx, d in enumerate(dialogues):
            text = d.get("dialogue", "")
            if len(text) > 100:
                failing.append(idx)
        return (len(failing) == 0, failing)

    MAX_RETRIES = 3

    for project_data in projects:
        title = project_data.get('title', '')
        caption = project_data.get('caption', '')
        pdf_url = project_data.get('pdf_path', '')

        if not all([title, caption, pdf_url]):
            logging.warning(f"Skipping project with incomplete data: {project_data}")
            continue

        print(f"Processing project: {title}")

        # Fetch PDF from URL
        pdf_content = fetch_pdf_from_url(pdf_url)
        
        if not pdf_content:
            logging.error(f"Could not fetch PDF for project: {title}")
            continue

        # Generate dialogues from PDF with retries if validation fails
        dialogues = None
        for attempt in range(1, MAX_RETRIES + 1):
            dialogue_data = generate_from_pdf_content(pdf_content)
            if not dialogue_data or "dialogue_scenes" not in dialogue_data:
                logging.error(f"Attempt {attempt}/{MAX_RETRIES}: Could not generate dialogues for project: {title}")
                if attempt == MAX_RETRIES:
                    logging.critical(f"Giving up generating dialogues for project: {title}")
                continue
            candidate = dialogue_data["dialogue_scenes"]
            required_keys = {"image", "dialogue", "character", "image_search"}
            if not all(required_keys.issubset(d.keys()) for d in candidate):
                logging.error(f"Attempt {attempt}/{MAX_RETRIES}: Missing required keys in generated dialogues for project '{title}'")
                if attempt == MAX_RETRIES:
                    logging.critical(f"Giving up due to missing keys for project: {title}")
                continue
            ok, failing_idx = validate_dialogues(candidate)
            if not ok:
                logging.warning(
                    f"Attempt {attempt}/{MAX_RETRIES}: Dialogue length violations for project '{title}' at indices {failing_idx}. Retrying generation."
                )
                if attempt == MAX_RETRIES:
                    logging.critical(
                        f"Project '{title}' failed validation after {MAX_RETRIES} attempts. Skipping. Violations at indices {failing_idx}."
                    )
                continue
            # Passed validation
            dialogues = candidate
            break

        if dialogues is None:
            # All retries failed
            print(f"Failed to generate valid dialogues for project: {title}")
            continue

        # Create project and add dialogues to DB
        project_id = db.create_project(title, caption, pdf_url)
        if not project_id:
            logging.critical(f"Failed to create project record for: {title}")
            continue
        
        print(f"Project '{title}' created with ID: {project_id}")

        db.add_or_update_dialogues(dialogues, project_id)
        
    count_new = len(db.get_dialogues_by_status(DialougeStatus.NEW, project_id))
    print(f"Added {count_new} new dialogues for project {project_id}.\n")

if __name__ == "__main__":
    add_project_flow()