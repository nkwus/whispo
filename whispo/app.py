import asyncio
import subprocess
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, ProgressBar, RichLog, Static
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from whispo import gpu, paths, recordings, speakers, state
from whispo.engine import EngineRun
from whispo.notes import parse_sections
from whispo.recordings import duration_for, format_duration, list_recordings, stakeholder_from_filename
from whispo.screens.process_modal import ProcessModal
from whispo.screens.rename_speakers_modal import RenameSpeakersModal


class _RecordingsWatcher(FileSystemEventHandler):
    """Bridges watchdog (thread) events to the Textual UI (main thread)."""

    def __init__(self, app, on_change) -> None:
        super().__init__()
        self._app = app
        self._on_change = on_change

    def on_any_event(self, event) -> None:
        # Only care about create/delete/move of files (not directory churn).
        if event.is_directory:
            return
        if event.event_type in ("created", "deleted", "moved"):
            self._app.call_from_thread(self._on_change)


class GpuPane(Static):
    """Live VRAM usage + loaded models."""

    def on_mount(self) -> None:
        self._update()
        self.set_interval(2.0, self._update)

    def _update(self) -> None:
        stats = gpu.gpu_stats()
        if not stats:
            self.update("[b red]nvidia-smi unavailable[/b red]")
            return
        used, total = stats["used"], stats["total"]
        pct = (used / total * 100) if total else 0
        bar_width = 28
        filled = int(bar_width * used / total) if total else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        lines = [
            "[b]VRAM[/b]",
            f"  [{bar}]  {used} / {total} MiB  ({pct:.0f}%)",
            "",
            "[b]Loaded on GPU[/b]",
        ]
        if not stats["processes"]:
            lines.append("  [dim](idle)[/dim]")
        else:
            for p in stats["processes"]:
                lines.append(f"  {p['name']:<22} {p['mem']:>5} MiB  pid {p['pid']}")
        self.update("\n".join(lines))


class RecordingsPane(DataTable):
    """File list with a processed-state marker."""

    def __init__(self):
        super().__init__()
        self.paths: list[Path] = []
        self._observer: Observer | None = None

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("", "Recording", "Length")
        self.refresh_list()
        # Watch the recordings dir for instant updates when a file is dropped.
        try:
            paths.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
            self._observer = Observer()
            self._observer.schedule(
                _RecordingsWatcher(self.app, self.refresh_list),
                str(paths.RECORDINGS_DIR),
                recursive=False,
            )
            self._observer.start()
        except Exception:
            self._observer = None
        # Periodic safety-net refresh in case the watcher misses something
        # (e.g., the dir got recreated, an inotify limit was hit).
        self.set_interval(15.0, self.refresh_list)

    def on_unmount(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=1.0)
            self._observer = None

    def refresh_list(self) -> None:
        prev_row = self.cursor_row if self.row_count else 0
        self.clear()
        self.paths = list_recordings()
        for f in self.paths:
            mark = "[green]✓[/green]" if state.is_processed(f) else " "
            dur = format_duration(duration_for(f))
            self.add_row(mark, f.name, dur)
        if self.paths:
            new_row = min(prev_row, len(self.paths) - 1)
            self.move_cursor(row=new_row)

    def current(self) -> Path | None:
        if not self.paths:
            return None
        idx = self.cursor_row
        if 0 <= idx < len(self.paths):
            return self.paths[idx]
        return None


class OutputPane(RichLog):
    """Scrolling log of the current/latest engine run."""

    def on_mount(self) -> None:
        self.markup = True
        self.wrap = True
        self.write("[b cyan]whispo[/b cyan]")
        self.write("")
        self.write("[dim]Select a recording and press [b]P[/b] to process.[/dim]")


# Each phase claims a slice of the overall progress bar.
# Transcribe is the long one and scales by segment timestamps; the others
# just jump to the bottom of their range when entered.
PHASE_RANGES = {
    "vad":        (0, 5),
    "transcribe": (5, 80),
    "align":      (80, 85),
    "diarize":    (85, 92),
    "summary":    (92, 99),
}
PHASE_LABELS = {
    "vad":        "Detecting voice activity",
    "transcribe": "Transcribing",
    "align":      "Aligning timestamps",
    "diarize":    "Diarizing speakers",
    "summary":    "Summarizing with LLM",
}


class StatusBar(Static):
    """Single-line phase + state indicator above the progress bar."""

    def show(self, label: str, *, style: str = "yellow") -> None:
        self.update(f"[b {style}]{label}[/b {style}]")

    def idle(self) -> None:
        self.update("[dim]idle[/dim]")


class WhispoApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #main {
        layout: horizontal;
        height: 1fr;
    }
    #left {
        layout: vertical;
        width: 50;
    }
    #right {
        layout: vertical;
        width: 1fr;
    }
    GpuPane {
        height: 10;
        padding: 1 2;
        border: round $primary;
    }
    RecordingsPane {
        height: 1fr;
        border: round $primary;
    }
    StatusBar {
        height: 1;
        padding: 0 2;
    }
    ProgressBar {
        height: 1;
        padding: 0 2;
        margin-bottom: 1;
    }
    ProgressBar > Bar {
        width: 1fr;
    }
    OutputPane {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    #process-modal {
        align: center middle;
        background: $surface;
        padding: 2 4;
        width: 70;
        height: auto;
        max-height: 22;
        border: thick $accent;
    }
    #process-modal-buttons {
        align: center middle;
        height: auto;
    }
    #process-modal-buttons Button {
        margin: 0 1;
    }
    #rename-modal {
        align: center middle;
        background: $surface;
        padding: 2 4;
        width: 60;
        height: auto;
        max-height: 30;
        border: thick $accent;
    }
    .rename-row {
        height: 3;
        layout: horizontal;
    }
    .rename-label {
        width: 14;
        content-align: left middle;
        padding: 1 0;
    }
    .rename-row Input {
        width: 1fr;
    }
    #rename-buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    #rename-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("p", "process", "Process"),
        Binding("n", "rename_speakers", "Rename speakers"),
        Binding("v", "view_note", "View note"),
        Binding("r", "refresh", "Refresh"),
        Binding("tab", "focus_next", "Next pane", show=False),
        Binding("shift+tab", "focus_previous", "Prev pane", show=False),
        Binding("q", "quit", "Quit"),
    ]

    TITLE = "whispo"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield GpuPane()
                yield RecordingsPane()
            with Vertical(id="right"):
                yield StatusBar("[dim]idle[/dim]")
                yield ProgressBar(total=100, show_eta=False, show_percentage=True)
                yield OutputPane()
        yield Footer()

    def action_refresh(self) -> None:
        self.query_one(RecordingsPane).refresh_list()
        self.query_one(GpuPane)._update()

    def action_rename_speakers(self) -> None:
        rec_pane = self.query_one(RecordingsPane)
        audio = rec_pane.current()
        out = self.query_one(OutputPane)
        if audio is None:
            out.write("[red]No recording selected.[/red]")
            return
        record = state.get_record(audio)
        if not record:
            out.write(f"[yellow]No note for {audio.name} yet — press P to process first.[/yellow]")
            return
        note_path = Path(record["note"])
        if not note_path.exists():
            out.write(f"[red]Note missing on disk: {note_path}[/red]")
            return

        labels = speakers.find_speakers(note_path)
        if not labels:
            out.write("[yellow]No SPEAKER_NN labels found in the note (already renamed?).[/yellow]")
            return

        def on_close(mapping: dict[str, str] | None) -> None:
            if not mapping:
                return
            n_note = speakers.rename_speakers(note_path, mapping)
            # Also update the raw transcript .txt so the two files stay in sync.
            txt_path = paths.TRANSCRIPTS_DIR / f"{note_path.stem}.txt"
            n_txt = speakers.rename_speakers(txt_path, mapping) if txt_path.exists() else 0
            renamed = ", ".join(f"{k}→{v}" for k, v in mapping.items())
            out.write("")
            out.write(f"[b green]Renamed:[/b green] {renamed}")
            out.write(f"[dim]{n_note} occurrences in note, {n_txt} in raw transcript.[/dim]")

        self.push_screen(RenameSpeakersModal(labels), on_close)

    def action_view_note(self) -> None:
        rec_pane = self.query_one(RecordingsPane)
        audio = rec_pane.current()
        out = self.query_one(OutputPane)
        if audio is None:
            out.write("[red]No recording selected.[/red]")
            return
        record = state.get_record(audio)
        if not record:
            out.write(f"[yellow]No note yet for {audio.name} — press P to process.[/yellow]")
            return
        note_path = record.get("note")
        if not note_path or not Path(note_path).exists():
            out.write(f"[red]Recorded note path missing on disk: {note_path}[/red]")
            return
        # Obsidian's URI scheme works whether or not the in-app CLI is enabled
        # and routes through xdg-open → Obsidian's URL handler.
        uri = f"obsidian://open?path={urllib.parse.quote(str(note_path))}"
        try:
            subprocess.Popen(
                ["xdg-open", uri],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            out.write(f"[dim]Opening in Obsidian: {Path(note_path).name}[/dim]")
        except FileNotFoundError:
            out.write("[red]xdg-open not found — can't launch Obsidian.[/red]")

    def action_process(self) -> None:
        rec_pane = self.query_one(RecordingsPane)
        audio = rec_pane.current()
        out = self.query_one(OutputPane)
        if audio is None:
            out.write("[red]No recording selected.[/red]")
            return

        default_stakeholder = stakeholder_from_filename(audio)
        default_model = state.last_model() or "large-v3"

        def on_close(result):
            if not result:
                return
            stakeholder, model = result
            self.run_worker(self._run_engine(audio, stakeholder, model), exclusive=True)

        self.push_screen(
            ProcessModal(default_stakeholder=default_stakeholder, default_model=default_model),
            on_close,
        )

    async def _run_engine(self, audio: Path, stakeholder: str, model: str) -> None:
        out = self.query_one(OutputPane)
        status = self.query_one(StatusBar)
        bar = self.query_one(ProgressBar)

        out.clear()
        out.write(f"[b cyan]Processing[/b cyan]  {audio.name}")
        out.write(f"[dim]Stakeholder:[/dim] {stakeholder}    [dim]Model:[/dim] {model}")

        duration = duration_for(audio) or 0.0
        if duration:
            out.write(f"[dim]Audio length: {format_duration(duration)}[/dim]")
        out.write("")

        bar.update(total=100, progress=0)
        status.show("Loading models")

        current_phase: str | None = None
        # Rough wall-time estimate per phase, so the bar advances even when
        # the engine isn't emitting per-segment lines. Real events snap the
        # bar to the truth; this is just to avoid the dead-air-then-jump UX
        # that whisperx's batched output causes on short clips.
        phase_start = 0.0
        phase_estimate = 0.0

        def estimate_for(phase: str) -> float:
            if phase == "transcribe":
                # whisperx on a recent GPU runs roughly 10-15x realtime.
                # Use 1/10 of audio duration with a 3s floor for tiny clips.
                return max(3.0, (duration or 30.0) / 10.0)
            if phase == "summary":
                # Ollama summary scales with transcript length but ~30s is typical.
                return 30.0
            return 5.0  # vad / align / diarize are short

        tick_handle = None

        def tick():
            # Smoothly fill from the current phase's low toward its high,
            # capped so real events can still leap past us.
            if current_phase not in PHASE_RANGES or phase_estimate <= 0:
                return
            low, high = PHASE_RANGES[current_phase]
            elapsed = time.monotonic() - phase_start
            frac = min(1.0, elapsed / phase_estimate)
            # Leave a small headroom (95% of the slice) so we don't bump into
            # the next phase before its real start event arrives.
            target = low + (high - low) * frac * 0.95
            current = bar.progress or 0
            if target > current:
                bar.update(progress=int(target))

        tick_handle = self.set_interval(0.25, tick)

        try:
            runner = EngineRun(audio, stakeholder, model)
            async for kind, data in runner.run():
                ts = datetime.now().strftime("%H:%M:%S")
                if kind == "phase":
                    current_phase = data
                    phase_start = time.monotonic()
                    phase_estimate = estimate_for(data)
                    low, _high = PHASE_RANGES.get(data, (0, 0))
                    bar.update(progress=low)
                    status.show(PHASE_LABELS.get(data, data))
                    out.write(f"[dim]{ts}[/dim] [b yellow]→[/b yellow] {PHASE_LABELS.get(data, data)}")
                elif kind == "segment":
                    start, end, text = data
                    if current_phase == "transcribe" and duration:
                        low, high = PHASE_RANGES["transcribe"]
                        span = high - low
                        pct = min(100, int(low + (end / duration) * span))
                        bar.update(progress=pct)
                        pct_text = f"[b cyan]{pct:>3d}%[/b cyan] "
                    else:
                        pct_text = ""
                    out.write(
                        f"[dim]{ts}[/dim] {pct_text}"
                        f"[dim][{start:>6.1f} → {end:>6.1f}][/dim] {text}"
                    )
                elif kind == "log":
                    if any(s in str(data).lower() for s in ("error", "exception", "traceback")):
                        out.write(f"[red]{data}[/red]")
                elif kind == "done":
                    bar.update(progress=100)
                    status.show("Done", style="green")
                    out.write("")
                    out.write(f"[b green]✓ Done.[/b green]  note: {Path(data).name}")
                    # Surface the LLM-generated summary inline so the user
                    # doesn't have to open Obsidian to see what was produced.
                    sections = parse_sections(Path(data))
                    summary = sections.get("Summary", "")
                    if summary:
                        out.write("")
                        out.write("[b]Summary[/b]")
                        out.write(summary)
                    claims = sections.get("Key claims", "")
                    if claims:
                        out.write("")
                        out.write("[b]Key claims[/b]")
                        out.write(claims)
                    out.write("")
                    out.write(f"[dim]Press [b]V[/b] to open the full note in Obsidian.[/dim]")
                    state.set_last_model(model)
                    self.query_one(RecordingsPane).refresh_list()
                elif kind == "error":
                    status.show(f"Error: {data}", style="red")
                    out.write("")
                    out.write(f"[b red]✗ Error.[/b red]  {data}")
        finally:
            if tick_handle is not None:
                tick_handle.stop()


def main() -> None:
    WhispoApp().run()


if __name__ == "__main__":
    main()
