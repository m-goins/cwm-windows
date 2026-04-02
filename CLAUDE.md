# cwm

## Purpose
Keyboard-first TUI for ConnectWise Manage ticket triage, built for MSP service desk workflows.

## Architecture
Three-pane Textual app: board list (left), ticket grid (center), ticket detail (right). Async API client with pagination and cancellable task management. State held in a single `AppState` dataclass. Modal forms for mutations (notes, time, assign, status).

Data flow: `config -> ConnectWiseAPI -> AppState -> widgets`. Board selection triggers ticket reload; ticket highlight triggers detail load. Both use `asyncio.Lock` to prevent races. Background tasks handle mutations without blocking the UI.

## Tech Stack
- Python 3.10+
- Textual (TUI framework)
- httpx (async HTTP client)
- pytest + pytest-asyncio (testing)

## Filesystem Structure
```
cwm/
├── __init__.py
├── __main__.py          # CLI entrypoint, arg parsing
├── config.py            # Multi-source config resolution (env, JSON, legacy vars)
├── logging_setup.py     # Rotating file logger
├── models.py            # Dataclasses: Board, Ticket, Notes, TimeEntry, Filters
├── state.py             # AppState dataclass
├── api.py               # Async ConnectWise API client with pagination
├── app.py               # Main Textual app, keybindings, event handlers
├── app.tcss             # Textual stylesheet
├── widgets.py           # BoardTable, TicketTable, TicketDetailView, StatusBar
├── modals.py            # Filter, Note, Time, Assign, Status modal forms
tests/
├── test_models.py       # Model parsing, filtering, formatting
├── test_config.py       # Config resolution, validation
```

## Decision Log

### 2026-04-01: Initial implementation
**Context:** Need a fast keyboard-driven CW Manage interface for triage
**Decision:** Textual + httpx, vim-style keybindings, three-pane layout
**Consequences:** No web UI, terminal-only. Textual handles async natively.
**Revisit When:** Need mobile or multi-user access

### 2026-04-02: Parallel detail fetching
**Context:** `load_ticket_detail` was fetching ticket, notes, and time entries serially
**Decision:** Switch to `asyncio.gather` for all three calls
**Consequences:** ~3x faster detail loads, no behavior change since calls are independent
**Revisit When:** Never, this is strictly better

### 2026-04-02: v3 feature set
**Context:** Daily triage workflow blockers identified during repo review
**Decision:** Added 9 features: my-tickets toggle, cross-board search, auto-refresh, ticket creation, clipboard, bulk operations, contact column, retry with backoff, configurable refresh interval
**Consequences:** app.py grew past 500 lines (now ~530). Candidate for extraction into separate modules (actions, mutations) in a future refactor.
**Revisit When:** app.py exceeds 700 lines or new feature categories emerge

## Current State
- Working: board browsing, ticket listing, detail view, notes, time entry, assignment, status changes
- Working: vim keybindings, SLA filtering, multi-column sorting, ticket window sizing
- Working: my-tickets filter, cross-board search, auto-refresh, ticket creation, clipboard, bulk select/assign/status
- Working: retry with exponential backoff on 429/5xx/transient errors
- 95 tests passing (models + config layers)
- No tests for API client or UI layer yet

## Environment
- Config via `CWM_*` env vars, JSON file (`--config`), or legacy `CW_*`/`CONNECTWISE_*` vars
- Required: `CWM_BASE_URL`, `CWM_COMPANY_ID`, `CWM_PUBLIC_KEY`, `CWM_PRIVATE_KEY`, `CWM_CLIENT_ID`
- Optional: `CWM_MEMBER_IDENTIFIER`, `CWM_VERIFY_SSL`, `CWM_LOG_PATH`, `CWM_LOG_LEVEL`, `CWM_REFRESH_INTERVAL`
- Default log: `~/.local/state/cwm/cwm.log`
- Startup script: `start_cwm.sh` (creates venv, installs deps, launches)
- Clipboard requires `xclip`, `xsel`, or `wl-copy` installed on the system

## Claude Instructions
- This is an MSP operations tool. Prioritize keyboard efficiency and triage speed.
- Config resolution order matters: env vars override JSON file values. Don't break this.
- The `from_api` classmethod pattern is used consistently across all models. Follow it.
- Keep widget code thin. Display logic belongs in model properties (`sla_badge`, `priority_badge`, etc).
- All API calls must go through `ConnectWiseAPI._request` for consistent error handling, logging, and retry.
- Bulk operations (assign, status) use `_get_actionable_ticket_ids()` which returns bulk selection if any, otherwise the cursor ticket. Follow this pattern for new mutations.
- Global search sets `state.global_search_active` and bypasses board filtering. Selecting a board or pressing `c`/`q` exits search mode.
