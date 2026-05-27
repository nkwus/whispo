from pathlib import Path

from whispo.notes import parse_sections


SAMPLE_NOTE = """\
---
type: interview
stakeholder:
---

# Interview — Jane (2026-05-20)

## Summary

A three-sentence summary.

## Key claims

- SPEAKER_01: prefers tabs
- SPEAKER_00: prefers spaces

## Open questions


## Action items

- None

---

## Transcript

[SPEAKER_01]: You okay?
"""


def test_parse_sections_extracts_all_headers(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(SAMPLE_NOTE)
    sections = parse_sections(note)
    assert set(sections) == {"Summary", "Key claims", "Open questions", "Action items", "Transcript"}


def test_parse_sections_body_content(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(SAMPLE_NOTE)
    sections = parse_sections(note)
    assert sections["Summary"] == "A three-sentence summary."
    assert "SPEAKER_01: prefers tabs" in sections["Key claims"]
    assert sections["Open questions"] == ""
    # Action items extends until the next ## header; the template's horizontal
    # rule (`---`) is part of its body. We only care that the bullets are there.
    assert sections["Action items"].startswith("- None")


def test_parse_sections_missing_file_returns_empty(tmp_path: Path) -> None:
    assert parse_sections(tmp_path / "does-not-exist.md") == {}


def test_parse_sections_handles_no_headers(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("Just plain text, no markdown headers.")
    assert parse_sections(note) == {}
