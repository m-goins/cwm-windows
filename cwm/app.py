from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.events import DescendantFocus, Focus
from textual.widgets import Header

from .api import APIError, ConnectWiseAPI
from .config import Settings
from .modals import (
    AssignFormResult,
    AssignModal,
    FilterModal,
    NoteFormResult,
    NoteModal,
    StatusFormResult,
    StatusModal,
    TimeFormResult,
    TimeModal,
)
from .models import BoardStatus, Member, TicketDetail, TicketFilters, TicketSummary
from .state import AppState
from .widgets import BoardTable, FooterHelp, QueueBar, StatusBar, TicketDetailView, TicketTable

logger = logging.getLogger("cwm.app")


class CWMApp(App[None]):
    CSS_PATH = "app.tcss"
    TITLE = "cwm"
    BINDINGS = [
        Binding("q", "quit_or_back", "Quit", show=False),
        Binding("j", "move_down", "Down", show=False),
        Binding("k", "move_up", "Up", show=False),
        Binding("h", "focus_left", "Left", show=False),
        Binding("l", "focus_right", "Right", show=False),
        Binding("x", "toggle_sla_filter", "Toggle SLA", show=False),
        Binding("u", "toggle_updated_sort", "Sort Updated", show=False),
        Binding("i", "toggle_id_sort", "Sort Ticket", show=False),
        Binding("c", "clear_filters", "Clear Filters", show=False),
        Binding("]", "increase_window", "More Tickets", show=False),
        Binding("[", "decrease_window", "Fewer Tickets", show=False),
        Binding("o", "toggle_opened_sort", "Sort Opened", show=False),
        Binding("g", "refresh_data", "Refresh", show=False),
        Binding("/", "edit_filters", "Filters", show=False),
        Binding("enter", "focus_detail", "Open", show=False),
        Binding("n", "add_note", "Note", show=False),
        Binding("t", "log_time", "Time", show=False),
        Binding("a", "assign_ticket", "Assign", show=False),
        Binding("s", "change_status", "Status", show=False),
        Binding("question_mark", "show_help", "Help", show=False),
    ]

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.api = ConnectWiseAPI(settings)
        self.state = AppState()
        self._ticket_reload_lock = asyncio.Lock()
        self._ticket_detail_lock = asyncio.Lock()
        self._suspend_highlight_events = False
        self._closing = False
        self._reload_task: asyncio.Task[None] | None = None
        self._detail_task: asyncio.Task[None] | None = None
        self._background_tasks: set[asyncio.Task[None]] = set()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield QueueBar(id="queue-bar")
        with Horizontal(id="workspace"):
            yield BoardTable(id="boards")
            with Vertical(id="center"):
                yield TicketTable(id="tickets")
            yield TicketDetailView(id="detail")
        with Horizontal(id="bottom-bar"):
            yield StatusBar(id="status")
            yield FooterHelp(id="footer-help")

    async def on_mount(self) -> None:
        logger.info("App mount for %s", self.settings.masked_summary)
        self._set_status(f"Connected config: {self.settings.masked_summary}")
        await self.load_initial_data()
        try:
            self.query_one(BoardTable).focus()
        except NoMatches:
            return
        self._refresh_footer()

    async def on_unmount(self) -> None:
        self._closing = True
        self._cancel_task(self._reload_task)
        self._cancel_task(self._detail_task)
        for task in list(self._background_tasks):
            self._cancel_task(task)
        logger.info("App unmount")
        await self.api.close()

    def _cancel_task(self, task: asyncio.Task[None] | None) -> None:
        if task is not None and not task.done():
            task.cancel()

    def _start_background_task(self, coroutine: Coroutine[object, object, None], description: str) -> None:
        if self._closing:
            return
        task = asyncio.create_task(self._run_background_task(coroutine, description))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _run_background_task(self, coroutine: Coroutine[object, object, None], description: str) -> None:
        try:
            await coroutine
        except asyncio.CancelledError:
            logger.debug("Background task cancelled: %s", description)
            raise
        except Exception:
            logger.exception("Background task failed: %s", description)

    def _schedule_reload(self, reason: str) -> None:
        if self._closing:
            return
        logger.debug("Scheduling reload: %s", reason)
        self._cancel_task(self._reload_task)
        self._reload_task = asyncio.create_task(self._run_reload_task(reason))

    async def _run_reload_task(self, reason: str) -> None:
        try:
            await self.reload_tickets()
        except asyncio.CancelledError:
            logger.debug("Reload cancelled: %s", reason)
            raise
        except Exception:
            logger.exception("Reload task failed: %s", reason)

    def _schedule_detail(self, ticket_id: int, reason: str) -> None:
        if self._closing:
            return
        logger.debug("Scheduling detail load for ticket=%s reason=%s", ticket_id, reason)
        self._cancel_task(self._detail_task)
        self._detail_task = asyncio.create_task(self._run_detail_task(ticket_id, reason))

    async def _run_detail_task(self, ticket_id: int, reason: str) -> None:
        try:
            await self.load_ticket_detail(ticket_id)
        except asyncio.CancelledError:
            logger.debug("Detail load cancelled for ticket=%s reason=%s", ticket_id, reason)
            raise
        except Exception:
            logger.exception("Detail load failed for ticket=%s reason=%s", ticket_id, reason)

    def _refresh_footer(self) -> None:
        if self._closing:
            return
        focused = self.focused
        if focused is None:
            context = "j/k move | h/l pane | o/u/i sort | x SLA | / filters | c clear | [ ] window | g refresh | q quit"
        elif focused.id == "boards":
            context = "j/k board | l tickets | o/u/i sort | x SLA | / filters | c clear | [ ] window | g refresh | q quit"
        elif focused.id == "tickets":
            context = "j/k tickets | h/l pane | Enter detail | o/u/i sort | x SLA | / filters | c clear | [ ] window | n/t/a/s mutate"
        else:
            context = "j/k detail | h tickets | o/u/i sort | x SLA | / filters | c clear | [ ] window | g refresh | n/t/a/s mutate | q quit"
        try:
            self.query_one(FooterHelp).set_context(context)
        except NoMatches:
            return

    def _active_board_name(self) -> str:
        if self.state.filters.board_id is None:
            return "-"
        board = next((item for item in self.state.boards if item.id == self.state.filters.board_id), None)
        return board.name if board is not None else "-"

    def _refresh_queue_bar(self) -> None:
        if self._closing:
            return
        selected = self.state.selected_ticket.ticket.id if self.state.selected_ticket is not None else None
        sort_summary = self._sort_summary()
        status_filter = self.state.filters.status_query or "all"
        company_filter = self.state.filters.company_query or "all"
        tech_filter = self.state.filters.tech_query or "all"
        sla_filter = "breached" if self.state.filters.sla_breached_only else "all"
        ticket_count = len(self.state.displayed_tickets)
        window = f"{ticket_count} shown (limit {self.state.ticket_limit})"
        if ticket_count >= self.state.ticket_limit:
            window = f"first {ticket_count} shown"
        selected_label = f"#{selected}" if selected is not None else "-"
        context = (
            f"board: {self._active_board_name()} | status(/): {status_filter} | company(/): {company_filter} | "
            f"tech(/): {tech_filter} | sla(x): {sla_filter} | sort(o/u/i): {sort_summary} | window([ ]): {window} | "
            f"selected: {selected_label}"
        )
        try:
            self.query_one(QueueBar).set_context(context)
        except NoMatches:
            return

    def _set_status(self, message: str) -> None:
        if self._closing:
            return
        self.state.status_message = message
        try:
            self.query_one(StatusBar).set_message(message)
        except NoMatches:
            return
        self._refresh_queue_bar()

    def _update_title(self) -> None:
        board_name = self._active_board_name()
        filter_summary = self.state.filters.summary()
        sort_summary = self._sort_summary()
        if sort_summary == "api":
            self.sub_title = f"{board_name} | {filter_summary}"
        else:
            self.sub_title = f"{board_name} | sort={sort_summary} | {filter_summary}"
        self._refresh_queue_bar()

    def _sort_summary(self) -> str:
        if self.state.ticket_sort_field == "opened":
            return "opened newest" if self.state.ticket_sort_desc else "opened oldest"
        if self.state.ticket_sort_field == "updated":
            return "updated newest" if self.state.ticket_sort_desc else "updated oldest"
        if self.state.ticket_sort_field == "id":
            return "ticket highest" if self.state.ticket_sort_desc else "ticket lowest"
        return "api order"

    def _selected_ticket_id(self) -> int | None:
        table = self.query_one(TicketTable)
        row_index = table.cursor_row
        if row_index < 0 or row_index >= len(self.state.displayed_tickets):
            return None
        return self.state.displayed_tickets[row_index].id

    def _date_sort_value(self, value: str | None) -> float:
        if not value:
            return 0.0
        text = value.strip()
        if not text:
            return 0.0
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    def _sort_tickets(self, tickets: list[TicketSummary]) -> list[TicketSummary]:
        if self.state.ticket_sort_field == "opened":
            return sorted(
                tickets,
                key=lambda ticket: self._date_sort_value(ticket.opened_at),
                reverse=self.state.ticket_sort_desc,
            )
        if self.state.ticket_sort_field == "updated":
            return sorted(
                tickets,
                key=lambda ticket: self._date_sort_value(ticket.updated_at),
                reverse=self.state.ticket_sort_desc,
            )
        if self.state.ticket_sort_field == "id":
            return sorted(tickets, key=lambda ticket: ticket.id, reverse=self.state.ticket_sort_desc)
        return list(tickets)

    def _render_tickets(self, selected_ticket_id: int | None = None) -> None:
        tickets = self._sort_tickets(self.state.tickets)
        self.state.displayed_tickets = tickets
        table = self.query_one(TicketTable)
        self._suspend_highlight_events = True
        table.set_tickets(tickets, selected_ticket_id=selected_ticket_id)
        self._suspend_highlight_events = False
        self._update_title()

    async def _ensure_members(self) -> list[Member]:
        if not self.state.members:
            self.state.members = await self.api.list_members()
        return self.state.members

    async def _ensure_statuses(self, board_id: int) -> list[BoardStatus]:
        if board_id not in self.state.statuses_by_board:
            self.state.statuses_by_board[board_id] = await self.api.list_board_statuses(board_id)
        return self.state.statuses_by_board[board_id]

    async def load_initial_data(self) -> None:
        try:
            boards = await self.api.list_boards()
            self.state.boards = boards
            logger.info("Initial load got %s boards", len(boards))
            board_table = self.query_one(BoardTable)
            if boards:
                self.state.filters.board_id = boards[0].id
                self._update_title()
            self._suspend_highlight_events = True
            board_table.set_boards(boards)
            self._suspend_highlight_events = False
            if boards:
                await self.reload_tickets()
            else:
                self._set_status("No service boards returned by the API.")
        except APIError as exc:
            logger.error("Initial load failed: %s", exc)
            self._set_status(str(exc))
        finally:
            self._suspend_highlight_events = False

    async def reload_tickets(self) -> None:
        async with self._ticket_reload_lock:
            board_id = self.state.filters.board_id
            if board_id is None:
                return
            self._set_status("Loading tickets...")
            self._update_title()
            logger.info("Reloading tickets for board=%s filters=%s", board_id, self.state.filters.summary())
            try:
                statuses = await self._ensure_statuses(board_id)
                status_id = self._resolve_status_id(self.state.filters.status_query, statuses)
                tickets = await self.api.list_tickets(
                    self.state.filters,
                    status_id=status_id,
                    page_size=100,
                    limit=self.state.ticket_limit,
                )
                selected_ticket_id = self.state.selected_ticket.ticket.id if self.state.selected_ticket is not None else None
                self.state.tickets = tickets
                self._render_tickets(selected_ticket_id=selected_ticket_id)
                if self.state.displayed_tickets:
                    active_ticket_id = selected_ticket_id
                    if active_ticket_id is None or not any(
                        ticket.id == active_ticket_id for ticket in self.state.displayed_tickets
                    ):
                        active_ticket_id = self.state.displayed_tickets[0].id
                    await self.load_ticket_detail(active_ticket_id)
                    self._set_status(f"Loaded {len(tickets)} tickets.")
                else:
                    self.state.selected_ticket = None
                    try:
                        self.query_one(TicketDetailView).set_placeholder("No tickets match the active filters.")
                    except NoMatches:
                        return
                    self._set_status("No tickets match the active filters.")
            except APIError as exc:
                logger.error("Reload failed for board=%s: %s", board_id, exc)
                self._set_status(str(exc))
            finally:
                self._suspend_highlight_events = False

    async def load_ticket_detail(self, ticket_id: int) -> None:
        async with self._ticket_detail_lock:
            try:
                self.query_one(TicketDetailView).set_placeholder(f"Loading ticket #{ticket_id}...")
            except NoMatches:
                return
            try:
                detail = await self.api.load_ticket_detail(ticket_id)
                self.state.selected_ticket = detail
                try:
                    self.query_one(TicketDetailView).set_ticket(detail)
                except NoMatches:
                    return
                self._refresh_queue_bar()
                self._set_status(f"Loaded ticket #{ticket_id}.")
            except APIError as exc:
                logger.error("Detail load failed for ticket=%s: %s", ticket_id, exc)
                self._set_status(str(exc))

    def _resolve_status_id(self, query: str, statuses: list[BoardStatus]) -> int | None:
        text = query.strip().lower()
        if not text:
            return None
        exact = [status for status in statuses if status.name.lower() == text]
        if len(exact) == 1:
            return exact[0].id
        return None

    def _resolve_member(self, query: str, members: list[Member]) -> Member:
        text = query.strip().lower()
        exact = [
            member
            for member in members
            if text in {member.name.lower(), member.identifier.lower(), member.label().lower()}
        ]
        if len(exact) == 1:
            return exact[0]
        matches = [member for member in members if text in member.label().lower()]
        if len(matches) == 1:
            return matches[0]
        preview = ", ".join(member.label() for member in matches[:8]) or "none"
        raise APIError(f"Member lookup for '{query}' is ambiguous. Matches: {preview}")

    def _resolve_status(self, query: str, statuses: list[BoardStatus]) -> BoardStatus:
        text = query.strip().lower()
        exact = [status for status in statuses if status.name.lower() == text]
        if len(exact) == 1:
            return exact[0]
        matches = [status for status in statuses if text in status.name.lower()]
        if len(matches) == 1:
            return matches[0]
        preview = ", ".join(status.name for status in matches[:8]) or "none"
        raise APIError(f"Status lookup for '{query}' is ambiguous. Matches: {preview}")

    async def action_refresh_data(self) -> None:
        self._schedule_reload("manual refresh")

    def _toggle_sort(self, field: str, label: str) -> None:
        if self.state.ticket_sort_field == field:
            self.state.ticket_sort_desc = not self.state.ticket_sort_desc
        else:
            self.state.ticket_sort_field = field
            self.state.ticket_sort_desc = True
        selected_ticket_id = self._selected_ticket_id()
        if self.state.tickets:
            self._render_tickets(selected_ticket_id=selected_ticket_id)
        if field == "id":
            direction = "highest first" if self.state.ticket_sort_desc else "lowest first"
        else:
            direction = "newest first" if self.state.ticket_sort_desc else "oldest first"
        self._set_status(f"Sorting tickets by {label} ({direction}).")
        self._refresh_footer()

    def action_toggle_opened_sort(self) -> None:
        self._toggle_sort("opened", "opened date")

    def action_toggle_updated_sort(self) -> None:
        self._toggle_sort("updated", "last updated")

    def action_toggle_id_sort(self) -> None:
        self._toggle_sort("id", "ticket id")

    def action_toggle_sla_filter(self) -> None:
        self.state.filters.sla_breached_only = not self.state.filters.sla_breached_only
        self._update_title()
        state = "breached only" if self.state.filters.sla_breached_only else "all tickets"
        self._set_status(f"SLA filter set to {state}.")
        self._schedule_reload("sla filter toggled")

    def action_clear_filters(self) -> None:
        board_id = self.state.filters.board_id
        self.state.filters = TicketFilters(board_id=board_id)
        self._update_title()
        self._set_status("Cleared filters.")
        self._schedule_reload("filters cleared")

    def action_increase_window(self) -> None:
        next_limit = min(self.state.ticket_limit + 100, 500)
        if next_limit == self.state.ticket_limit:
            self._set_status("Ticket window is already at the maximum of 500.")
            return
        self.state.ticket_limit = next_limit
        self._update_title()
        self._set_status(f"Ticket window increased to {next_limit}.")
        self._schedule_reload("window increased")

    def action_decrease_window(self) -> None:
        next_limit = max(self.state.ticket_limit - 100, 100)
        if next_limit == self.state.ticket_limit:
            self._set_status("Ticket window is already at the minimum of 100.")
            return
        self.state.ticket_limit = next_limit
        self._update_title()
        self._set_status(f"Ticket window decreased to {next_limit}.")
        self._schedule_reload("window decreased")

    def _handle_filter_result(self, updated: TicketFilters | None) -> None:
        if updated is None:
            return
        updated.board_id = self.state.filters.board_id
        self.state.filters = updated
        logger.info("Filters updated to %s", self.state.filters.summary())
        self._schedule_reload("filter update")

    async def action_edit_filters(self) -> None:
        self.push_screen(FilterModal(self.state.filters), callback=self._handle_filter_result)

    async def _submit_note(self, ticket_id: int, result: NoteFormResult) -> None:
        try:
            logger.info("Submitting note for ticket=%s", ticket_id)
            await self.api.add_ticket_note(
                ticket_id,
                text=result.text,
                internal=result.internal,
                detail_description=result.detail_description,
            )
            self._schedule_reload("note added")
            self._schedule_detail(ticket_id, "note added")
            self._set_status(f"Added note to ticket #{ticket_id}.")
        except APIError as exc:
            self._set_status(str(exc))

    def _handle_note_result(self, ticket_id: int, result: NoteFormResult | None) -> None:
        if result is None:
            return
        self._start_background_task(self._submit_note(ticket_id, result), f"submit note ticket={ticket_id}")

    async def action_add_note(self) -> None:
        ticket_id = self._selected_ticket_id()
        if ticket_id is None:
            self._set_status("Select a ticket first.")
            return
        self.push_screen(NoteModal(), callback=lambda result: self._handle_note_result(ticket_id, result))

    async def _submit_time_entry(self, ticket_id: int, result: TimeFormResult) -> None:
        try:
            members = await self._ensure_members()
            member_id = None
            if result.member_query:
                member_id = self._resolve_member(result.member_query, members).id
            logger.info("Submitting time entry for ticket=%s minutes=%s", ticket_id, result.minutes)
            await self.api.add_time_entry(
                ticket_id,
                minutes=result.minutes,
                note=result.note,
                member_id=member_id,
                billable=result.billable,
            )
            self._schedule_detail(ticket_id, "time added")
            self._set_status(f"Logged {result.minutes} minutes on ticket #{ticket_id}.")
        except APIError as exc:
            self._set_status(str(exc))

    def _handle_time_result(self, ticket_id: int, result: TimeFormResult | None) -> None:
        if result is None:
            return
        self._start_background_task(self._submit_time_entry(ticket_id, result), f"log time ticket={ticket_id}")

    async def action_log_time(self) -> None:
        ticket_id = self._selected_ticket_id()
        if ticket_id is None:
            self._set_status("Select a ticket first.")
            return
        default_member = self.settings.member_identifier or ""
        self.push_screen(
            TimeModal(default_member=default_member),
            callback=lambda result: self._handle_time_result(ticket_id, result),
        )

    async def _submit_assignment(self, ticket_id: int, member_query: str, members: list[Member]) -> None:
        try:
            member = self._resolve_member(member_query, members)
            logger.info("Submitting assignment for ticket=%s member=%s", ticket_id, member.label())
            await self.api.assign_ticket(ticket_id, member.id)
            self._schedule_reload("assignment changed")
            self._schedule_detail(ticket_id, "assignment changed")
            self._set_status(f"Assigned ticket #{ticket_id} to {member.label()}.")
        except APIError as exc:
            self._set_status(str(exc))

    def _handle_assign_result(
        self,
        ticket_id: int,
        members: list[Member],
        result: AssignFormResult | None,
    ) -> None:
        if result is None:
            return
        self._start_background_task(
            self._submit_assignment(ticket_id, result.member_query, members),
            f"assign ticket={ticket_id}",
        )

    async def action_assign_ticket(self) -> None:
        ticket_id = self._selected_ticket_id()
        if ticket_id is None:
            self._set_status("Select a ticket first.")
            return
        try:
            members = await self._ensure_members()
            self.push_screen(
                AssignModal(members),
                callback=lambda result: self._handle_assign_result(ticket_id, members, result),
            )
        except APIError as exc:
            self._set_status(str(exc))

    async def _submit_status_change(self, ticket_id: int, status_query: str, statuses: list[BoardStatus]) -> None:
        try:
            status = self._resolve_status(status_query, statuses)
            logger.info("Submitting status change for ticket=%s status=%s", ticket_id, status.name)
            await self.api.update_ticket_status(ticket_id, status.id)
            self._schedule_reload("status changed")
            self._schedule_detail(ticket_id, "status changed")
            self._set_status(f"Updated ticket #{ticket_id} to {status.name}.")
        except APIError as exc:
            self._set_status(str(exc))

    def _handle_status_result(
        self,
        ticket_id: int,
        statuses: list[BoardStatus],
        result: StatusFormResult | None,
    ) -> None:
        if result is None:
            return
        self._start_background_task(
            self._submit_status_change(ticket_id, result.status_query, statuses),
            f"change status ticket={ticket_id}",
        )

    async def action_change_status(self) -> None:
        ticket_id = self._selected_ticket_id()
        if ticket_id is None:
            self._set_status("Select a ticket first.")
            return
        board_id = self.state.filters.board_id
        if board_id is None:
            self._set_status("No board selected.")
            return
        try:
            statuses = await self._ensure_statuses(board_id)
            self.push_screen(
                StatusModal(statuses),
                callback=lambda result: self._handle_status_result(ticket_id, statuses, result),
            )
        except APIError as exc:
            self._set_status(str(exc))

    async def action_focus_detail(self) -> None:
        self.query_one(TicketDetailView).focus()
        self._refresh_footer()

    def action_show_help(self) -> None:
        self._set_status(
            "Keys: j/k move or scroll, h/l pane, o opened sort, u updated sort, i ticket sort, x SLA toggle, / filters, c clear, [ ] ticket window, g refresh, n/t/a/s mutate, q quit."
        )

    def action_move_down(self) -> None:
        focused = self.focused
        if focused is not None and hasattr(focused, "action_cursor_down"):
            focused.action_cursor_down()
            return
        if focused is not None and focused.id == "detail":
            focused.scroll_down(animate=False)

    def action_move_up(self) -> None:
        focused = self.focused
        if focused is not None and hasattr(focused, "action_cursor_up"):
            focused.action_cursor_up()
            return
        if focused is not None and focused.id == "detail":
            focused.scroll_up(animate=False)

    def action_focus_left(self) -> None:
        focused = self.focused
        if focused is None or focused.id == "detail":
            self.query_one(TicketTable).focus()
        elif focused.id == "tickets":
            self.query_one(BoardTable).focus()
        self.call_after_refresh(self._refresh_footer)

    def action_focus_right(self) -> None:
        focused = self.focused
        if focused is None or focused.id == "boards":
            self.query_one(TicketTable).focus()
        elif focused.id == "tickets":
            self.query_one(TicketDetailView).focus()
        self.call_after_refresh(self._refresh_footer)

    def action_quit_or_back(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()
            return
        self.exit()

    async def on_data_table_row_highlighted(self, event: TicketTable.RowHighlighted | BoardTable.RowHighlighted) -> None:
        if self._suspend_highlight_events:
            return
        if event.data_table.id == "boards":
            row_key = event.row_key
            if row_key is None:
                return
            board_id = int(str(row_key.value))
            if board_id != self.state.filters.board_id:
                self.state.filters.board_id = board_id
                self._schedule_reload("board highlight")
            self._refresh_footer()
            return
        if event.data_table.id == "tickets":
            row_key = event.row_key
            if row_key is None:
                return
            ticket_id = int(str(row_key.value))
            if self.state.selected_ticket is None or self.state.selected_ticket.ticket.id != ticket_id:
                self._schedule_detail(ticket_id, "ticket highlight")
            self._refresh_footer()

    def on_descendant_focus(self, _: DescendantFocus) -> None:
        self.call_after_refresh(self._refresh_footer)

    def on_focus(self, _: Focus) -> None:
        self.call_after_refresh(self._refresh_footer)
