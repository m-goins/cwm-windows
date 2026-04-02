from __future__ import annotations

from dataclasses import dataclass, field

from .models import Board, BoardStatus, Member, TicketDetail, TicketFilters, TicketSummary


@dataclass(slots=True)
class AppState:
    boards: list[Board] = field(default_factory=list)
    statuses_by_board: dict[int, list[BoardStatus]] = field(default_factory=dict)
    members: list[Member] = field(default_factory=list)
    filters: TicketFilters = field(default_factory=TicketFilters)
    tickets: list[TicketSummary] = field(default_factory=list)
    displayed_tickets: list[TicketSummary] = field(default_factory=list)
    ticket_sort_field: str = "api"
    ticket_sort_desc: bool = True
    ticket_limit: int = 100
    status_message: str = ""
    selected_ticket: TicketDetail | None = None
