from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class RenameSpeakersModal(ModalScreen[dict[str, str] | None]):
    """Show one input per detected SPEAKER_NN label; return the rename mapping."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, speakers: list[str]):
        super().__init__()
        self.speakers = speakers

    def compose(self) -> ComposeResult:
        with Vertical(id="rename-modal"):
            yield Label("[b]Rename speakers[/b]")
            yield Label("[dim]Empty fields leave that speaker unchanged.[/dim]")
            yield Label("")
            for sp in self.speakers:
                with Horizontal(classes="rename-row"):
                    yield Label(sp, classes="rename-label")
                    yield Input(placeholder="real name", id=f"input-{sp}")
            yield Label("")
            with Horizontal(id="rename-buttons"):
                yield Button("Apply", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        if self.speakers:
            self.query_one(f"#input-{self.speakers[0]}", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _collect(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for sp in self.speakers:
            new = self.query_one(f"#input-{sp}", Input).value.strip()
            if new:
                mapping[sp] = new
        return mapping

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.dismiss(self._collect())
        else:
            self.dismiss(None)

    def on_input_submitted(self, _: Input.Submitted) -> None:
        # Enter in any input also submits the whole form.
        self.dismiss(self._collect())
