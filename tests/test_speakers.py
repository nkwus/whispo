from pathlib import Path

from whispo.speakers import find_speakers, rename_speakers


SAMPLE = """\
## Summary

- SPEAKER_01: prefers tabs
- SPEAKER_00: prefers spaces

## Transcript

[SPEAKER_01]: You okay?
[SPEAKER_00]: My roommate's going out of town.
[SPEAKER_01]: Tabs create smaller file sizes.
"""


def test_find_speakers_returns_sorted_unique_labels(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(SAMPLE)
    assert find_speakers(note) == ["SPEAKER_00", "SPEAKER_01"]


def test_find_speakers_missing_file_returns_empty(tmp_path: Path) -> None:
    assert find_speakers(tmp_path / "nope.md") == []


def test_rename_speakers_replaces_all_matches(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(SAMPLE)

    n = rename_speakers(note, {"SPEAKER_00": "Jane", "SPEAKER_01": "Richard"})
    assert n == 5  # 2 in summary, 3 in transcript

    text = note.read_text()
    assert "SPEAKER_00" not in text
    assert "SPEAKER_01" not in text
    assert "[Richard]: You okay?" in text
    assert "[Jane]: My roommate's going out of town." in text
    assert "- Richard: prefers tabs" in text


def test_rename_speakers_partial_mapping_leaves_others_alone(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(SAMPLE)

    n = rename_speakers(note, {"SPEAKER_01": "Richard"})
    assert n == 3  # only SPEAKER_01 instances

    text = note.read_text()
    assert "SPEAKER_00" in text   # untouched
    assert "SPEAKER_01" not in text
    assert "[Richard]: You okay?" in text


def test_rename_speakers_empty_mapping_is_noop(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(SAMPLE)

    assert rename_speakers(note, {}) == 0
    assert note.read_text() == SAMPLE
