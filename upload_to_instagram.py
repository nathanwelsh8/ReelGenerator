from instagrapi import Client
import sys
import os
from settings import get_settings
from db_handler import DBOperation
from utils import DialougeStatus
from services.thumbnail_generator import generate as generate_thumbnail
from services.caption_generator import generate_caption

def main():
    settings = get_settings()
    db = DBOperation()

    # Get all completed projects
    completed_projects = db.get_projects_by_status(DialougeStatus.COMPLETED)

    if not completed_projects:
        print("No completed projects to upload.")
        return

    username = settings.INSTAGRAM_USERNAME
    password = settings.INSTAGRAM_PASSWORD
    if not username or not password:
        print("Please set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD environment variables.")
        sys.exit(1)

    cl = Client()
    try:
        cl.login(username, password)
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)

    for project in completed_projects:
        project_id = project['id']
        video_path = project['video_path']
        caption = get_caption(project)

        thumbnail_path = get_thumbnail_path(project)

        if not video_path or not os.path.isfile(video_path):
            print(f"Video file not found for project {project_id}: {video_path}")
            continue

        if not caption:
            print(f"Caption not found for project {project_id}")
            continue

        print(f"Uploading reel for project {project_id}...")
        try:
            media = cl.clip_upload(video_path, caption=caption, thumbnail=thumbnail_path)
            print(f"Reel uploaded successfully! Media ID: {media.pk}")
            # Update project status to UPLOADED
            db.update_project_status(project_id, DialougeStatus.UPLOADED)
            print(f"Project {project_id} status updated to UPLOADED.")
        except Exception as e:
            print(f"Failed to upload reel for project {project_id}: {e}")
            db.update_project_status(project_id, DialougeStatus.FAILED)


def get_thumbnail_path(project:dict)->str:
    print("Generating thumbnail...")
    video_path = project.get('video_path')
    if not video_path or not os.path.isfile(video_path):
        print(f"Video path missing or not found for project {project.get('id')}: {video_path}")
        return None
    try:
        return generate_thumbnail(project['title'], f"thumbnail_{project['id']}", video_path)
    except Exception as e:
        print(f"Thumbnail generation failed for project {project.get('id')}: {e}")
        return None

def get_caption(project:dict)->str:
    print("Generating caption...")
    return generate_caption(project['title'], project['caption'], project['pdf_url'])

if __name__ == "__main__":
    main()
