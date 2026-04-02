from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static, TextArea

from .models import BoardStatus, Member, TicketFilters


@dataclass(slots=True)
class NoteFormResult:
    text: str
    internal: bool
    detail_description: bool


@dataclass(slots=True)
class TimeFormResult:
    minutes: int
    note: str
    member_query: str
    billable: bool


@dataclass(slots=True)
class AssignFormResult:
    member_query: str


@dataclass(slots=True)
class StatusFormResult:
    status_query: str


class FilterModal(ModalScreen[TicketFilters | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, current: TicketFilters) -> None:
        super().__init__()
        self.current = current

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Filters"),
            Input(value=self.current.status_query, placeholder="Status contains...", id="status-query"),
            Input(value=self.current.company_query, placeholder="Company contains...", id="company-query"),
            Input(value=self.current.tech_query, placeholder="Tech contains...", id="tech-query"),
            Checkbox("SLA breached only", value=self.current.sla_breached_only, id="sla-only"),
            Horizontal(
                Button("Apply", variant="primary", id="apply"),
                Button("Clear", id="clear"),
                Button("Cancel", id="cancel"),
                id="actions",
            ),
            id="modal-body",
        )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "clear":
            self.dismiss(TicketFilters(board_id=self.current.board_id))
            return
        self.dismiss(
            TicketFilters(
                board_id=self.current.board_id,
                status_query=self.query_one("#status-query", Input).value.strip(),
                company_query=self.query_one("#company-query", Input).value.strip(),
                tech_query=self.query_one("#tech-query", Input).value.strip(),
                sla_breached_only=self.query_one("#sla-only", Checkbox).value,
            )
        )


class NoteModal(ModalScreen[NoteFormResult | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Add note"),
            TextArea(id="note-text"),
            Checkbox("Internal note", value=True, id="internal"),
            Checkbox("Add to detail description", value=False, id="detail-description"),
            Horizontal(
                Button("Save", variant="primary", id="save"),
                Button("Cancel", id="cancel"),
            ),
            id="modal-body",
        )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        text = self.query_one("#note-text", TextArea).text.strip()
        if not text:
            self.query_one(Label).update("Add note (text required)")
            return
        internal = self.query_one("#internal", Checkbox).value
        detail_description = self.query_one("#detail-description", Checkbox).value
        if not internal and not detail_description:
            self.query_one(Label).update("Add note (choose internal note or detail description)")
            return
        self.dismiss(
            NoteFormResult(
                text=text,
                internal=internal,
                detail_description=detail_description,
            )
        )


class TimeModal(ModalScreen[TimeFormResult | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, default_member: str = "") -> None:
        super().__init__()
        self.default_member = default_member

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Log time"),
            Input(value="30", placeholder="Minutes", id="minutes"),
            Input(value=self.default_member, placeholder="Member identifier or name", id="member-query"),
            TextArea(id="time-note"),
            Checkbox("Billable", value=True, id="billable"),
            Horizontal(
                Button("Save", variant="primary", id="save"),
                Button("Cancel", id="cancel"),
            ),
            id="modal-body",
        )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        minutes_text = self.query_one("#minutes", Input).value.strip()
        if not minutes_text.isdigit() or int(minutes_text) <= 0:
            self.query_one(Label).update("Log time (minutes must be a positive integer)")
            return
        note = self.query_one("#time-note", TextArea).text.strip()
        if not note:
            self.query_one(Label).update("Log time (note required)")
            return
        self.dismiss(
            TimeFormResult(
                minutes=int(minutes_text),
                note=note,
                member_query=self.query_one("#member-query", Input).value.strip(),
                billable=self.query_one("#billable", Checkbox).value,
            )
        )


class AssignModal(ModalScreen[AssignFormResult | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, members: list[Member]) -> None:
        super().__init__()
        self.members = members

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Assign ticket"),
            Input(placeholder="Member name or identifier", id="member-query"),
            Static(self._member_preview(""), id="preview"),
            Horizontal(
                Button("Assign", variant="primary", id="save"),
                Button("Cancel", id="cancel"),
            ),
            id="modal-body",
        )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _member_preview(self, query: str) -> str:
        query = query.strip().lower()
        if not query:
            sample = ", ".join(member.label() for member in self.members[:8])
            return f"Type to search members. Sample: {sample}"
        matches = [
            member.label()
            for member in self.members
            if query in member.label().lower()
        ][:8]
        return "Matches: " + (", ".join(matches) if matches else "none")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "member-query":
            self.query_one("#preview", Static).update(self._member_preview(event.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        query = self.query_one("#member-query", Input).value.strip()
        if not query:
            self.query_one(Label).update("Assign ticket (member query required)")
            return
        self.dismiss(AssignFormResult(member_query=query))


class StatusModal(ModalScreen[StatusFormResult | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, statuses: list[BoardStatus]) -> None:
        super().__init__()
        self.statuses = statuses

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Update status"),
            Input(placeholder="Status name", id="status-query"),
            Static(self._status_preview(""), id="preview"),
            Horizontal(
                Button("Apply", variant="primary", id="save"),
                Button("Cancel", id="cancel"),
            ),
            id="modal-body",
        )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _status_preview(self, query: str) -> str:
        query = query.strip().lower()
        ordered = sorted(self.statuses, key=lambda item: (item.sort_order, item.name.lower()))
        if not query:
            sample = ", ".join(status.name for status in ordered[:8])
            return f"Type to search statuses. Sample: {sample}"
        matches = [status.name for status in ordered if query in status.name.lower()][:8]
        return "Matches: " + (", ".join(matches) if matches else "none")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "status-query":
            self.query_one("#preview", Static).update(self._status_preview(event.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        query = self.query_one("#status-query", Input).value.strip()
        if not query:
            self.query_one(Label).update("Update status (status query required)")
            return
        self.dismiss(StatusFormResult(status_query=query))
