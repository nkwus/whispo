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


def mark_processed(audio: Path, note: Path) -> None:
    """Record that this audio has been processed and where the note landed."""
    state = _load()
    processed = state.setdefault("processed", {})
    key = str(audio.resolve())
    # Preserve any existing fields (e.g. a `speakers` map) on re-process.
    existing = processed.get(key, {})
    existing["note"] = str(note)
    processed[key] = existing
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


# --- Cross-recording speaker roster -----------------------------------------

def speaker_roster() -> list[str]:
    """All speaker names ever entered, alphabetical, deduped."""
    return sorted(set(_load().get("speaker_roster", [])))


def add_to_roster(*names: str) -> list[str]:
    """Add one or more names to the roster. Returns the names that were new.

    Empty strings, whitespace-only, and placeholder labels (SPEAKER_NN)
    are ignored — those aren't real speakers.
    """
    from whispo.speakers import is_placeholder
    state = _load()
    roster = set(state.get("speaker_roster", []))
    added: list[str] = []
    for raw in names:
        name = raw.strip()
        if not name or is_placeholder(name):
            continue
        if name not in roster:
            roster.add(name)
            added.append(name)
    if added:
        state["speaker_roster"] = sorted(roster)
        _save(state)
    return added


def remove_from_roster(name: str) -> bool:
    """Remove a name from the roster. Returns True if it was there."""
    state = _load()
    roster = set(state.get("speaker_roster", []))
    if name not in roster:
        return False
    roster.discard(name)
    state["speaker_roster"] = sorted(roster)
    _save(state)
    return True


def backfill_roster() -> int:
    """Hydrate the roster from every per-recording speakers map.

    Idempotent — already-present names are skipped. Returns the number
    of names newly added. Lets users who renamed before the roster
    feature existed see their speakers without re-renaming.
    """
    names: list[str] = []
    for record in _load().get("processed", {}).values():
        for name in (record.get("speakers", {}) or {}).values():
            if name:
                names.append(name)
    return len(add_to_roster(*names))
