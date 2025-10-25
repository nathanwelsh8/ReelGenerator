"""Migration runner: sequentially execute migration scripts.

Usage (programmatic):
    from migrations.runner import run_all_migrations
    run_all_migrations()

CLI:
    python -m migrations.runner

All migration scripts must expose a `run(db: DBOperation)` function.
They should be idempotent.
"""
from importlib import import_module
from pathlib import Path
from typing import List
import sys, os
from logging import getLogger

# Ensure project root is on sys.path when executed directly (e.g., python migrations/runner.py)
PROJECT_ROOT = os.path.abspath(os.path.join(Path(__file__).parent, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from db_handler import DBOperation

logger = getLogger("migrations")

MIGRATIONS_PACKAGE = 'migrations'


def discover_migration_modules() -> List[str]:
    base = Path(__file__).parent
    modules: List[str] = []
    for py in sorted(base.glob('*.py')):
        if py.name == 'runner.py' or py.name.startswith('__'):
            continue
        modules.append(f"{MIGRATIONS_PACKAGE}.{py.stem}")
    return modules


def run_all_migrations(db_path: str = 'stewie_database.db'):
    db = DBOperation(db_name=db_path)
    # Avoid running schema logic inside DBOperation.__init__ now; ensure __init__ minimal.
    # We assume DBOperation.__init__ will be trimmed separately.
    modules = discover_migration_modules()
    for mod_name in modules:
        mod = import_module(mod_name)
        logger.info(f"Running migration: {mod_name}")
        if hasattr(mod, 'run'):
            mod.run(db)
    print('Migrations completed.')

if __name__ == '__main__':
    run_all_migrations()
    
