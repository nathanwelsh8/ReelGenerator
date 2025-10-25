"""Migrations package.

Each migration file should expose a `run(db: DBOperation)` function and be
idempotent so it can safely execute multiple times (e.g., on API startup).
"""
# Marks migrations as a package so importlib can discover modules reliably.
