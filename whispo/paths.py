from pathlib import Path

HOME = Path.home()

DATA_ROOT = HOME / "Documents" / "whispo" / ".obsidian" / "Whispo"
RECORDINGS_DIR = DATA_ROOT / "recordings"
TRANSCRIPTS_DIR = DATA_ROOT / "transcripts"
NOTES_DIR = DATA_ROOT / "notes"
TEMPLATES_DIR = DATA_ROOT / "templates"
TEMPLATE_FILE = TEMPLATES_DIR / "Interview.md"
ATTACHMENTS_DIR = DATA_ROOT / "_attachments"

CONFIG_DIR = HOME / ".config" / "whispo"
STATE_FILE = CONFIG_DIR / "state.json"

ENGINE = HOME / ".local" / "bin" / "transcribe-interview"
