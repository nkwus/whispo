"""Find and rename SPEAKER_NN labels emitted by pyannote diarization."""

import re
from pathlib import Path


_LABEL = re.compile(r"\bSPEAKER_\d+\b")


def find_speakers(path: Path) -> list[str]:
    """Return sorted unique SPEAKER_NN labels present in the file."""
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []
    return sorted(set(_LABEL.findall(text)))


def rename_speakers(path: Path, mapping: dict[str, str]) -> int:
    """Rewrite path replacing each `SPEAKER_NN` with mapping[label] where defined.

    Returns the number of replacements made. Labels not in the mapping are
    left untouched, so a partial rename is safe.
    """
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return 0

    counter = {"n": 0}

    def replace(match: re.Match) -> str:
        label = match.group(0)
        new = mapping.get(label)
        if new is None:
            return label
        counter["n"] += 1
        return new

    new_text = _LABEL.sub(replace, text)
    if counter["n"]:
        path.write_text(new_text)
    return counter["n"]
