import streamlit as st
import sqlite3
import os
from typing import List, Dict, Tuple
import html
import sys
import math

# Ensure root path is in sys.path BEFORE importing internal packages
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Import project logic pieces from existing modules
from db_handler import DBOperation
from utils import DialougeStatus
import importlib.util
import types
# Dynamically load project_service to avoid path ambiguity in Streamlit runtime
service_file = os.path.join(ROOT_DIR, 'services', 'project_service.py')
spec = importlib.util.spec_from_file_location('project_service', service_file)
project_service = importlib.util.module_from_spec(spec) if spec and spec.loader else types.ModuleType('project_service')
if spec and spec.loader:
    spec.loader.exec_module(project_service)  # type: ignore
create_project_with_dialogues = getattr(project_service, 'create_project_with_dialogues')
ProjectExistsError = getattr(project_service, 'ProjectExistsError')
DialogueGenerationError = getattr(project_service, 'DialogueGenerationError')
ProjectValidationError = getattr(project_service, 'ProjectValidationError')
# Load process_project orchestration
try:
    from use_cases.process_project_flow import process_project
except ModuleNotFoundError:
    flow_spec_path = os.path.join(ROOT_DIR, 'use_cases', 'process_project_flow.py')
    flow_spec = importlib.util.spec_from_file_location('process_project_flow', flow_spec_path)
    flow_module = importlib.util.module_from_spec(flow_spec) if flow_spec and flow_spec.loader else types.ModuleType('process_project_flow')
    if flow_spec and flow_spec.loader:
        flow_spec.loader.exec_module(flow_module)  # type: ignore
    process_project = getattr(flow_module, 'process_project')

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
    """Trigger a rerun in a version-agnostic way."""
    try:
        # Streamlit >= 1.30 provides st.rerun
        if hasattr(st, 'rerun'):
            st.rerun()
            return
    except Exception:
        pass
    # Legacy or fallback: mutate session_state sentinel
    st.session_state['_force_rerun'] = st.session_state.get('_force_rerun', 0) + 1


# Duplicate check helper

def project_exists(title: str, pdf_url: str) -> bool:
    # Retained for quick pre-check (avoids extra error surfacing in UI)
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
    character = st.selectbox("Primary Character", ["Stewie", "Peter"], index=0)
    submit = st.form_submit_button("Submit")

    if submit:
        if not title or not caption or not pdf_path:
            st.error("All fields are required.")
        elif project_exists(title, pdf_path):
            st.warning("A project with this title and pdf_path already exists.")
        else:
            with st.spinner("Processing project: this may take a moment..."):
                try:
                    result = create_project_with_dialogues(
                        db=DB,
                        project_name=title,
                        caption=caption,
                        pdf_url=pdf_path,
                        character=character,
                    )
                    st.success(f"Project '{title}' created (ID {result['project_id']}) with {result['dialogue_count']} dialogues.")
                except ProjectExistsError as e:
                    st.warning(str(e))
                except (DialogueGenerationError, ProjectValidationError) as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Unexpected error: {e}")
                finally:
                    safe_rerun()

# --- Toolbar ---
col1, = st.columns([5])

with col1:
    if st.button("Reconcile dialogue statuses"):
        result = DB.reconcile_dialogue_statuses()
        st.info(f"Reconciled: {result}")

# --- Projects table ---
st.subheader("Existing projects")

