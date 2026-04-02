from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def ref_id(value: dict[str, Any] | None) -> int | None:
    if not isinstance(value, dict):
        return None
    raw = value.get("id")
    return int(raw) if isinstance(raw, int) or str(raw).isdigit() else None


def ref_name(value: dict[str, Any] | None) -> str:
    if not isinstance(value, dict):
        return ""
    for key in ("name", "identifier", "summary"):
        raw = value.get(key)
        if raw:
            return str(raw)
    return ""


def coalesce(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def format_dt(value: str | None) -> str:
    if not value:
        return "-"
    text = value.strip()
    try:
        normalized = text.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return text


def format_hours(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}h"


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass(slots=True)
class Board:
    id: int
    name: str
    inactive: bool = False

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Board":
        return cls(
            id=int(payload["id"]),
            name=coalesce(payload.get("name"), f"Board {payload['id']}"),
            inactive=bool(payload.get("inactive", False)),
        )


@dataclass(slots=True)
class BoardStatus:
    id: int
    board_id: int
    name: str
    sort_order: int = 0
    closed_status: bool = False
    inactive: bool = False

    @classmethod
    def from_api(cls, board_id: int, payload: dict[str, Any]) -> "BoardStatus":
        return cls(
            id=int(payload["id"]),
            board_id=board_id,
            name=coalesce(payload.get("name"), f"Status {payload['id']}"),
            sort_order=int(payload.get("sortOrder") or 0),
            closed_status=bool(payload.get("closedStatus", False)),
            inactive=bool(payload.get("inactive", False)),
        )


@dataclass(slots=True)
class Member:
    id: int
    identifier: str
    name: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Member":
        return cls(
            id=int(payload["id"]),
            identifier=coalesce(payload.get("identifier")),
            name=coalesce(payload.get("name"), payload.get("identifier"), f"Member {payload['id']}"),
        )

    def label(self) -> str:
        if self.identifier and self.identifier != self.name:
            return f"{self.name} ({self.identifier})"
        return self.name


@dataclass(slots=True)
class ServiceNote:
    id: int
    text: str
    created_by: str
    created_at: str
    internal: bool

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "ServiceNote":
        return cls(
            id=int(payload.get("id") or 0),
            text=coalesce(payload.get("text"), "").strip(),
            created_by=coalesce(payload.get("createdBy"), ref_name(payload.get("member"))),
            created_at=format_dt(payload.get("dateCreated")),
            internal=bool(payload.get("internalFlag") or payload.get("internalAnalysisFlag")),
        )


@dataclass(slots=True)
class TimeEntry:
    id: int
    member_name: str
    time_start: str
    time_end: str
    actual_hours: str
    notes: str
    billable_option: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "TimeEntry":
        return cls(
            id=int(payload.get("id") or 0),
            member_name=coalesce(ref_name(payload.get("member")), payload.get("enteredBy")),
            time_start=format_dt(payload.get("timeStart")),
            time_end=format_dt(payload.get("timeEnd")),
            actual_hours=format_hours(payload.get("actualHours")),
            notes=coalesce(payload.get("notes"), payload.get("internalNotes")),
            billable_option=coalesce(payload.get("billableOption")),
        )


@dataclass(slots=True)
class TicketFilters:
    board_id: int | None = None
    status_query: str = ""
    company_query: str = ""
    tech_query: str = ""
    sla_breached_only: bool = False

    def summary(self) -> str:
        parts: list[str] = []
        if self.status_query:
            parts.append(f"status={self.status_query}")
        if self.company_query:
            parts.append(f"company~{self.company_query}")
        if self.tech_query:
            parts.append(f"tech~{self.tech_query}")
        if self.sla_breached_only:
            parts.append("sla=breached")
        return ", ".join(parts) if parts else "no extra filters"


@dataclass(slots=True)
class TicketSummary:
    id: int
    summary: str
    company_name: str
    board_name: str
    status_name: str
    owner_name: str
    priority_name: str
    last_updated: str
    updated_at: str
    sla_status: str
    is_in_sla: bool | None
    date_entered: str
    opened_at: str
    raw: dict[str, Any] = field(repr=False)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "TicketSummary":
        info = payload.get("_info") or {}
        last_updated = coalesce(
            info.get("lastUpdated"),
            payload.get("dateUpdated"),
            payload.get("dateResponded"),
            payload.get("dateEntered"),
        )
        opened_at = coalesce(
            payload.get("dateEntered"),
            info.get("dateEntered"),
        )
        return cls(
            id=int(payload["id"]),
            summary=coalesce(payload.get("summary"), f"Ticket {payload['id']}"),
            company_name=coalesce(ref_name(payload.get("company")), payload.get("companyName")),
            board_name=coalesce(ref_name(payload.get("board"))),
            status_name=coalesce(ref_name(payload.get("status")), payload.get("slaStatus")),
            owner_name=coalesce(ref_name(payload.get("owner")), payload.get("resources")),
            priority_name=coalesce(ref_name(payload.get("priority")), payload.get("severity")),
            last_updated=format_dt(last_updated),
            updated_at=last_updated,
            sla_status=coalesce(payload.get("slaStatus"), "Unknown"),
            is_in_sla=payload.get("isInSla"),
            date_entered=format_dt(opened_at),
            opened_at=opened_at,
            raw=payload,
        )

    @property
    def sla_badge(self) -> str:
        if self.is_sla_breached():
            return "BREACH"
        if self.is_in_sla is True:
            return "OK"
        if self.sla_status:
            return self.sla_status
        return "-"

    def is_sla_breached(self) -> bool:
        if self.is_in_sla is False:
            return True
        lowered = self.sla_status.lower()
        return "breach" in lowered or "past" in lowered

    @property
    def priority_badge(self) -> str:
        text = self.priority_name.strip()
        if not text:
            return "-"
        lowered = text.lower()
        if lowered.startswith("priority "):
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return f"P{parts[1]}"
        return text[:10]

    @property
    def age_badge(self) -> str:
        opened = parse_dt(self.opened_at)
        if opened is None:
            return "-"
        now = datetime.now(opened.tzinfo or timezone.utc)
        delta = now - opened
        if delta.days >= 1:
            return f"{delta.days}d"
        hours = delta.seconds // 3600
        if hours >= 1:
            return f"{hours}h"
        minutes = delta.seconds // 60
        return f"{minutes}m"

    def matches(self, filters: TicketFilters) -> bool:
        company_match = filters.company_query.lower() in self.company_name.lower()
        tech_match = filters.tech_query.lower() in self.owner_name.lower()
        status_match = filters.status_query.lower() in self.status_name.lower()
        sla_match = (not filters.sla_breached_only) or self.is_sla_breached()
        return company_match and tech_match and status_match and sla_match


@dataclass(slots=True)
class TicketDetail:
    ticket: TicketSummary
    contact_name: str
    contact_email: str
    initial_description: str
    date_resolved: str
    board_status: str
    notes: list[ServiceNote]
    time_entries: list[TimeEntry]

    @classmethod
    def from_api(
        cls,
        payload: dict[str, Any],
        notes: list[ServiceNote],
        time_entries: list[TimeEntry],
    ) -> "TicketDetail":
        summary = TicketSummary.from_api(payload)
        return cls(
            ticket=summary,
            contact_name=coalesce(payload.get("contactName"), ref_name(payload.get("contact"))),
            contact_email=coalesce(payload.get("contactEmailAddress")),
            initial_description=coalesce(
                payload.get("initialDescription"),
                payload.get("initialInternalAnalysis"),
                payload.get("summary"),
            ),
            date_resolved=format_dt(payload.get("dateResolved")),
            board_status=coalesce(ref_name(payload.get("status")), payload.get("slaStatus")),
            notes=notes,
            time_entries=time_entries,
        )
