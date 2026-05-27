from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class RenameSpeakersModal(ModalScreen[dict[str, str] | None]):
    """Modal for renaming speakers. Repeatable: pre-fills with current names.

    Constructor takes a list of (original_label, current_name) tuples so
    the modal can show the immutable SPEAKER_NN as the row label and the
    editable current name in the input. Returns a dict keyed by the
    original label.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, speakers: list[tuple[str, str]]):
        super().__init__()
        self.speakers = list(speakers)

    def compose(self) -> ComposeResult:
        with Vertical(id="rename-modal"):
            yield Label("[b]Rename speakers[/b]")
            yield Label(
                "[dim]Edit, leave alone, or type the original "
                "SPEAKER_NN to undo.[/dim]"
            )
            yield Label("")
            for orig, current in self.speakers:
                with Horizontal(classes="rename-row"):
                    yield Label(orig, classes="rename-label")
                    yield Input(value=current, id=f"input-{orig}")
            yield Label("")
            with Horizontal(id="rename-buttons"):
                yield Button("Apply", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        if self.speakers:
            self.query_one(f"#input-{self.speakers[0][0]}", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _collect(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for orig, _current in self.speakers:
            value = self.query_one(f"#input-{orig}", Input).value.strip()
            if value:
                out[orig] = value
        return out

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.dismiss(self._collect())
        else:
            self.dismiss(None)

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self.dismiss(self._collect())
