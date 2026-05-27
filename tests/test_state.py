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
    note = tmp_path / "2026-05-20-jane.md"
    note.touch()

    assert state.is_processed(audio) is False
    state.mark_processed(audio, note, "Jane")
    assert state.is_processed(audio) is True

    record = state.get_record(audio)
    assert record is not None
    assert record["note"] == str(note)
    assert record["stakeholder"] == "Jane"


def test_unprocessed_returns_none_record(tmp_path: Path) -> None:
    assert state.get_record(tmp_path / "nothing.m4a") is None
