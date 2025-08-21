import os
import sys
import streamlit as st
import importlib.util
import types

# Ensure root path is in sys.path BEFORE importing internal packages
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from db_handler import DBOperation

# Dynamically load image_converter to avoid path ambiguity in some Streamlit runtimes
img_conv_file = os.path.join(ROOT_DIR, 'services', 'image_converter.py')
_img_spec = importlib.util.spec_from_file_location('image_converter', img_conv_file)
_img_mod = importlib.util.module_from_spec(_img_spec) if _img_spec and _img_spec.loader else types.ModuleType('image_converter')
if _img_spec and _img_spec.loader:
    _img_spec.loader.exec_module(_img_mod)  # type: ignore
save_bytes_as_png = getattr(_img_mod, 'save_bytes_as_png', None)

# Dynamically load CharacterService for uniqueness checks
char_service_file = os.path.join(ROOT_DIR, 'services', 'character_service.py')
_cs_spec = importlib.util.spec_from_file_location('character_service', char_service_file)
_cs_mod = importlib.util.module_from_spec(_cs_spec) if _cs_spec and _cs_spec.loader else types.ModuleType('character_service')
if _cs_spec and _cs_spec.loader:
    _cs_spec.loader.exec_module(_cs_mod)  # type: ignore
CharacterService = getattr(_cs_mod, 'CharacterService', None)

st.set_page_config(page_title="Characters", layout="wide")
st.header("Characters Admin")

DB = DBOperation()
images_dir = os.path.join("image_assests")
os.makedirs(images_dir, exist_ok=True)

# Helpers

def load_characters(include_inactive=True):
    try:
        return DB.get_characters(active_only=not include_inactive)
    except Exception:
        # Direct query fallback
        try:
            conn = DB.connect()
            cur = conn.cursor()
            cur.execute("SELECT id, name, image_path, parrot_ai_path, active FROM characters ORDER BY name ASC;")
            rows = cur.fetchall()
            return [
                {"id": r[0], "name": r[1], "image_path": r[2], "parrot_ai_path": r[3], "active": r[4]}
                for r in rows
            ]
        finally:
            try:
                conn.close()
            except Exception:
                pass

# Add character
st.subheader("Add new character")
with st.form(key="add_char_form"):
    new_name = st.text_input("Name")
    new_slug = st.text_input("Parrot AI slug (e.g., stewie-griffin)")
    new_img = st.file_uploader("Character image (PNG or WEBP)", type=["png", "webp"])  # webp will be converted to png
    submitted = st.form_submit_button("Create")
    if submitted:
        if not new_name or not new_slug or not new_img:
            st.error("All fields are required; image can be PNG or WEBP.")
        else:
            # Enforce unique character name (case-insensitive)
            try:
                if CharacterService is None:
                    raise RuntimeError("CharacterService not available")
                cs = CharacterService()
                cs.ensure_unique_name(new_name.strip())
            except ValueError as ve:
                st.error(str(ve))
                st.stop()
            except Exception as e:
                # If we cannot validate, proceed but warn
                st.warning(f"Name uniqueness could not be verified: {e}")
            # Save image as {character}.png
            safe_basename = f"{new_name.strip().lower().replace(' ', '_')}.png"
            out_path = os.path.join(images_dir, safe_basename)
            # Convert WEBP to PNG if necessary
            try:
                if new_img.type and new_img.type.lower() == 'image/webp' or (new_img.name or '').lower().endswith('.webp'):
                    save_bytes_as_png(new_img.getvalue(), out_path)
                else:
                    # Still normalize via Pillow to be safe
                    save_bytes_as_png(new_img.getvalue(), out_path)
            except Exception as e:
                st.error(f"Failed to process image: {e}")
                st.stop()
            cid = DB.create_character(name=new_name.strip(), parrot_ai_path=new_slug.strip(), image_filename=safe_basename, active=1)
            if cid:
                st.success(f"Character created with id {cid}")
                st.experimental_rerun() if hasattr(st, 'experimental_rerun') else st.rerun()
            else:
                st.error("Failed to create character (check logs for details)")

st.markdown("---")

# Edit existing
st.subheader("Edit character")
chars = load_characters(include_inactive=True)
if not chars:
    st.info("No characters found.")
else:
    options = {f"{c['name']} (id {c['id']})": c for c in chars}
    selected_label = st.selectbox("Select character", list(options.keys()))
    sel = options[selected_label]

    with st.form(key="edit_char_form"):
        st.write(f"Editing: {sel['name']}")
        upd_slug = st.text_input("Parrot AI slug", value=sel.get('parrot_ai_path') or "")
        # Coerce to proper bool; treat 1/'1'/True as active
        raw_active = sel.get('active', 1)
        try:
            default_active = bool(int(raw_active))
        except Exception:
            default_active = bool(raw_active)
        upd_active = st.checkbox("Active", value=default_active)
        upd_img = st.file_uploader("Replace image (PNG or WEBP)", type=["png", "webp"], key="replace_img")
        do_update = st.form_submit_button("Update")

    # Handle update
    if do_update:
        new_img_name = None
        if upd_img is not None:
            new_img_name = f"{sel['name'].strip().lower().replace(' ', '_')}.png"
            try:
                out_path = os.path.join(images_dir, new_img_name)
                if upd_img.type and upd_img.type.lower() == 'image/webp' or (upd_img.name or '').lower().endswith('.webp'):
                    save_bytes_as_png(upd_img.getvalue(), out_path)
                else:
                    save_bytes_as_png(upd_img.getvalue(), out_path)
            except Exception as e:
                st.error(f"Failed to process image: {e}")
                st.stop()
        ok = DB.update_character(sel['id'], parrot_ai_path=upd_slug.strip(), image_filename=new_img_name, active=1 if upd_active else 0)
        if ok:
            st.success("Character updated")
            st.experimental_rerun() if hasattr(st, 'experimental_rerun') else st.rerun()
        else:
            st.error("No changes applied or update failed")

    # Deletion moved to table below

st.markdown("---")

# Characters table
st.subheader("All characters")
rows = load_characters(include_inactive=True)
if not rows:
    st.info("No characters.")
else:
    # Compact table: name, slug, image, status, delete action
    col_names = ["Name", "Parrot slug", "Image", "Active", "Delete"]
    st.write(" ")
    hdr = st.columns([3, 3, 3, 1, 1])
    for c, t in zip(hdr, col_names):
        c.markdown(f"**{t}**")
    for r in rows:
        c1, c2, c3, c4, c5 = st.columns([3, 3, 3, 1, 1])
        c1.write(r.get('name', ''))
        c2.write(r.get('parrot_ai_path', ''))
        try:
            if r.get('image_path'):
                c3.image(os.path.join(images_dir, r['image_path']), width=64)
            else:
                c3.write("-")
        except Exception:
            c3.write(r.get('image_path', '-'))
        c4.write("✅" if bool(r.get('active', 1)) else "⛔️")
        # Delete column with guardrail
        try:
            in_use = DB.character_has_active_projects(r['id'])
        except Exception:
            in_use = False
        if in_use:
            c5.write("🔒")
        else:
            if c5.button("Delete", key=f"del_{r['id']}"):
                ok = DB.delete_character(r['id'])
                if ok:
                    st.success(f"Deleted {r.get('name','character')}")
                    (st.experimental_rerun() if hasattr(st, 'experimental_rerun') else st.rerun())
                else:
                    st.error("Delete failed (see logs)")
