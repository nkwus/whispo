"""Find and rewrite speaker labels in a note / transcript file.

Speaker names appear in two structured forms in the engine's output:

  - `[NAME]:` at the start of a transcript line
  - `- NAME:` in a Markdown bullet (LLM-generated key claims)

When a placeholder SPEAKER_NN is renamed to a real name, the name is
wrapped in `[[ ]]` so Obsidian renders it as a wikilink — clickable in
the editor, and joinable across notes via Obsidian's graph view. So
the file forms above become:

  - `[[Richard]]:` at the start of a transcript line
  - `- [[Richard]]:` in a Markdown bullet

Placeholder labels (SPEAKER_NN) deliberately stay plain — wrapping them
in `[[ ]]` would create junk Obsidian notes named "SPEAKER_01.md".

Plain-prose occurrences of a name in body text are NOT touched by
renames; the rewrite only matches the structured forms above.
"""

import re
from pathlib import Path


_INITIAL_LABEL = re.compile(r"\bSPEAKER_\d+\b")
_PLACEHOLDER = re.compile(r"\ASPEAKER_\d+\Z")


def _is_placeholder(name: str) -> bool:
    return bool(_PLACEHOLDER.match(name))


def _transcript_form(name: str) -> str:
    """File representation at the start of a transcript line."""
    if _is_placeholder(name):
        return f"[{name}]:"
    return f"[[{name}]]:"


def _bullet_form(name: str) -> str:
    """File representation in a summary bullet."""
    if _is_placeholder(name):
        return f"- {name}:"
    return f"- [[{name}]]:"


def _possible_transcript_forms(name: str) -> list[str]:
    """All file forms we might encounter for this name on disk.

    For real names this includes the legacy single-bracket form left
    behind by earlier whispo versions, so a re-rename migrates them
    forward to wikilinks.
    """
    if _is_placeholder(name):
        return [f"[{name}]:"]
    return [f"[[{name}]]:", f"[{name}]:"]


def _possible_bullet_forms(name: str) -> list[str]:
    if _is_placeholder(name):
        return [f"- {name}:"]
    return [f"- [[{name}]]:", f"- {name}:"]


def find_speakers(path: Path) -> list[str]:
    """Scan for original SPEAKER_NN labels. Used when initializing state."""
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []
    return sorted(set(_INITIAL_LABEL.findall(text)))


def rewrite_speakers(path: Path, mapping: dict[str, str]) -> int:
    """Rewrite path: each `old -> new` pair replaces structured speaker uses.

    `mapping` keys are CURRENT names in the file (SPEAKER_NN initially,
    or whatever name was set by an earlier rename). Values are the desired
    new names. Pairs where old == new (or new is empty) are skipped.

    Real-name targets get wrapped in `[[ ]]`; placeholder targets stay
    plain. The lookup of the OLD form tolerates both bracket variants
    (legacy single-bracket and current double-bracket) so existing notes
    migrate forward on the next rename.

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

        # Bullets first — otherwise the unanchored transcript form
        # `[[Old]]:` would also match inside `- [[Old]]:`.
        new_b = _bullet_form(new)
        for old_b in _possible_bullet_forms(old):
            pattern = re.compile(rf"^(\s*){re.escape(old_b)}", re.MULTILINE)
            text, n_b = pattern.subn(rf"\g<1>{new_b}", text)
            count += n_b

        # Transcript form must be anchored to start-of-line so we don't
        # accidentally match inside other contexts.
        new_t = _transcript_form(new)
        for old_t in _possible_transcript_forms(old):
            pattern = re.compile(rf"^{re.escape(old_t)}", re.MULTILINE)
            text, n_t = pattern.subn(new_t, text)
            count += n_t

    if count:
        path.write_text(text)
    return count
