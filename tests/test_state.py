from pathlib import Path

import pytest

from whispo import state


@pytest.fixture(autouse=True)
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect state.json to a tmp dir so tests don't clobber real state."""
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(state, "STATE_FILE", state_file)
    monkeypatch.setattr(state, "CONFIG_DIR", tmp_path)
    return state_file


def test_last_model_returns_none_when_unset() -> None:
    assert state.last_model() is None


def test_set_and_get_last_model() -> None:
    state.set_last_model("large-v2")
    assert state.last_model() == "large-v2"


def test_set_last_model_overrides_previous() -> None:
    state.set_last_model("large-v2")
    state.set_last_model("medium")
    assert state.last_model() == "medium"


def test_mark_processed_and_get_record(tmp_path: Path) -> None:
    audio = tmp_path / "sample.m4a"
    audio.touch()
    note = tmp_path / "sample.md"
    note.touch()

    assert state.is_processed(audio) is False
    state.mark_processed(audio, note)
    assert state.is_processed(audio) is True

    record = state.get_record(audio)
    assert record is not None
    assert record["note"] == str(note)


def test_mark_processed_preserves_existing_speakers(tmp_path: Path) -> None:
    audio = tmp_path / "sample.m4a"
    audio.touch()
    note = tmp_path / "sample.md"
    note.touch()
    state.mark_processed(audio, note)
    state.set_speakers(audio, {"SPEAKER_00": "Jane"})

    state.mark_processed(audio, note)
    assert state.get_speakers(audio) == {"SPEAKER_00": "Jane"}


def test_unprocessed_returns_none_record(tmp_path: Path) -> None:
    assert state.get_record(tmp_path / "nothing.m4a") is None


def test_speakers_round_trip(tmp_path: Path) -> None:
    audio = tmp_path / "sample.m4a"
    audio.touch()
    note = tmp_path / "note.md"
    note.touch()
    state.mark_processed(audio, note)

    assert state.get_speakers(audio) == {}

    state.set_speakers(audio, {"SPEAKER_00": "Jane", "SPEAKER_01": "Richard"})
    assert state.get_speakers(audio) == {"SPEAKER_00": "Jane", "SPEAKER_01": "Richard"}

    state.set_speakers(audio, {"SPEAKER_00": "Jane Doe", "SPEAKER_01": "Richard"})
    assert state.get_speakers(audio)["SPEAKER_00"] == "Jane Doe"


def test_set_speakers_is_noop_for_unprocessed_recording(tmp_path: Path) -> None:
    audio = tmp_path / "unprocessed.m4a"
    audio.touch()
    state.set_speakers(audio, {"SPEAKER_00": "Jane"})
    assert state.get_record(audio) is None


# --- speaker_roster ---------------------------------------------------------

def test_roster_empty_initially() -> None:
    assert state.speaker_roster() == []


def test_add_to_roster_dedupes_and_sorts() -> None:
    added = state.add_to_roster("Jane", "Richard", "Jane")
    assert sorted(added) == ["Jane", "Richard"]
    assert state.speaker_roster() == ["Jane", "Richard"]


def test_add_to_roster_returns_only_new_names() -> None:
    state.add_to_roster("Jane")
    added = state.add_to_roster("Jane", "Bob")
    assert added == ["Bob"]


def test_add_to_roster_ignores_placeholders_and_blanks() -> None:
    added = state.add_to_roster("", "  ", "SPEAKER_00", "SPEAKER_42", "Jane")
    assert added == ["Jane"]
    assert state.speaker_roster() == ["Jane"]


def test_remove_from_roster() -> None:
    state.add_to_roster("Jane", "Richard")
    assert state.remove_from_roster("Jane") is True
    assert state.speaker_roster() == ["Richard"]


def test_remove_from_roster_returns_false_when_missing() -> None:
    assert state.remove_from_roster("nobody") is False


def test_backfill_roster_from_speaker_maps(tmp_path: Path) -> None:
    a1 = tmp_path / "a1.m4a"
    a2 = tmp_path / "a2.m4a"
    a1.touch(); a2.touch()
    state.mark_processed(a1, tmp_path / "a1.md")
    state.mark_processed(a2, tmp_path / "a2.md")
    state.set_speakers(a1, {"SPEAKER_00": "Jane", "SPEAKER_01": "Richard"})
    state.set_speakers(a2, {"SPEAKER_00": "Jane", "SPEAKER_01": "Bob"})

    n = state.backfill_roster()
    assert n == 3  # Jane, Richard, Bob (Jane only counted once)
    assert state.speaker_roster() == ["Bob", "Jane", "Richard"]


def test_backfill_roster_is_idempotent(tmp_path: Path) -> None:
    a = tmp_path / "a.m4a"
    a.touch()
    state.mark_processed(a, tmp_path / "a.md")
    state.set_speakers(a, {"SPEAKER_00": "Jane"})
    state.backfill_roster()
    assert state.backfill_roster() == 0
    assert state.speaker_roster() == ["Jane"]
