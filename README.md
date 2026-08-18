# FE4 Oracle Read-Only (Cursor plugin)

Minimal Cursor plugin for **FE4-only**, **read-only** Oracle access.

| Ships in the plugin | Wired by `install.ps1` (Windows) |
|---|---|
| Rules, skills, hooks | MCP server entry in `~/.cursor/mcp.json` |
| SELECT-only Python MCP (`scripts/`) | Absolute path to plugin `runtime\Scripts\python.exe` |

Plugin-hosted MCP spawn is unreliable on Windows Cursor builds, so install registers MCP via user `mcp.json` while still packaging code inside the plugin. Rules/skills/hooks load from the plugin UI.

## What’s in the box

```text
.cursor-plugin/plugin.json   # Cursor plugin manifest
hooks/                       # fail-closed SELECT / shell / credential guards
rules/                       # always-apply FE4 read-only rule
skills/                      # query guidance
scripts/                     # MCP server + guards
  config.py                  # pinned user / host / SID (no password)
  config.example.py
mcp.json                     # empty on purpose (MCP via user mcp.json)
install.ps1                  # one-shot Windows installer
uninstall.ps1                # removes MCP entry + local plugin folder
requirements.txt
secrets.local.example
tests/
```

## Team install (Windows)

1. Clone this repo anywhere.
2. Run:

```powershell
cd path\to\fe4-oracle-readonly
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

3. Edit `%USERPROFILE%\.cursor\plugins\local\fe4-oracle-readonly\secrets.local` (one line: password).
4. Confirm `scripts\config.py` (username / host / SID).
5. Cursor → **Developer: Reload Window**.
6. Check:
   - **Plugins** → Fe4 Oracle Readonly (Local) — Rules + Skills
   - **MCP** → `fe4-oracle-readonly` — Connected (User source)
   - **Hooks** → fe4-oracle-readonly guards

### Prerequisites

- Python 3.11+ (used only to create the plugin-local `runtime` venv)
- Network access to FE4 Oracle
- DBA-issued read-only account

You do **not** need a global `PYTHON` env var for day-to-day use after install.

## Uninstall (Windows)

Run from the clone (preferred) or from the installed plugin folder:

```powershell
cd path\to\fe4-oracle-readonly
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

What it does:

1. Removes only the `fe4-oracle-readonly` entry from `%USERPROFILE%\.cursor\mcp.json` (other MCP servers are kept).
2. Stops any running MCP `python.exe` processes that are using the plugin `runtime` (these keep DLLs locked).
3. Deletes `%USERPROFILE%\.cursor\plugins\local\fe4-oracle-readonly` (rules, skills, hooks, runtime, and `secrets.local`).
4. Leaves the clone / GitHub source alone.

If delete still fails with “Access denied” on a `.pyd` file, fully quit Cursor and run uninstall again.

Then **Developer: Reload Window**.

Preview without changing anything: `.\uninstall.ps1 -WhatIf`

## Security

- Password: `secrets.local` only (gitignored). Never `config.py`.
- Agent cannot pass alternate user/host/password into tools.
- Hooks block INSERT/UPDATE/DELETE and shell `sqlplus`/`sqlcl`.
- DB grants remain the real backstop.

## Verify

```powershell
cd %USERPROFILE%\.cursor\plugins\local\fe4-oracle-readonly
.\runtime\Scripts\python.exe tests\test_sql_guard.py
.\runtime\Scripts\python.exe tests\test_mcp_hook.py
.\runtime\Scripts\python.exe tests\test_connect_pin.py
.\runtime\Scripts\python.exe tests\test_shell_guard.py
```

In chat: ask for `session_info` or `SELECT COUNT(*) FROM GLOBAL_BLACKOUT_DATES`.

## GitHub

Commit this folder as the repo root. Do not commit `runtime/`, `secrets.local`, or `.venv/`.
