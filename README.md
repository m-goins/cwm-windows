# cwm

Keyboard-first ConnectWise Manage TUI built with Textual.

## Config

Set these environment variables or pass `--config /path/to/config.json`:

- `CWM_BASE_URL`
- `CWM_COMPANY_ID`
- `CWM_PUBLIC_KEY`
- `CWM_PRIVATE_KEY`
- `CWM_CLIENT_ID`

Optional:

- `CWM_MEMBER_IDENTIFIER`
- `CWM_VERIFY_SSL`
- `CWM_LOG_PATH`
- `CWM_LOG_LEVEL`

Legacy ConnectWise-style variables are also accepted where possible:

- `CW_BASE_URL`, `CW_URL`, `CW_COMPANY_ID`, `CW_PUBLIC_KEY`, `CW_PRIVATE_KEY`, `CW_CLIENT_ID`
- `CONNECTWISE_API_URL`, `CONNECTWISE_PUBLIC_KEY`, `CONNECTWISE_PRIVATE_KEY`
- `CONNECTWISE_AUTH_PREFIX`, `CONNECTWISE_COMPANY_ID`, `CONNECTWISE_CLIENT_ID`

The JSON config loader also accepts `CW_URL` for existing MDC config files.

## Run

```bash
python -m cwm --config ~/.config/cwm/config.json
```

## Startup script

```bash
chmod +x start_cwm.sh
./start_cwm.sh
```

The startup script looks for config in this order:
1. `CWM_CONFIG_PATH` env var (if set)
2. `~/.config/cwm/config.json`

Default log path: `~/.local/state/cwm/cwm.log` (override with `CWM_LOG_PATH`)

## Keys

### Navigation
- `j` / `k` move in the focused list (scroll when detail pane focused)
- `h` / `l` move focus between panes
- `Enter` open ticket detail
- `q` back out of search/modal or quit from the main screen

### Sorting and filtering
- `o` toggle ticket sort by opened date
- `u` toggle ticket sort by last update
- `i` toggle ticket sort by ticket number
- `m` toggle "my tickets" filter (requires `CWM_MEMBER_IDENTIFIER`)
- `x` toggle SLA-breached-only filtering
- `/` open filter modal (status, company, tech)
- `c` clear all filters, selections, and exit search mode
- `[` / `]` shrink or expand the ticket window

### Search and create
- `?` cross-board ticket search
- `w` create a new ticket on the current board

### Mutations
- `n` add a note to the selected ticket
- `t` log time on the selected ticket
- `a` assign ticket (or batch assign if tickets selected with `space`)
- `s` change ticket status (or batch change if tickets selected)

### Other
- `space` toggle bulk selection on current ticket
- `y` copy ticket number to clipboard
- `g` manual refresh

## Optional

- `CWM_REFRESH_INTERVAL` seconds between auto-refresh polls (0 = disabled, default)

## v3 improvements

- **my tickets** (`m`) toggle filters to your tickets via `CWM_MEMBER_IDENTIFIER`
- **cross-board search** (`?`) search ticket summaries across all boards
- **auto-refresh** configurable polling interval with last-refresh timestamp in queue bar
- **ticket creation** (`w`) create tickets with summary, company lookup, and description
- **clipboard** (`y`) copy ticket number to clipboard (xclip/xsel/wl-copy)
- **bulk operations** (`space` to select, then `a`/`s` to batch assign/status change)
- **contact column** in ticket grid showing contact name
- **retry with backoff** on 429/5xx and transient network errors (3 attempts, exponential)
- denser ticket grid with opened date, priority, age, SLA, contact, and updated columns
- top-of-screen queue bar showing board, mine, status, company, tech, SLA, sort, window, bulk count, and last refresh
- bottom bar split into live status on the left and context-sensitive command hints on the right
