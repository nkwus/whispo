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


def last_model() -> str | None:
    """Most recently used whisper model size, or None if never set."""
    return _load().get("last_model")


def set_last_model(model: str) -> None:
    state = _load()
    state["last_model"] = model
    _save(state)


def get_speakers(audio: Path) -> dict[str, str]:
    """Persisted speaker map for this recording: {SPEAKER_NN -> current name}.

    Returns {} if the recording has no map yet (never renamed).
    """
    record = get_record(audio) or {}
    return dict(record.get("speakers", {}))


def set_speakers(audio: Path, speakers: dict[str, str]) -> None:
    """Persist the speaker map for an already-processed recording.

    No-op if the recording isn't in the processed index (we don't want to
    silently materialize a phantom record).
    """
    state = _load()
    key = str(audio.resolve())
    processed = state.setdefault("processed", {})
    if key not in processed:
        return
    processed[key]["speakers"] = dict(speakers)
    _save(state)
