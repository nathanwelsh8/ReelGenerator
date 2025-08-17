import streamlit as st
import sqlite3
import random
import os
from typing import List, Dict, Tuple
import html
import time

# Import project logic pieces from existing modules
from db_handler import DBOperation
from services.dialouge_creator import fetch_pdf_from_url, generate_from_pdf_content
from add_projects import FOLLOW_FOR_MORE_DIALOGUE, PETER_FOLLOW_FOR_MORE, STEWIE_FOLLOW_FOR_MORE
from utils import DialougeStatus

st.set_page_config(page_title="Projects", layout="wide")

st.header("Projects")

# Checklist of requirements shown for visibility
st.markdown(
    "- Add new project form (Title, Caption, PDF path)\n- Prevent duplicates by title+pdf_url\n- Run generation flow and insert dialogues + ending follow-for-more\n- Show projects table with embedded video when available"
)

DB = DBOperation()

# (video assets serving removed - video column not shown)


# Helper to safely request a rerun; some Streamlit builds may not expose experimental_rerun
def safe_rerun():
    try:
        st.experimental_rerun()
    except Exception:
        # Fallback: change a query param to force Streamlit to refresh the page
        try:
                st.query_params = {"_rerun": [str(time.time())]}
        except Exception:
            # Last resort: write a message asking the user to manually refresh
            st.info("Please refresh the page to see updates.")

# Helper: validate dialogues

def validate_dialogues(dialogues: List[Dict]) -> Tuple[bool, List[int]]:
    failing = []
    for idx, d in enumerate(dialogues):
        text = d.get("dialogue", "")
        if len(text) > 100:
            failing.append(idx)
    return (len(failing) == 0, failing)


# Helper: add ending dialogue (copied from add_projects.py logic)
def add_ending_dialogue(project_id: int):
    db = DBOperation()
    ending_dialogue = random.choice(FOLLOW_FOR_MORE_DIALOGUE)
    db.add_or_update_dialogues([ending_dialogue], project_id)
    ending_dialogue_id = db.get_dialouge_id(project_id)
    if ending_dialogue_id:
        db.update_status(ending_dialogue_id, DialougeStatus.COMPLETED)


# Duplicate check helper

def project_exists(title: str, pdf_url: str) -> bool:
    try:
        conn = sqlite3.connect(DB.db_name)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM projects WHERE title = ? AND pdf_url = ? LIMIT 1;",
            (title, pdf_url),
        )
        row = cursor.fetchone()
        return row is not None
    finally:
        conn.close()


# --- Form to add a new project ---
with st.form(key="add_project_form"):
    st.subheader("Add new project")
    title = st.text_input("Title")
    caption = st.text_area("Caption")
    pdf_path = st.text_input("PDF path or URL")
    submit = st.form_submit_button("Submit")

    if submit:
        if not title or not caption or not pdf_path:
            st.error("All fields are required.")
        elif project_exists(title, pdf_path):
            st.warning("A project with this title and pdf_path already exists.")
        else:
            spinner = st.spinner("Processing project: this may take a moment...")
            with spinner:
                # Fetch PDF
                pdf_content = fetch_pdf_from_url(pdf_path)
                if not pdf_content:
                    st.error("Failed to fetch PDF from the provided path/URL.")
                else:
                    # Generate dialogues with retries
                    MAX_RETRIES = 3
                    dialogues = None
                    for attempt in range(1, MAX_RETRIES + 1):
                        dialogue_data = generate_from_pdf_content(pdf_content)
                        if not dialogue_data or "dialogue_scenes" not in dialogue_data:
                            if attempt == MAX_RETRIES:
                                st.error("Failed to generate dialogues after multiple attempts.")
                            continue
                        candidate = dialogue_data["dialogue_scenes"]
                        required_keys = {"image", "dialogue", "character", "image_search"}
                        if not all(required_keys.issubset(d.keys()) for d in candidate):
                            if attempt == MAX_RETRIES:
                                st.error("Generated dialogues are missing required keys.")
                            continue
                        ok, failing_idx = validate_dialogues(candidate)
                        if not ok:
                            if attempt == MAX_RETRIES:
                                st.error(f"Dialogue validation failed at indices {failing_idx}.")
                            continue
                        dialogues = candidate
                        break

                    if dialogues is None:
                        st.error("Could not create valid dialogues for the provided PDF.")
                    else:
                        project_id = DB.create_project(title, caption, pdf_path)
                        if not project_id:
                            st.error("Failed to create project in database.")
                        else:
                            DB.add_or_update_dialogues(dialogues, project_id)
                            add_ending_dialogue(project_id)
                            st.success(f"Project '{title}' created with ID {project_id}.")

# --- Toolbar ---
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("Refresh"):
        safe_rerun()
with col2:
    if st.button("Reconcile dialogue statuses"):
        result = DB.reconcile_dialogue_statuses()
        st.info(f"Reconciled: {result}")

# --- Projects table ---
st.subheader("Existing projects")

