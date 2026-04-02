from __future__ import annotations

from cwm.models import (
    Board,
    BoardStatus,
    Member,
    ServiceNote,
    TicketFilters,
    TicketSummary,
    TimeEntry,
    coalesce,
    format_dt,
    format_hours,
    parse_dt,
    ref_id,
    ref_name,
)


class TestRefId:
    def test_none_input(self) -> None:
        assert ref_id(None) is None

    def test_non_dict(self) -> None:
        assert ref_id("not a dict") is None

    def test_int_id(self) -> None:
        assert ref_id({"id": 42}) == 42

    def test_string_digit_id(self) -> None:
        assert ref_id({"id": "7"}) == 7

    def test_non_numeric_id(self) -> None:
        assert ref_id({"id": "abc"}) is None

    def test_missing_id(self) -> None:
        assert ref_id({}) is None


class TestRefName:
    def test_none_input(self) -> None:
        assert ref_name(None) == ""

    def test_name_key(self) -> None:
        assert ref_name({"name": "Foo"}) == "Foo"

    def test_identifier_key(self) -> None:
        assert ref_name({"identifier": "bar"}) == "bar"

    def test_summary_key(self) -> None:
        assert ref_name({"summary": "baz"}) == "baz"

    def test_priority_order(self) -> None:
        assert ref_name({"name": "first", "identifier": "second"}) == "first"

    def test_empty_dict(self) -> None:
        assert ref_name({}) == ""


class TestCoalesce:
    def test_first_non_empty(self) -> None:
        assert coalesce(None, "", "value") == "value"

    def test_all_none(self) -> None:
        assert coalesce(None, None) == ""

    def test_whitespace_skipped(self) -> None:
        assert coalesce("  ", "real") == "real"

    def test_first_wins(self) -> None:
        assert coalesce("a", "b") == "a"


class TestFormatDt:
    def test_none(self) -> None:
        assert format_dt(None) == "-"

    def test_empty(self) -> None:
        assert format_dt("") == "-"

    def test_iso_format(self) -> None:
        assert format_dt("2025-03-15T14:30:00Z") == "2025-03-15 14:30"

    def test_with_offset(self) -> None:
        assert format_dt("2025-03-15T14:30:00+00:00") == "2025-03-15 14:30"

    def test_invalid_falls_through(self) -> None:
        assert format_dt("not-a-date") == "not-a-date"


class TestFormatHours:
    def test_none(self) -> None:
        assert format_hours(None) == "-"

    def test_int(self) -> None:
        assert format_hours(2) == "2.00h"

    def test_float(self) -> None:
        assert format_hours(1.5) == "1.50h"

    def test_zero(self) -> None:
        assert format_hours(0) == "0.00h"


class TestParseDt:
    def test_none(self) -> None:
        assert parse_dt(None) is None

    def test_empty(self) -> None:
        assert parse_dt("") is None

    def test_valid_iso(self) -> None:
        result = parse_dt("2025-03-15T14:30:00Z")
        assert result is not None
        assert result.year == 2025
        assert result.month == 3
        assert result.hour == 14

    def test_invalid(self) -> None:
        assert parse_dt("garbage") is None


class TestBoardFromApi:
    def test_basic(self) -> None:
        board = Board.from_api({"id": 1, "name": "Service"})
        assert board.id == 1
        assert board.name == "Service"
        assert board.inactive is False

    def test_inactive(self) -> None:
        board = Board.from_api({"id": 2, "name": "Old", "inactive": True})
        assert board.inactive is True

    def test_missing_name(self) -> None:
        board = Board.from_api({"id": 3})
        assert board.name == "Board 3"


class TestBoardStatusFromApi:
    def test_basic(self) -> None:
        status = BoardStatus.from_api(10, {"id": 1, "name": "New"})
        assert status.id == 1
        assert status.board_id == 10
        assert status.name == "New"

    def test_closed(self) -> None:
        status = BoardStatus.from_api(10, {"id": 2, "name": "Closed", "closedStatus": True})
        assert status.closed_status is True


class TestMember:
    def test_from_api(self) -> None:
        member = Member.from_api({"id": 1, "identifier": "jdoe", "name": "John Doe"})
        assert member.id == 1
        assert member.identifier == "jdoe"
        assert member.name == "John Doe"

    def test_label_with_identifier(self) -> None:
        member = Member(id=1, identifier="jdoe", name="John Doe")
        assert member.label() == "John Doe (jdoe)"

    def test_label_same_as_name(self) -> None:
        member = Member(id=1, identifier="John Doe", name="John Doe")
        assert member.label() == "John Doe"


class TestServiceNote:
    def test_from_api(self) -> None:
        note = ServiceNote.from_api({
            "id": 1,
            "text": "Fixed the issue",
            "createdBy": "jdoe",
            "dateCreated": "2025-03-15T10:00:00Z",
            "internalFlag": True,
        })
        assert note.id == 1
        assert note.text == "Fixed the issue"
        assert note.created_by == "jdoe"
        assert note.internal is True


