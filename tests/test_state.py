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
    """Re-processing a recording should keep its persisted speaker map."""
    audio = tmp_path / "sample.m4a"
    audio.touch()
    note = tmp_path / "sample.md"
    note.touch()
    state.mark_processed(audio, note)
    state.set_speakers(audio, {"SPEAKER_00": "Jane"})

    # Re-process (e.g. fresh run)
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

    # Update one
    state.set_speakers(audio, {"SPEAKER_00": "Jane Doe", "SPEAKER_01": "Richard"})
    assert state.get_speakers(audio)["SPEAKER_00"] == "Jane Doe"


def test_set_speakers_is_noop_for_unprocessed_recording(tmp_path: Path) -> None:
    """Should not silently create a phantom record."""
    audio = tmp_path / "unprocessed.m4a"
    audio.touch()
    state.set_speakers(audio, {"SPEAKER_00": "Jane"})
    assert state.get_record(audio) is None
