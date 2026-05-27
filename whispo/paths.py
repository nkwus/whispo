from pathlib import Path

HOME = Path.home()

# Raw side — audio inputs and plain-text transcripts, NOT part of the vault.
DATA_ROOT = HOME / "Documents" / "whispo"
RECORDINGS_DIR = DATA_ROOT / "recordings"
TRANSCRIPTS_DIR = DATA_ROOT / "transcripts"

# Obsidian vault — what you open in Obsidian. Templated notes live here so
# they show up in the file pane; raw transcripts/audio do not.
VAULT_ROOT = DATA_ROOT / "whispo_vault"
NOTES_DIR = VAULT_ROOT / "notes"
TEMPLATES_DIR = VAULT_ROOT / "templates"
TEMPLATE_FILE = TEMPLATES_DIR / "Interview.md"
ATTACHMENTS_DIR = VAULT_ROOT / "_attachments"

CONFIG_DIR = HOME / ".config" / "whispo"
STATE_FILE = CONFIG_DIR / "state.json"

ENGINE = HOME / ".local" / "bin" / "transcribe-interview"
