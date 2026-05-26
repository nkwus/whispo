from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select


MODEL_OPTIONS = [
    ("large-v3  (best quality, 8 GB+ VRAM)", "large-v3"),
    ("large-v2  (good quality, 6 GB VRAM)", "large-v2"),
    ("medium    (acceptable, 4 GB VRAM)", "medium"),
    ("small     (fastest, 2 GB VRAM)", "small"),
]


class ProcessModal(ModalScreen[tuple[str, str] | None]):
    """Collect stakeholder name + model size before kicking off a run."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, default_stakeholder: str = "", default_model: str = "large-v3"):
        super().__init__()
        self.default_stakeholder = default_stakeholder
        self.default_model = default_model

    def compose(self) -> ComposeResult:
        with Vertical(id="process-modal"):
            yield Label("[b]Process recording[/b]")
            yield Label("")
            yield Label("Stakeholder")
            yield Input(
                value=self.default_stakeholder,
                placeholder="e.g. Jane Doe",
                id="stakeholder",
            )
            yield Label("")
            yield Label("Model")
            yield Select(MODEL_OPTIONS, value=self.default_model, id="model", allow_blank=False)
            yield Label("")
            with Horizontal(id="process-modal-buttons"):
                yield Button("Process", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#stakeholder", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            stakeholder = self.query_one("#stakeholder", Input).value.strip() or "unknown"
            model = self.query_one("#model", Select).value
            self.dismiss((stakeholder, str(model)))
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Pressing Enter in the stakeholder field submits the form.
        if event.input.id == "stakeholder":
            stakeholder = event.value.strip() or "unknown"
            model = self.query_one("#model", Select).value
            self.dismiss((stakeholder, str(model)))
