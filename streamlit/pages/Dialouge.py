import streamlit as st
import sqlite3
from db_handler import DBOperation
from services.scrap_audio import VoiceGenerator
from utils import DialougeStatus

st.set_page_config(page_title="Dialouge", layout="wide")
st.header("Dialouges")

# safe rerun helper (some streamlit builds may not provide experimental_rerun)
def safe_rerun():
    try:
        st.experimental_rerun()
    except Exception:
        try:
            import time
            st.query_params = {"_rerun": [str(time.time())]}
        except Exception:
            st.info("Please refresh the page to see updates.")

# Read project_id from query params (use stable API `st.query_params`)
query_params = st.query_params
project_id = None
if "project_id" in query_params:
    try:
        # st.query_params maps keys to lists of values
        project_id = int(query_params["project_id"][0])
    except Exception:
        project_id = None

if not project_id:
    # Fallback: check session_state for selected project id (set by Projects page)
    project_id = st.session_state.get("selected_project_id") if "selected_project_id" in st.session_state else None
    if not project_id:
        st.error("No project_id provided. Select a project on the Projects page and click 'Open Dialogues page for selected project'.")
else:
    db = DBOperation()
    # Fetch dialogues for project
    rows = db.get_all_dialogues_by_project(project_id)
    if not rows:
        st.info("No dialogues found for this project.")
    else:
        # Render as a table with regenerate buttons
        st.write(f"Dialogues for project {project_id}")
        cols = st.columns([1, 6, 2, 2])
        cols[0].markdown("**ID**")
        cols[1].markdown("**Sentence**")
        cols[2].markdown("**Status**")
        cols[3].markdown("**Actions**")

        voice_gen = VoiceGenerator()
        for row in rows:
            did, sentence, character, image, image_search, audio, status = row
            c0, c1, c2, c3 = st.columns([1, 6, 2, 2])
            c0.write(did)
            c1.write(sentence)
            c2.write(status)
            # Regenerate button - calls VoiceGenerator to produce audio for this sentence
            if c3.button("Regenerate", key=f"regen_{did}"):
                with st.spinner(f"Regenerating audio for dialogue {did}..."):
                    try:
                        # Use character to pick speaker; fallback to 'peter'
                        speaker = character if character else 'peter'
                        audio_path = voice_gen.generate_audio_from_sentence(sentence, speaker, f"regen_{did}", db_handler=db, dialogue_id=did)
                        if audio_path:
                            st.success(f"Audio generated: {audio_path}")
                        else:
                            st.error("Failed to generate audio.")
                    except Exception as e:
                        st.error(f"Error generating audio: {e}")
                # Refresh page to show updated status/audio
                safe_rerun()
