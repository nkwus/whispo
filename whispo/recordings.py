import subprocess
from functools import lru_cache
from pathlib import Path

from whispo.paths import RECORDINGS_DIR

AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".opus", ".flac", ".aac", ".ogg"}


def list_recordings() -> list[Path]:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        p for p in RECORDINGS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    )


@lru_cache(maxsize=256)
def get_duration(path_str: str, mtime: float) -> float | None:
    """ffprobe duration in seconds; mtime is part of the cache key so edits invalidate."""
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                path_str,
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return float(out)
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        return None


def duration_for(path: Path) -> float | None:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return get_duration(str(path), mtime)


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
