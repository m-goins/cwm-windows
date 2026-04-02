from __future__ import annotations

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

from .models import Board, TicketDetail, TicketSummary


class BoardTable(DataTable):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, cursor_type="row", zebra_stripes=True, **kwargs)

    def on_mount(self) -> None:
        self.add_columns("Boards")

    def set_boards(self, boards: list[Board]) -> None:
        self.clear(columns=False)
        for board in boards:
            self.add_row(board.name, key=str(board.id))
        if boards:
            self.move_cursor(row=0, column=0)


class TicketTable(DataTable):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, cursor_type="row", zebra_stripes=True, **kwargs)

    def on_mount(self) -> None:
        self.add_columns("Opened", "ID", "Pri", "Age", "Status", "Company", "Summary", "Tech", "SLA", "Updated")

    def set_tickets(self, tickets: list[TicketSummary], selected_ticket_id: int | None = None) -> None:
        self.clear(columns=False)
        for ticket in tickets:
            self.add_row(
                ticket.date_entered,
                str(ticket.id),
                ticket.priority_badge,
                ticket.age_badge,
                ticket.status_name,
                ticket.company_name,
                ticket.summary,
                ticket.owner_name,
                ticket.sla_badge,
                ticket.last_updated,
                key=str(ticket.id),
            )
        if tickets:
            row_index = 0
            if selected_ticket_id is not None:
                for index, ticket in enumerate(tickets):
                    if ticket.id == selected_ticket_id:
                        row_index = index
                        break
            self.move_cursor(row=row_index, column=0)


class TicketDetailView(VerticalScroll):
    DEFAULT_TEXT = "Select a ticket to load detail."

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, can_focus=True, **kwargs)
        self._body_content = self.DEFAULT_TEXT

    def compose(self) -> ComposeResult:
        yield Static(self._body_content, id="detail-body")

    def _set_body(self, content: str) -> None:
        self._body_content = content
        if self.is_mounted:
            self.query_one("#detail-body", Static).update(content)

    def set_placeholder(self, message: str) -> None:
        self._set_body(message)
        self.scroll_home(animate=False)

    def _format_note(self, created_at: str, created_by: str, text: str) -> str:
        header = f"- [{escape(created_at or '-')}] {escape(created_by or '-')}"
        body = escape(text.strip() or "-").replace("\n", "\n  ")
        return f"{header}\n  {body}"

    def _format_time_entry(self, time_start: str, member_name: str, actual_hours: str, notes: str) -> str:
        header = f"- [{escape(time_start or '-')}] {escape(member_name or '-')} ({escape(actual_hours or '-')})"
        body = escape(notes.strip() or "-").replace("\n", "\n  ")
        return f"{header}\n  {body}"

    def set_ticket(self, detail: TicketDetail | None) -> None:
        if detail is None:
            self._set_body(self.DEFAULT_TEXT)
            self.scroll_home(animate=False)
            return

        ticket = detail.ticket
        notes = "\n".join(
            self._format_note(note.created_at, note.created_by, note.text)
            for note in detail.notes
        ) or "- No notes"
        time_entries = "\n".join(
            self._format_time_entry(entry.time_start, entry.member_name, entry.actual_hours, entry.notes)
            for entry in detail.time_entries
        ) or "- No time entries"

        body = "\n".join(
            [
                f"[b]#{ticket.id}[/b] {escape(ticket.summary)}",
                "",
                f"[b]Company:[/b] {escape(ticket.company_name or '-')}",
                f"[b]Board:[/b] {escape(ticket.board_name or '-')}",
                f"[b]Status:[/b] {escape(ticket.status_name or '-')}",
                f"[b]Owner:[/b] {escape(ticket.owner_name or '-')}",
                f"[b]Priority:[/b] {escape(ticket.priority_name or '-')}",
                f"[b]SLA:[/b] {escape(ticket.sla_badge or '-')}",
                f"[b]Opened:[/b] {escape(ticket.date_entered or '-')}",
                f"[b]Updated:[/b] {escape(ticket.last_updated or '-')}",
                f"[b]Contact:[/b] {escape(detail.contact_name or '-')}",
                f"[b]Email:[/b] {escape(detail.contact_email or '-')}",
                "",
                "[b]Description[/b]",
                escape(detail.initial_description or "-").replace("\n", "\n  "),
                "",
                f"[b]Notes ({len(detail.notes)})[/b]",
                notes,
                "",
                f"[b]Time Entries ({len(detail.time_entries)})[/b]",
                time_entries,
            ]
        )
        self._set_body(body)
        self.scroll_home(animate=False)


class FooterHelp(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def set_context(self, context: str) -> None:
        self.update(Text(context))


class StatusBar(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def set_message(self, message: str) -> None:
        self.update(Text(message))


class QueueBar(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def set_context(self, context: str) -> None:
        self.update(Text(context))
