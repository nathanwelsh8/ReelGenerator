#!/usr/bin/env python3
"""
Bootstrap Higgs Audio package at runtime to avoid long image rebuilds.

This script tries to import boson_multimodal. If missing, it installs the
boson-ai/higgs-audio package from GitHub and retries the import. Exits nonzero
on failure so the caller can decide whether to continue or not.
"""
import sys
import subprocess
import importlib
import os
import time

# Ensure HF cache envs are present so any first-run downloads persist
HF_HOME = os.environ.get("HF_HOME", "/root/.cache/huggingface")
os.environ.setdefault("HF_HOME", HF_HOME)
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", os.path.join(HF_HOME, "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", os.path.join(HF_HOME, "transformers"))

def try_import() -> bool:
    try:
        importlib.import_module("boson_multimodal")
        return True
    except Exception:
        return False

def main() -> int:
    if try_import():
        print("bootstrap_higgs: boson_multimodal already available")
        return 0
    print("bootstrap_higgs: boson_multimodal missing, attempting installation…", flush=True)
    # Build pip install spec with optional ref pinning
    repo_ref = os.environ.get("HIGGS_AUDIO_REPO_REF")  # branch/tag/commit
    repo_spec = "git+https://github.com/boson-ai/higgs-audio.git"
    if repo_ref:
        repo_spec = repo_spec + f"@{repo_ref}"

    # Prefer quiet, resilient install; rely on image's Python & pip
    base_cmd = [
        sys.executable, "-m", "pip", "install",
        "--no-cache-dir",
        "--progress-bar", "off",
        "--default-timeout", os.environ.get("PIP_DEFAULT_TIMEOUT", "120"),
    ]
    # Retries: pip supports --retries; allow override via env
    retries = int(os.environ.get("PIP_RETRIES", "3"))
    base_cmd += ["--retries", str(retries)]

    attempt = 0
    max_attempts = max(1, int(os.environ.get("HIGGS_BOOTSTRAP_ATTEMPTS", "2")))
    last_code = 0
    while attempt < max_attempts:
        attempt += 1
        print(f"bootstrap_higgs: pip install attempt {attempt}/{max_attempts}")
        cmd = base_cmd + [repo_spec]
        try:
            subprocess.check_call(cmd)
            if try_import():
                print("bootstrap_higgs: boson_multimodal installed successfully")
                return 0
        except subprocess.CalledProcessError as e:
            last_code = e.returncode or 1
            print(f"bootstrap_higgs: pip install failed (code {last_code}); will retry" if attempt < max_attempts else f"bootstrap_higgs: pip install failed (code {last_code})", file=sys.stderr)
            time.sleep(3 * attempt)

    # Fallback: clone + requirements + editable install
    tmp_dir = "/tmp/higgs-audio"
    try:
        print("bootstrap_higgs: falling back to git clone + editable install")
        if os.path.exists(tmp_dir):
            # best effort cleanup of a previous failed attempt
            try:
                import shutil
                shutil.rmtree(tmp_dir)
            except Exception:
                pass
        clone_cmd = ["git", "clone", "https://github.com/boson-ai/higgs-audio.git", tmp_dir]
        subprocess.check_call(clone_cmd)
        if repo_ref:
            subprocess.check_call(["git", "checkout", repo_ref], cwd=tmp_dir)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", os.path.join(tmp_dir, "requirements.txt")])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", tmp_dir])
        if try_import():
            print("bootstrap_higgs: editable install succeeded")
            return 0
    except subprocess.CalledProcessError as e:
        last_code = e.returncode or 1
        print(f"bootstrap_higgs: fallback install failed with code {last_code}", file=sys.stderr)

    print("bootstrap_higgs: installation completed but import still failing", file=sys.stderr)
    return last_code or 2

if __name__ == "__main__":
    sys.exit(main())
