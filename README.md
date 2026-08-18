# FE4 database read-only Cursor plugins

Monorepo for team-shareable Cursor plugins that give agents **pinned, read-only** access to FE4 databases.

| Project | Status | Path |
|---------|--------|------|
| FE4 Oracle Read-Only | Ready | [`fe4-oracle-readonly/`](./fe4-oracle-readonly/) |
| FE4 SQL Server Read-Only | Placeholder | [`fe4-sqlserver-readonly/`](./fe4-sqlserver-readonly/) |

Each plugin is a **separate installable project** (own `install.ps1`, rules, hooks, MCP). They share this repo for convenience only — installing one does not install the other.

## Quick start

**Oracle (working today):**

```powershell
cd fe4-oracle-readonly
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

See [`fe4-oracle-readonly/README.md`](./fe4-oracle-readonly/README.md).

**SQL Server:** not built yet — see [`fe4-sqlserver-readonly/README.md`](./fe4-sqlserver-readonly/README.md).

## Repo layout

```text
fe4-oracle-readonly/       # Oracle plugin (Cursor local plugin + user MCP)
fe4-sqlserver-readonly/    # SQL Server plugin (stub)
.gitignore
README.md                  # this file
```

Do not commit `runtime/`, `secrets.local`, or `.venv/` from either project.
