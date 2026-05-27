"""Find and rewrite speaker labels in a note / transcript file.

Two patterns are recognized as "speaker label uses" so renames stay safe
even after the original SPEAKER_NN placeholders have been replaced:

  - `[NAME]:` at the start of a transcript line
  - `- NAME:`  in a Markdown bullet (LLM-generated key claims)

Plain-text occurrences of a name in body prose are deliberately NOT
matched, so a re-rename ("Jane" -> "Jane Doe") won't accidentally
mangle a sentence that mentions "Jane".
"""

import re
from pathlib import Path


_INITIAL_LABEL = re.compile(r"\bSPEAKER_\d+\b")


def find_speakers(path: Path) -> list[str]:
    """Scan for original SPEAKER_NN labels. Used when initializing state."""
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []
    return sorted(set(_INITIAL_LABEL.findall(text)))


def rewrite_speakers(path: Path, mapping: dict[str, str]) -> int:
    """Rewrite path: each `current -> new` pair replaces structured speaker uses.

    `mapping` keys are CURRENT names in the file (SPEAKER_NN initially,
    or whatever name was set by an earlier rename). Values are the desired
    new names. Pairs where old == new (or new is empty) are skipped.

    Returns the total number of replacements made across both patterns.
    """
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return 0

    count = 0
    for old, new in mapping.items():
        if not new or old == new:
            continue
        # `[old]:` -> `[new]:`   (transcript lines)
        bracket_old = f"[{old}]:"
        n_bracket = text.count(bracket_old)
        if n_bracket:
            text = text.replace(bracket_old, f"[{new}]:")
            count += n_bracket
        # `- old:` -> `- new:`   (summary bullets); preserve leading whitespace
        bullet_re = re.compile(rf"^(\s*-\s*){re.escape(old)}(?=:)", re.MULTILINE)
        text, n_bullet = bullet_re.subn(rf"\g<1>{new}", text)
        count += n_bullet

    if count:
        path.write_text(text)
    return count
