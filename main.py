import os
import logging
import json
import sys
from datetime import datetime
from db_handler import DBOperation
from services.scrap_audio import VoiceGenerator
from services.editor_agent import DynamicVideoEditor
import concurrent.futures
import functools

def process_dialogue(row, db, voice_generator):
    """Processes a single dialogue row to generate audio."""
    dialogue_id, sentence, character, _, _, _, _ = row
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    try:
        logging.info(f"Processing dialogue {dialogue_id}: {sentence}")
        db.update_status(dialogue_id, 'INPROGRESS')
        voice_generator.generate_audio_from_sentence(
            sentence.strip(),
            character.strip().lower(),
            f"{dialogue_id}_{timestamp}",
            db_handler=db,
            dialogue_id=dialogue_id
        )
        logging.info(f"Successfully processed dialogue {dialogue_id}")
    except Exception as e:
        logging.critical(f"Error processing dialogue {dialogue_id}: {e}")
        db.update_status(dialogue_id, 'FAILED')

def run_flow():
    # Setup logging
    # ... (logging setup remains the same)

    video_dir = "video_assets"
    os.makedirs(video_dir, exist_ok=True)

    db = DBOperation()

    # 1. Find a project to process
    project = db.get_project_by_status('INPROGRESS')
    if not project:
        project = db.get_project_by_status('NEW')
        if project:
            db.update_project_status(project[0], 'INPROGRESS')
            logging.info(f"New project {project[0]} status set to INPROGRESS")
        else:
            logging.info("No projects to process.")
            return
    
    project_id = project[0]
    logging.info(f"Processing project ID: {project_id}")

    all_dialogues = db.get_all_dialogues_by_project(project_id)
    if not all_dialogues:
        logging.critical(f"Project with ID {project_id} not found or has no dialogues.")
        logging.info(f"Project with ID {project_id} not found or has no dialogues.")
        return

    voice_generator = VoiceGenerator()

    # 2. Process NEW or FAILED dialogues concurrently
    dialogues_to_process = db.get_dialogues_for_processing(project_id)
    if dialogues_to_process:
        logging.info(f"Processing {len(dialogues_to_process)} dialogues concurrently for project {project_id}...")
        # Using ThreadPoolExecutor to process dialogues in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Create a partial function with fixed db and voice_generator arguments
            task = functools.partial(process_dialogue, db=db, voice_generator=voice_generator)
            # Map the task to all dialogues
            executor.map(task, dialogues_to_process)
    else:
        logging.info("No new or failed dialogues to process.")

    # 3. Generate video if all are COMPLETED
    completed_rows = db.get_dialogues_by_status('COMPLETED', project_id)
    if not completed_rows or len(completed_rows) < len(all_dialogues):
        count_failed = len(db.get_dialogues_by_status('FAILED', project_id))
        count_inprogress = len(db.get_dialogues_by_status('INPROGRESS', project_id))
        logging.critical(f"Not all dialogues are completed for project {project_id}. ({len(completed_rows)}/{len(all_dialogues)} completed, {count_failed} failed, {count_inprogress} in progress). Skipping video generation.")
        logging.info(f"Not all dialogues are completed for project {project_id}. Skipping video generation.")
        return
        
    logging.info("All dialogues completed. Generating video...")
    ready_assets = db.get_ready_assets(project_id)

    video_filename = f"output_video_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    video_output_path = os.path.join(video_dir, video_filename)

    background_video_path = os.path.join(video_dir,"background_videos", "Minecraft Parkour Gameplay.mp4")
    if not os.path.exists(background_video_path):
        logging.warning(f"Background video {background_video_path} not found. Video will not be generated.")
        logging.info(f"Background video {background_video_path} not found. Video will not be generated.")
        return

    editor = DynamicVideoEditor(
        video_path=background_video_path,
        output_path=video_output_path,
        dialogue_data=ready_assets,
    )
    try:
        editor.edit()
        logging.info(f"Video generated at {video_output_path}")
        db.update_project_video_path(project_id, video_output_path)
        db.update_project_status(project_id, 'COMPLETED')
        logging.info(f"Project {project_id} status set to COMPLETED")
    except Exception as e:
        logging.critical(f"Error during video generation: {e}")
        logging.info(f"Error during video generation: {e}")
        return

if __name__ == "__main__":
    run_flow()
