import os
import logging
import json
from db_handler import DBOperation
from services.dialouge_creator import fetch_pdf_from_url, generate_from_pdf_content

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

        # Generate dialogues from PDF
        dialogue_data = generate_from_pdf_content(pdf_content)
        if not dialogue_data or "dialogue_scenes" not in dialogue_data:
            logging.error(f"Could not generate dialogues for project: {title}")
            continue
        
        dialogues = dialogue_data["dialogue_scenes"]

        # Validate dialogues
        required_keys = {"image", "dialogue", "character", "image_search"}
        if not all(required_keys.issubset(d.keys()) for d in dialogues):
            logging.error(f"Generated dialogues for project '{title}' are missing required keys.")
            continue

        # Create project and add dialogues to DB
        project_id = db.create_project(title, caption, pdf_url)
        if not project_id:
            logging.critical(f"Failed to create project record for: {title}")
            continue
        
        print(f"Project '{title}' created with ID: {project_id}")

        db.add_or_update_dialogues(dialogues, project_id)
        
        count_new = len(db.get_dialogues_by_status('NEW', project_id))
        print(f"Added {count_new} new dialogues for project {project_id}.\n")

if __name__ == "__main__":
    add_project_flow()