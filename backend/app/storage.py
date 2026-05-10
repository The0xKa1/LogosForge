from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from .config import settings
from .models import ProjectState


DATA_DIR = settings.data_dir
STATE_PATH = DATA_DIR / "state.json"


class JsonStateStore:
    """Small JSONB-like persistence layer for hackathon local runs.

    The API surface is intentionally close to a database repository, so the
    project can later swap this for Postgres JSONB without changing routes.
    """

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def load(self) -> ProjectState:
        with self._lock:
            if not STATE_PATH.exists():
                return ProjectState()
            return ProjectState.model_validate_json(STATE_PATH.read_text(encoding="utf-8"))

    def save(self, state: ProjectState) -> ProjectState:
        with self._lock:
            STATE_PATH.write_text(
                json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return state

    def reset(self) -> ProjectState:
        state = ProjectState()
        return self.save(state)


store = JsonStateStore()

