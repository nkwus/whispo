"""Async wrapper around the bash `transcribe-interview` engine.

Streams the engine's stdout/stderr and emits structured events the TUI
can render: phase transitions, transcript segments, completion, errors.
"""

import asyncio
import os
import re
from pathlib import Path
from typing import AsyncIterator

from whispo import state
from whispo.paths import ENGINE


_PHASES = [
    ("vad", re.compile(r"Performing voice activity detection")),
    ("transcribe", re.compile(r"Performing transcription")),
    ("align", re.compile(r"Performing alignment")),
    ("diarize", re.compile(r"Performing diarization")),
    ("summary", re.compile(r"Performing summary")),
]
_SEGMENT = re.compile(r"Transcript:\s*\[(\d+(?:\.\d+)?)\s*-->\s*(\d+(?:\.\d+)?)\]\s*(.*)")
_NOISE = re.compile(
    r"GetGpuDevices|ReadFileContents|Failed to detect devices|Failed to open file|"
    r"warnings\.warn|UserWarning|Lightning automatically upgraded"
)


class EngineRun:
    def __init__(self, audio: Path, stakeholder: str, model: str = "large-v3"):
        self.audio = Path(audio)
        self.stakeholder = stakeholder
        self.model = model

    async def run(self) -> AsyncIterator[tuple[str, object]]:
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        cmd = [str(ENGINE), str(self.audio), self.stakeholder, self.model]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
        except FileNotFoundError:
            yield ("error", f"engine not found at {ENGINE}")
            return

        last_phase: str | None = None
        last_line = ""
        assert proc.stdout is not None
        while True:
            chunk = await proc.stdout.readline()
            if not chunk:
                break
            line = chunk.decode(errors="replace").rstrip()
            if not line or _NOISE.search(line):
                continue
            last_line = line

            for phase, pat in _PHASES:
                if pat.search(line):
                    if phase != last_phase:
                        last_phase = phase
                        yield ("phase", phase)
                    break

            m = _SEGMENT.search(line)
            if m:
                start, end, text = float(m.group(1)), float(m.group(2)), m.group(3).strip()
                yield ("segment", (start, end, text))
                continue

            yield ("log", line)

        rc = await proc.wait()
        if rc != 0:
            yield ("error", f"engine exited with code {rc}")
            return

        note_path = Path(last_line) if last_line else None
        if note_path and note_path.exists():
            state.mark_processed(self.audio, note_path, self.stakeholder)
            yield ("done", note_path)
        else:
            yield ("error", "engine returned 0 but no note path was found in output")
