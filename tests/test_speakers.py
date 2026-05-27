from pathlib import Path

from whispo.speakers import find_speakers, rewrite_speakers


INITIAL_NOTE = """\
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
    note.write_text(INITIAL_NOTE)
    assert find_speakers(note) == ["SPEAKER_00", "SPEAKER_01"]


def test_find_speakers_missing_file_returns_empty(tmp_path: Path) -> None:
    assert find_speakers(tmp_path / "nope.md") == []


def test_rewrite_speakers_initial_rename(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(INITIAL_NOTE)

    n = rewrite_speakers(note, {"SPEAKER_00": "Jane", "SPEAKER_01": "Richard"})
    # 3 transcript brackets + 2 summary bullets
    assert n == 5

    text = note.read_text()
    assert "[Richard]: You okay?" in text
    assert "[Jane]: My roommate's going out of town." in text
    assert "- Richard: prefers tabs" in text
    assert "- Jane: prefers spaces" in text


def test_rewrite_speakers_re_rename_after_first(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(INITIAL_NOTE)
    rewrite_speakers(note, {"SPEAKER_01": "Richard"})

    # Now re-rename Richard -> "Richard Hendricks"
    n = rewrite_speakers(note, {"Richard": "Richard Hendricks"})
    assert n == 3  # 2 brackets + 1 bullet (Richard appears in 1 bullet)

    text = note.read_text()
    assert "Richard Hendricks" in text
    assert "[Richard]" not in text


def test_rewrite_speakers_undo_back_to_original(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(INITIAL_NOTE)
    rewrite_speakers(note, {"SPEAKER_01": "Richard"})
    rewrite_speakers(note, {"Richard": "SPEAKER_01"})

    # Should be back to the original
    assert note.read_text() == INITIAL_NOTE


def test_rewrite_speakers_does_not_match_plain_text(tmp_path: Path) -> None:
    # If "Jane" appears in body prose (not as [Jane]: or - Jane:), it must
    # not be touched by a re-rename of Jane.
    note = tmp_path / "note.md"
    note.write_text("[Jane]: hi\nJane was happy about it.\n- Jane: a claim\n")

    rewrite_speakers(note, {"Jane": "Jane Doe"})
    text = note.read_text()
    assert "[Jane Doe]: hi" in text
    assert "- Jane Doe: a claim" in text
    # Plain prose untouched
    assert "Jane was happy about it." in text


def test_rewrite_speakers_partial_mapping(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(INITIAL_NOTE)

    n = rewrite_speakers(note, {"SPEAKER_01": "Richard"})
    assert n == 3

    text = note.read_text()
    assert "SPEAKER_00" in text  # untouched
    assert "SPEAKER_01" not in text


def test_rewrite_speakers_empty_mapping_is_noop(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(INITIAL_NOTE)
    assert rewrite_speakers(note, {}) == 0
    assert note.read_text() == INITIAL_NOTE


def test_rewrite_speakers_same_value_is_noop(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(INITIAL_NOTE)
    assert rewrite_speakers(note, {"SPEAKER_01": "SPEAKER_01"}) == 0