# Fetch all projects (we'll query for all statuses)
try:
    conn = sqlite3.connect(DB.db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, caption, pdf_url, status, video_path FROM projects ORDER BY id ASC;")
    projects = cursor.fetchall()
finally:
    conn.close()

if not projects:
    st.info("No projects found.")
else:
    # Build a compact HTML table.

    # Create a simple selector to pick a project for editing. Stores selection in session_state.
    project_options = [f"{p[0]} - {p[1]}" for p in projects]
    selected_option = st.selectbox("Select project to edit", project_options, key="proj_select")
    try:
        selected_project_id = int(selected_option.split(" - ")[0])
        st.session_state["selected_project_id"] = selected_project_id
    except Exception:
        selected_project_id = None

    open_col1, open_col2 = st.columns([1, 4])
    with open_col1:
        if st.button("Open Dialogues page for selected project"):
            if selected_project_id:
                # Set query param so the Dialouge page can pick this project when opened
                try:
                        st.query_params = {"project_id": [str(selected_project_id)]}
                except Exception:
                    pass
                # Provide a clickable link to the Dialouge page (some Streamlit versions do not support programmatic rerun/navigation)
                link = f"/?page=Dialouge&project_id={selected_project_id}"
                st.markdown(f"[Open Dialouges for selected project]({link})", unsafe_allow_html=True)
            else:
                st.warning("No project selected.")
    with open_col2:
        if selected_project_id:
            st.markdown(f"Selected project ID: **{selected_project_id}** — You can now click the 'Dialouge' page in the sidebar to view its dialogues.")

    # Render a compact row layout with an Action button per project
    st.markdown("""
    <style>
    .proj-row { display:flex; gap:12px; align-items:flex-start; padding:6px 0; border-bottom:1px solid #eee }
    .proj-col { min-width: 80px; }
    .proj-title { min-width: 260px; font-weight:600 }
    .proj-caption { min-width: 420px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
    </style>
    """, unsafe_allow_html=True)

    # Header
    cols = st.columns([1, 4, 8, 2, 2, 1])
    cols[0].markdown("**ID**")
    cols[1].markdown("**Title**")
    cols[2].markdown("**Caption**")
    cols[3].markdown("**PDF**")
    cols[4].markdown("**Status / Action**")
    cols[5].markdown("**Progress**")

    # Import generator/upload functions
    import threading
    from main import run_flow
    from upload_to_instagram import main as upload_main

    def start_generation_for_project(pid: int):
        # mark project INPROGRESS immediately
        db_local = DBOperation()
        db_local.update_project_status(pid, DialougeStatus.INPROGRESS)

        def worker():
            try:
                run_flow()
            except Exception as e:
                print(f"Error while running flow for project {pid}: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def upload_project(pid: int):
        def worker():
            try:
                upload_main()
            except Exception as e:
                print(f"Upload error for project {pid}: {e}")

        threading.Thread(target=worker, daemon=True).start()

    # Prefetch dialogue counts for all projects in one query to avoid per-row DB hits
    project_ids = [p[0] for p in projects]
    counts_map = {}
    if project_ids:
        try:
            conn = sqlite3.connect(DB.db_name)
            cur = conn.cursor()
            q = (
                "SELECT project_id, COUNT(*) as total, "
                "SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as completed "
                "FROM dialouge_stage WHERE project_id IN ({ids}) GROUP BY project_id;"
            )
            ids = ",".join([str(int(x)) for x in project_ids])
            q = q.replace("{ids}", ids)
            cur.execute(q, (DialougeStatus.COMPLETED,))
            rows_counts = cur.fetchall()
            for r in rows_counts:
                pid_c, total_c, completed_c = r
                counts_map[int(pid_c)] = (int(completed_c or 0), int(total_c or 0))
        except Exception:
            counts_map = {}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # Rows
    for p in projects:
        pid, ptitle, pcaption, ppdf, pstatus, _ = p
        c0, c1, c2, c3, c4, c5 = st.columns([1, 4, 8, 2, 2, 1])
        c0.write(pid)
        c1.write(ptitle)
        # show truncated caption
        cap = pcaption or ""
        c2.write(cap if len(cap) < 120 else cap[:116] + '...')
        c3.markdown(f"[PDF]({html.escape(ppdf, quote=True)})")

        # Determine action button appearance and behavior
        action_clicked = False
        if pstatus == DialougeStatus.NEW or pstatus == DialougeStatus.INPROGRESS:
            if c4.button("🔄", key=f"gen_{pid}"):
                start_generation_for_project(pid)
                action_clicked = True
                st.success(f"Started generation for project {pid}")
        elif pstatus == DialougeStatus.COMPLETED:
            if c4.button("➡️", key=f"upload_{pid}"):
                upload_project(pid)
                action_clicked = True
                st.success(f"Uploading project {pid} to Instagram (in background)")
        else:
            # Other statuses show a disabled button for visibility
            c4.write(pstatus)
        # Progress column: show completed/total using prefetched counts
        completed, total = counts_map.get(pid, (0, 0))
        if total > 0:
            c5.markdown(f"**{completed}/{total}**")
            try:
                # show a small progress bar (fraction)
                frac = float(completed) / float(total) if total > 0 else 0.0
                c5.progress(frac)
            except Exception:
                pass
        else:
            c5.write("")

        if action_clicked:
            safe_rerun()


