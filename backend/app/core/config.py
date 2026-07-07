"""
DEPRECATED -- This file is a legacy duplicate.
The live application uses app.config (backend/app/config.py).
This file is only referenced by dead-code directories (app/worker/, app/api/, app/core/logging.py).
Do not add new imports from this module.
TODO: Delete once app/worker/ and app/api/ directories are cleaned up.
"""
# Re-export from the canonical config so any accidental imports still work.
from app.config import settings, Settings, get_settings  # noqa: F401
