import json
from pathlib import Path

from whispo.paths import CONFIG_DIR, STATE_FILE


def _load() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return {"processed": {}}
    return {"processed": {}}


def _save(state: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def mark_processed(audio: Path, note: Path, stakeholder: str) -> None:
    state = _load()
    state.setdefault("processed", {})[str(audio.resolve())] = {
        "note": str(note),
        "stakeholder": stakeholder,
    }
    _save(state)


def is_processed(audio: Path) -> bool:
    state = _load()
    return str(audio.resolve()) in state.get("processed", {})


def get_record(audio: Path) -> dict | None:
    state = _load()
    return state.get("processed", {}).get(str(audio.resolve()))
