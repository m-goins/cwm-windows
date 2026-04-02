from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings
from .models import Board, BoardStatus, Member, ServiceNote, TicketDetail, TicketFilters, TicketSummary, TimeEntry

logger = logging.getLogger("cwm.api")


class APIError(RuntimeError):
    """Raised on ConnectWise API errors."""

    def __init__(self, message: str, status_code: int | None = None, payload: Any | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload


class ConnectWiseAPI:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            verify=settings.verify_ssl,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        auth = f"{self.settings.company_id}+{self.settings.public_key}:{self.settings.private_key}"
        encoded = base64.b64encode(auth.encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "clientId": self.settings.client_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def close(self) -> None:
        await self.client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> Any:
        logger.debug(
            "HTTP %s %s params=%s payload=%s",
            method,
            path,
            sorted((params or {}).keys()),
            sorted(json.keys()) if isinstance(json, dict) else type(json).__name__ if json is not None else "none",
        )
        try:
            response = await self.client.request(method, path, params=params, json=json)
        except httpx.TimeoutException as exc:
            logger.exception("Timeout on %s %s", method, path)
            raise APIError(f"{method} {path} timed out: {exc}") from exc
        except httpx.RequestError as exc:
            logger.exception("Request error on %s %s", method, path)
            raise APIError(f"{method} {path} request failed: {exc}") from exc
        logger.debug("HTTP %s %s -> %s", method, path, response.status_code)
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            logger.error("HTTP %s %s failed: %s", method, path, payload)
            raise APIError(
                f"{method} {path} failed with HTTP {response.status_code}: {payload}",
                status_code=response.status_code,
                payload=payload,
            )
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return response.text

    async def _paged_get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        page_size: int = 100,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        combined: list[dict[str, Any]] = []
        page = 1
        base_params = dict(params or {})
        while True:
            query = {**base_params, "page": page, "pageSize": page_size}
            logger.debug("Paged fetch %s page=%s page_size=%s", path, page, page_size)
            batch = await self._request("GET", path, params=query)
            if not isinstance(batch, list) or not batch:
                break
            combined.extend(batch)
            if limit is not None and len(combined) >= limit:
                return combined[:limit]
            if len(batch) < page_size:
                break
            page += 1
        return combined

    async def list_boards(self) -> list[Board]:
        payload = await self._paged_get(
            "/service/boards",
            params={"fields": "id,name,inactive", "orderBy": "name asc"},
            page_size=100,
        )
        boards = [Board.from_api(item) for item in payload]
        logger.info("Loaded %s boards", len(boards))
        return [board for board in boards if not board.inactive]

    async def list_board_statuses(self, board_id: int) -> list[BoardStatus]:
        payload = await self._paged_get(
            f"/service/boards/{board_id}/statuses",
            params={
                "fields": "id,name,sortOrder,closedStatus,defaultFlag,inactive",
                "orderBy": "sortOrder asc,name asc",
            },
            page_size=100,
        )
        statuses = [BoardStatus.from_api(board_id, item) for item in payload]
        logger.info("Loaded %s statuses for board=%s", len(statuses), board_id)
        return [status for status in statuses if not status.inactive]

    def _ticket_conditions(self, filters: TicketFilters, status_id: int | None = None) -> str:
        conditions: list[str] = []
        if filters.board_id is not None:
            conditions.append(f"board/id={filters.board_id}")
        if status_id is not None:
            conditions.append(f"status/id={status_id}")
        return " AND ".join(conditions)

    async def list_tickets(
        self,
        filters: TicketFilters,
        *,
        status_id: int | None = None,
        page_size: int = 100,
        limit: int | None = None,
    ) -> list[TicketSummary]:
        fields = ",".join(
            [
                "id",
                "summary",
                "company",
                "board",
                "status",
                "owner",
                "priority",
                "dateEntered",
                "dateResponded",
                "dateUpdated",
                "isInSla",
                "slaStatus",
                "resources",
                "_info",
            ]
        )
        params = {
            "fields": fields,
            "orderBy": "id desc",
        }
        conditions = self._ticket_conditions(filters, status_id=status_id)
        if conditions:
            params["conditions"] = conditions
        payload = await self._paged_get("/service/tickets", params=params, page_size=page_size, limit=limit)
        tickets = [TicketSummary.from_api(item) for item in payload]
        matched = [ticket for ticket in tickets if ticket.matches(filters)]
        logger.info(
            "Loaded %s tickets (%s after local filters) for board=%s",
            len(tickets),
            len(matched),
            filters.board_id,
        )
        return matched

    async def get_ticket(self, ticket_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/service/tickets/{ticket_id}")

    async def list_ticket_notes(self, ticket_id: int, all_notes: bool = True) -> list[ServiceNote]:
        endpoint = "allNotes" if all_notes else "notes"
        payload = await self._paged_get(
            f"/service/tickets/{ticket_id}/{endpoint}",
            params={"fields": "id,text,createdBy,dateCreated,member,internalFlag,internalAnalysisFlag"},
            page_size=100,
        )
        notes = [ServiceNote.from_api(item) for item in payload]
        notes.sort(key=lambda item: item.created_at, reverse=True)
        logger.info("Loaded %s notes for ticket=%s", len(notes), ticket_id)
        return notes

    async def list_ticket_time_entries(self, ticket_id: int) -> list[TimeEntry]:
        conditions = quote(f'(chargeToType="ServiceTicket" OR chargeToType="ProjectTicket") AND chargeToId={ticket_id}', safe='=()" ')
        payload = await self._paged_get(
            "/time/entries",
            params={
                "conditions": conditions,
                "fields": "id,member,timeStart,timeEnd,actualHours,notes,internalNotes,billableOption",
                "orderBy": "timeStart desc",
            },
            page_size=100,
        )
        entries = [TimeEntry.from_api(item) for item in payload]
        logger.info("Loaded %s time entries for ticket=%s", len(entries), ticket_id)
        return entries

    async def load_ticket_detail(self, ticket_id: int) -> TicketDetail:
        ticket_payload, notes, time_entries = await asyncio.gather(
            self.get_ticket(ticket_id),
            self.list_ticket_notes(ticket_id, all_notes=True),
            self.list_ticket_time_entries(ticket_id),
        )
        logger.info("Loaded ticket detail for ticket=%s", ticket_id)
        return TicketDetail.from_api(ticket_payload, notes, time_entries)

    async def list_members(self) -> list[Member]:
        payload = await self._paged_get(
            "/system/members",
            params={"fields": "id,identifier,name"},
            page_size=200,
        )
        members = [Member.from_api(item) for item in payload]
        members.sort(key=lambda item: item.label().lower())
        logger.info("Loaded %s members", len(members))
        return members

    async def add_ticket_note(
        self,
        ticket_id: int,
        *,
        text: str,
        internal: bool,
        detail_description: bool,
    ) -> None:
        payload = {
            "text": text,
            "internalFlag": internal,
            "internalAnalysisFlag": internal,
            "detailDescriptionFlag": detail_description,
            "resolutionFlag": False,
            "processNotifications": False,
        }
        logger.info("Adding note to ticket=%s", ticket_id)
        await self._request("POST", f"/service/tickets/{ticket_id}/notes", json=payload)

    async def add_time_entry(
        self,
        ticket_id: int,
        *,
        minutes: int,
        note: str,
        member_id: int | None,
        billable: bool,
    ) -> None:
        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=minutes)
        payload: dict[str, Any] = {
            "chargeToId": ticket_id,
            "chargeToType": "ServiceTicket",
            "timeStart": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeEnd": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "actualHours": round(minutes / 60.0, 2),
            "notes": note,
            "billableOption": "Billable" if billable else "DoNotBill",
        }
        if member_id is not None:
            payload["member"] = {"id": member_id}
        logger.info("Adding time entry to ticket=%s minutes=%s member_id=%s", ticket_id, minutes, member_id)
        await self._request("POST", "/time/entries", json=payload)

    async def assign_ticket(self, ticket_id: int, member_id: int) -> None:
        patch = [{"op": "replace", "path": "owner", "value": {"id": member_id}}]
        logger.info("Assigning ticket=%s member_id=%s", ticket_id, member_id)
        await self._request("PATCH", f"/service/tickets/{ticket_id}", json=patch)

    async def update_ticket_status(self, ticket_id: int, status_id: int) -> None:
        patch = [{"op": "replace", "path": "status", "value": {"id": status_id}}]
        logger.info("Updating ticket=%s status_id=%s", ticket_id, status_id)
        await self._request("PATCH", f"/service/tickets/{ticket_id}", json=patch)