class TestTimeEntry:
    def test_from_api(self) -> None:
        entry = TimeEntry.from_api({
            "id": 5,
            "member": {"name": "Jane"},
            "timeStart": "2025-03-15T09:00:00Z",
            "timeEnd": "2025-03-15T10:00:00Z",
            "actualHours": 1.0,
            "notes": "Worked on config",
            "billableOption": "Billable",
        })
        assert entry.id == 5
        assert entry.member_name == "Jane"
        assert entry.actual_hours == "1.00h"
        assert entry.billable_option == "Billable"


class TestTicketFilters:
    def test_empty_summary(self) -> None:
        filters = TicketFilters()
        assert filters.summary() == "no extra filters"

    def test_with_filters(self) -> None:
        filters = TicketFilters(status_query="New", sla_breached_only=True)
        summary = filters.summary()
        assert "status=New" in summary
        assert "sla=breached" in summary

    def test_my_tickets_summary(self) -> None:
        filters = TicketFilters(my_tickets_only=True, member_identifier="jdoe")
        summary = filters.summary()
        assert "mine=jdoe" in summary

    def test_my_tickets_not_in_summary_when_off(self) -> None:
        filters = TicketFilters(my_tickets_only=False, member_identifier="jdoe")
        assert "mine" not in filters.summary()


class TestTicketSummary:
    PAYLOAD = {
        "id": 100,
        "summary": "Server down",
        "company": {"name": "Acme"},
        "board": {"name": "Service"},
        "status": {"name": "New"},
        "owner": {"name": "Jane"},
        "priority": {"name": "Priority 1 - Critical"},
        "dateEntered": "2025-03-10T08:00:00Z",
        "isInSla": True,
        "slaStatus": "Respond - OK",
        "_info": {"lastUpdated": "2025-03-15T14:00:00Z"},
    }

    def test_from_api(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        assert ticket.id == 100
        assert ticket.summary == "Server down"
        assert ticket.company_name == "Acme"
        assert ticket.board_name == "Service"
        assert ticket.status_name == "New"
        assert ticket.owner_name == "Jane"

    def test_sla_badge_ok(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        assert ticket.sla_badge == "OK"

    def test_sla_badge_breach(self) -> None:
        payload = {**self.PAYLOAD, "isInSla": False, "slaStatus": "Respond - Breach"}
        ticket = TicketSummary.from_api(payload)
        assert ticket.sla_badge == "BREACH"
        assert ticket.is_sla_breached() is True

    def test_priority_badge_p1(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        assert ticket.priority_badge == "P1"

    def test_priority_badge_no_priority(self) -> None:
        payload = {**self.PAYLOAD, "priority": None}
        ticket = TicketSummary.from_api(payload)
        assert ticket.priority_badge == "-"

    def test_age_badge_days(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        badge = ticket.age_badge
        assert badge.endswith("d")

    def test_matches_no_filters(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        assert ticket.matches(TicketFilters()) is True

    def test_matches_company_filter(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        assert ticket.matches(TicketFilters(company_query="Acme")) is True
        assert ticket.matches(TicketFilters(company_query="Other")) is False

    def test_matches_sla_filter(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        assert ticket.matches(TicketFilters(sla_breached_only=True)) is False

    def test_matches_tech_filter(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        assert ticket.matches(TicketFilters(tech_query="Jane")) is True
        assert ticket.matches(TicketFilters(tech_query="Bob")) is False

    def test_contact_name_from_api(self) -> None:
        payload = {**self.PAYLOAD, "contactName": "Alice Smith"}
        ticket = TicketSummary.from_api(payload)
        assert ticket.contact_name == "Alice Smith"

    def test_contact_name_empty_default(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        assert ticket.contact_name == ""

    def test_contact_name_from_ref(self) -> None:
        payload = {**self.PAYLOAD, "contact": {"name": "Bob Jones"}}
        ticket = TicketSummary.from_api(payload)
        assert ticket.contact_name == "Bob Jones"

    def test_matches_my_tickets_filter(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        filters = TicketFilters(my_tickets_only=True, member_identifier="Jane")
        assert ticket.matches(filters) is True

    def test_matches_my_tickets_filter_no_match(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        filters = TicketFilters(my_tickets_only=True, member_identifier="Bob")
        assert ticket.matches(filters) is False

    def test_matches_my_tickets_disabled(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        filters = TicketFilters(my_tickets_only=False, member_identifier="Bob")
        assert ticket.matches(filters) is True

    def test_matches_my_tickets_no_identifier(self) -> None:
        ticket = TicketSummary.from_api(self.PAYLOAD)
        filters = TicketFilters(my_tickets_only=True, member_identifier="")
        assert ticket.matches(filters) is False
