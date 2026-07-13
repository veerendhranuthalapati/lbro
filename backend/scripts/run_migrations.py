#!/usr/bin/env python3
"""
Run Alembic migrations programmatically.

This script bypasses the `alembic` CLI entrypoint so that PYTHONPATH
conflicts (a local 'alembic/' directory shadowing the installed package)
cannot break the migration run.  It prepends site-packages to sys.path
before importing alembic, guaranteeing the installed package wins.
"""
import os
import site
import sys


def _fix_path() -> None:
    """Ensure the installed alembic package is found before any local dir."""
    installed_dirs = site.getsitepackages()
    # Remove them first so we can re-insert at position 0 in the right order.
    for sp in installed_dirs:
        if sp in sys.path:
            sys.path.remove(sp)
    for sp in reversed(installed_dirs):
        sys.path.insert(0, sp)


def main() -> None:
    _fix_path()

    # Late-import so the fixed sys.path is in effect.
    from alembic.config import Config  # noqa: PLC0415
    from alembic import command as alembic_command  # noqa: PLC0415

    # alembic.ini lives at /app/alembic.ini (COPY backend/ → /app/)
    ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    ini_path = os.path.abspath(ini_path)

    if not os.path.exists(ini_path):
        sys.exit(f"ERROR: alembic.ini not found at {ini_path}")

    print(f"alembic.ini  : {ini_path}")
    print(f"alembic from : {__import__('alembic').__file__}")
    print("Running: alembic upgrade head")

    cfg = Config(ini_path)
    alembic_command.upgrade(cfg, "head")
    print("Migrations complete.")


if __name__ == "__main__":
    main()
