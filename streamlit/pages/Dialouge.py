import streamlit as st
import sqlite3
import os
from db_handler import DBOperation
from services.scrap_audio import VoiceGenerator
from utils import DialougeStatus

st.set_page_config(page_title="Dialouge", layout="wide")
st.header("Dialouges")

# safe rerun helper (some streamlit builds may not provide experimental_rerun)
def safe_rerun():
    try:
        if hasattr(st, 'rerun'):
            st.rerun()
            return
    except Exception:
        pass
    st.session_state['_force_rerun'] = st.session_state.get('_force_rerun', 0) + 1

def resolve_active_project_id():
    # Prefer session_state (most recent UI selection) over potentially stale query params
    sid = st.session_state.get("selected_project_id")
    if sid:
        return sid
    try:
        qp = st.query_params
        if "project_id" in qp:
            return int(qp["project_id"][0])
    except Exception:
        pass
    return None

project_id = resolve_active_project_id()

if not project_id:
    st.error("No project selected. Go to the Projects page and pick a project.")
else:
    db = DBOperation()
    rows = db.get_all_dialogues_by_project(project_id)
    if not rows:
        st.info("No dialogues found for this project.")
    else:
        st.write(f"Dialogues for project {project_id}")
        cols = st.columns([1, 2, 6, 3, 2, 2])
        cols[0].markdown("**ID**")
        cols[1].markdown("**Speaker**")
        cols[2].markdown("**Sentence**")
        cols[3].markdown("**Audio**")
        cols[4].markdown("**Status**")
        cols[5].markdown("**Actions**")

        voice_gen = VoiceGenerator()
        for row in rows:
            did, sentence, character, image, image_search, audio, status = row
            c0, c1, c2, c3, c4, c5 = st.columns([1, 2, 6, 3, 2, 2])
            c0.write(did)
            c1.write(character or "")
            c2.write(sentence)
            if audio and str(audio).strip():
                try:
                    c3.write(os.path.basename(str(audio)))
                except Exception:
                    c3.write(str(audio))
            else:
                c3.write("")
            c4.write(status)
            if c5.button("Regenerate", key=f"regen_{did}"):
                with st.spinner(f"Regenerating audio for dialogue {did}..."):
                    try:
                        speaker = character or 'peter'
                        audio_path = voice_gen.generate_audio_from_sentence(sentence, speaker, f"regen_{did}", db_handler=db, dialogue_id=did)
                        if audio_path:
                            st.success(f"Audio generated: {audio_path}")
                        else:
                            st.error("Failed to generate audio.")
                    except Exception as e:
                        st.error(f"Error generating audio: {e}")
                safe_rerun()
