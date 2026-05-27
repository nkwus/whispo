"""Parsers for the templated interview note files."""

import re
from pathlib import Path


_SECTION = re.compile(
    r"^##\s+(.+?)\s*$\n+(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)


def parse_sections(note_path: Path) -> dict[str, str]:
    """Return {header: body} for every `## Section` block in the note.

    Bodies are stripped of leading/trailing whitespace. Empty sections
    are included with empty-string values so callers can distinguish
    "section exists but blank" from "section missing entirely".
    """
    try:
        text = note_path.read_text()
    except (OSError, UnicodeDecodeError):
        return {}
    return {
        m.group(1).strip(): m.group(2).strip()
        for m in _SECTION.finditer(text)
    }
