import asyncio
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, RichLog, Static

from whispo import gpu, recordings, state
from whispo.engine import EngineRun
from whispo.recordings import duration_for, format_duration, list_recordings, stakeholder_from_filename
from whispo.screens.process_modal import ProcessModal


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

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("", "Recording", "Length")
        self.refresh_list()
        self.set_interval(5.0, self.refresh_list)

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
    GpuPane {
        height: 10;
        padding: 1 2;
        border: round $primary;
    }
    RecordingsPane {
        height: 1fr;
        border: round $primary;
    }
    OutputPane {
        width: 1fr;
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
    """

    BINDINGS = [
        Binding("p", "process", "Process"),
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
            yield OutputPane()
        yield Footer()

    def action_refresh(self) -> None:
        self.query_one(RecordingsPane).refresh_list()
        self.query_one(GpuPane)._update()

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

        def on_close(result):
            if not result:
                return
            stakeholder, model = result
            self.run_worker(self._run_engine(audio, stakeholder, model), exclusive=True)

        self.push_screen(ProcessModal(default_stakeholder=default_stakeholder), on_close)

    async def _run_engine(self, audio: Path, stakeholder: str, model: str) -> None:
        out = self.query_one(OutputPane)
        out.clear()
        out.write(f"[b cyan]Processing[/b cyan]  {audio.name}")
        out.write(f"[dim]Stakeholder:[/dim] {stakeholder}    [dim]Model:[/dim] {model}")

        # Compute audio duration up front for per-segment % during transcription.
        duration = duration_for(audio) or 0.0
        if duration:
            out.write(f"[dim]Audio length: {format_duration(duration)}[/dim]")
        out.write("")

        phase_label = {
            "vad": "Detecting voice activity",
            "transcribe": "Transcribing",
            "align": "Aligning timestamps",
            "diarize": "Diarizing speakers",
            "summary": "Summarizing with LLM",
        }

        runner = EngineRun(audio, stakeholder, model)
        async for kind, data in runner.run():
            ts = datetime.now().strftime("%H:%M:%S")
            if kind == "phase":
                out.write(f"[dim]{ts}[/dim] [b yellow]→[/b yellow] {phase_label.get(data, data)}")
            elif kind == "segment":
                start, end, text = data
                if duration:
                    pct = min(100, int(end / duration * 100))
                    out.write(
                        f"[dim]{ts}[/dim] [b cyan]{pct:>3d}%[/b cyan] "
                        f"[dim][{start:>6.1f} → {end:>6.1f}][/dim] {text}"
                    )
                else:
                    out.write(f"[dim]{ts}[/dim] [dim][{start:>6.1f} → {end:>6.1f}][/dim] {text}")
            elif kind == "log":
                # quiet on routine engine logs; surface only if it looks important
                if any(s in str(data).lower() for s in ("error", "exception", "traceback")):
                    out.write(f"[red]{data}[/red]")
            elif kind == "done":
                out.write("")
                out.write(f"[b green]✓ Done.[/b green]  note: {data}")
                self.query_one(RecordingsPane).refresh_list()
            elif kind == "error":
                out.write("")
                out.write(f"[b red]✗ Error.[/b red]  {data}")


def main() -> None:
    WhispoApp().run()


if __name__ == "__main__":
    main()
