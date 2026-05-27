from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class AddSpeakerModal(ModalScreen[str | None]):
    """Small input for adding a name to the speaker roster."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-speaker-modal"):
            yield Label("[b]Add speaker[/b]")
            yield Label("")
            yield Input(placeholder="e.g. Jane Doe", id="speaker-name")
            yield Label("")
            with Horizontal(id="add-speaker-buttons"):
                yield Button("Add", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#speaker-name", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            name = self.query_one("#speaker-name", Input).value.strip()
            self.dismiss(name or None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)