# Fetch all projects (we'll query for all statuses)
try:
    conn = sqlite3.connect(DB.db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, caption, pdf_url, status, video_path FROM projects ORDER BY id DESC;")
    projects = cursor.fetchall()
finally:
    conn.close()

if not projects:
    st.info("No projects found.")
else:
    # Build select options
    project_options = [f"{p[0]} - {p[1]}" for p in projects]
    id_to_option = {p[0]: f"{p[0]} - {p[1]}" for p in projects}

    # Initialize persistent selected_project_id only once
    if "selected_project_id" not in st.session_state:
        inprog_pid = next((p[0] for p in projects if p[4] == DialougeStatus.INPROGRESS), None)
        st.session_state["selected_project_id"] = inprog_pid if inprog_pid is not None else projects[0][0]

    # Sync only on first load or if the previously selected project vanished
    expected_option = id_to_option.get(st.session_state["selected_project_id"])  # may be None if project removed
    if "proj_select" not in st.session_state:
        # first load: set the select widget value
        if expected_option is not None:
            st.session_state["proj_select"] = expected_option
    else:
        # If selected project was removed, fall back to first option
        if expected_option is None:
            fallback_id = projects[0][0]
            st.session_state["selected_project_id"] = fallback_id
            st.session_state["proj_select"] = id_to_option.get(fallback_id, project_options[0])

    # Render selectbox; user changes update proj_select -> we parse and update selected_project_id
    selected_option = st.selectbox("Select project to edit", project_options, key="proj_select")
    try:
        new_selected_id = int(selected_option.split(" - ")[0])
        st.session_state["selected_project_id"] = new_selected_id
    except Exception:
        pass
    selected_project_id = st.session_state.get("selected_project_id")

    open_col1, = st.columns([5])
    with open_col1:
        if selected_project_id:
            st.markdown(f"Selected project ID: **{selected_project_id}** — You can now click the 'Dialouge' page in the sidebar to view its dialogues.")

    # Orchestration controls
    orch_col1, orch_col2 = st.columns([2,4])
    with orch_col1:
        if st.button("Process Any Pending Project"):
            result = process_project(project_id=None)
            st.session_state['last_orch_result'] = result
            st.toast("Global orchestration pass complete", icon="🔄")
    with orch_col2:
        if 'last_orch_result' in st.session_state:
            res = st.session_state['last_orch_result']
            st.markdown("**Last orchestration result:**")
            st.json(res)

    # --- Progress Polling & Auto Processing ---
    st.markdown("---")
    st.subheader("Processing Progress")

    def project_progress(pid: int):
        dbp = DBOperation()
        all_rows = dbp.get_all_dialogues_by_project(pid) or []
        total = len(all_rows)
        completed = len(dbp.get_dialogues_by_status(DialougeStatus.COMPLETED, pid)) if total else 0
        failed = len(dbp.get_dialogues_by_status(DialougeStatus.FAILED, pid)) if total else 0
        inprogress = len(dbp.get_dialogues_by_status(DialougeStatus.INPROGRESS, pid)) if total else 0
        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'inprogress': inprogress,
            'remaining': max(total - completed - failed - inprogress, 0)
        }

    if 'auto_processing' not in st.session_state:
        st.session_state['auto_processing'] = False

    prog_col1, prog_col2, prog_col3 = st.columns([2,2,6])
    with prog_col1:
        if not st.session_state['auto_processing']:
            if st.button("Start Auto Process", disabled=not selected_project_id):
                if selected_project_id:
                    st.session_state['auto_processing'] = True
                    st.session_state['auto_process_project'] = selected_project_id
                    safe_rerun()
        else:
            if st.button("Stop Auto Process"):
                st.session_state['auto_processing'] = False
                safe_rerun()
    with prog_col2:
        if st.button("Refresh Progress"):
            safe_rerun()
    with prog_col3:
        if selected_project_id:
            stats = project_progress(selected_project_id)
            if stats['total']:
                frac = stats['completed'] / stats['total'] if stats['total'] else 0
                st.progress(frac, text=f"Completed {stats['completed']}/{stats['total']} | Failed {stats['failed']} | InProgress {stats['inprogress']}")
            else:
                st.info("No dialogues yet for this project.")

    # Auto loop execution (single pass per rerun)
    if st.session_state.get('auto_processing'):
        target_pid = st.session_state.get('auto_process_project')
        if target_pid:
            result = process_project(project_id=target_pid)
            st.session_state['last_orch_result'] = result
            # Stop automatically if completed
            stats = project_progress(target_pid)
            if stats['total'] and stats['completed'] == stats['total']:
                st.session_state['auto_processing'] = False
                st.toast("Project processing completed", icon="✅")
            else:
                # Inject an autorefresh for next polling pass
                st.autorefresh(interval=5000, key='auto_proc_refresh')

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
        # Mark INPROGRESS then call orchestrator once (threaded)
        db_local = DBOperation()
        db_local.update_project_status(pid, DialougeStatus.INPROGRESS)
        def worker():
            try:
                result = process_project(project_id=pid)
                st.session_state['last_orch_result'] = result
            except Exception as e:
                print(f"Error while processing project {pid}: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def upload_project(pid: int):
        def worker():
            try:
                upload_main()
            except Exception as e:
                print(f"Upload error for project {pid}: {e}")

        threading.Thread(target=worker, daemon=True).start()

    # --- Pagination (client-side) ---
    PAGE_SIZE = 7
    total_projects = len(projects)
    total_pages = max(math.ceil(total_projects / PAGE_SIZE), 1)
    if 'project_page' not in st.session_state:
        st.session_state['project_page'] = 0
    # Clamp page if out of range (e.g., after deletions)
    if st.session_state['project_page'] > total_pages - 1:
        st.session_state['project_page'] = total_pages - 1
    page = st.session_state['project_page']
    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    visible_projects = projects[start_idx:end_idx]

    pag_col_left_buttons, pag_col_next, pag_col_info = st.columns([1,1,3])
    with pag_col_left_buttons:
        if st.button('First', disabled=page == 0):
            st.session_state['project_page'] = 0
            safe_rerun()
        if st.button('Prev', disabled=page == 0):
            st.session_state['project_page'] -= 1
            safe_rerun()
    with pag_col_next:
        if st.button('Next', disabled=page >= total_pages - 1):
            st.session_state['project_page'] += 1
            safe_rerun()
    with pag_col_info:
        st.markdown(f"Page **{page+1}** / **{total_pages}**  ")

    # Prefetch dialogue counts only for visible projects to reduce queries
    project_ids = [p[0] for p in visible_projects]
    counts_map = {}
    if project_ids:
        try:
            conn = sqlite3.connect(DB.db_name)
            cur = conn.cursor()
            q = (
                "SELECT project_id, COUNT(*) as total, "
                "SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as completed "
                "FROM dialouge_stage WHERE project_id IN ({ids}) "
                "GROUP BY project_id;"
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
    for p in visible_projects:
        pid, ptitle, pcaption, ppdf, pstatus, video_path = p
        c0, c1, c2, c3, c4, c5 = st.columns([1, 4, 8, 2, 2, 1])
        c0.write(pid)
        c1.write(ptitle)
        # show truncated caption
        cap = pcaption or ""
        c2.write(cap if len(cap) < 120 else cap[:116] + '...')
        c3.markdown(f"[PDF]({html.escape(ppdf, quote=True)})")

        # Determine action button appearance and behavior
        action_clicked = False
        completed, total = counts_map.get(pid, (0, 0))
        all_dialogues_done = total > 0 and completed == total
        video_missing = not video_path or str(video_path).strip() == ""

        # If all dialogues are complete but video not generated yet -> show download icon
        if all_dialogues_done and video_missing and pstatus != DialougeStatus.COMPLETED:
            if c4.button("📥", key=f"vid_{pid}"):
                start_generation_for_project(pid)
                action_clicked = True
                st.info(f"Generating video for project {pid} (dialogues already complete)")
        elif pstatus == DialougeStatus.NEW or pstatus == DialougeStatus.INPROGRESS:
            if c4.button("🔄", key=f"gen_{pid}"):
                start_generation_for_project(pid)
                action_clicked = True
                st.success(f"Started processing for project {pid}")
        elif pstatus == DialougeStatus.COMPLETED:
            if c4.button("➡️", key=f"upload_{pid}"):
                upload_project(pid)
                action_clicked = True
                st.success(f"Uploading project {pid} to Instagram (in background)")
        else:
            # Other statuses show a disabled button for visibility
            c4.write(pstatus)
        # Progress column: show completed/total using prefetched counts (already retrieved)
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


