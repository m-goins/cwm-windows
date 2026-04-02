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
python -m cwm
```

## Startup script

```bash
cd /home/mgoins/cwm
chmod +x start_cwm.sh
./start_cwm.sh
```

Defaults:

- config: `/home/mgoins/cwaudit/configurations/api_configs/config.json`
- log: `/home/mgoins/cwm/logs/cwm.log`

## Keys

- `j` / `k` move in the focused list
- `h` / `l` move focus between panes
- when the detail pane is focused, `j` / `k` scroll notes and time history
- `o` toggle ticket sort by opened date
- `u` toggle ticket sort by last update
- `i` toggle ticket sort by ticket number
- `x` toggle SLA-breached-only filtering
- `/` open filters
- `c` clear filters
- `[` / `]` shrink or expand the ticket window
- `q` back out of a modal or quit from the main screen

## v2 board-list improvements

- denser ticket grid with opened date, priority, age, SLA, and updated columns
- top-of-screen queue bar showing board, status, company, tech, SLA, sort, ticket window, and selection
- bottom bar split into live status on the left and command hints on the right
- adjustable ticket window for faster triage on large boards
