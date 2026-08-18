---
name: fe4-oracle-readonly
description: >-
  Query the pinned FE4 Oracle database read-only via the fe4-oracle-readonly MCP.
  Use when the user asks about FE4 data, Oracle tables, schema, or SQL against FE4.
---

# FE4 Oracle read-only

## Setup (human, once)

1. Edit `scripts/config.py`: set `PINNED_USERNAME`, `PINNED_DSN`, and `ALLOWED_SERVICE_NAMES` to the DBA-provided FE4 read-only values.
2. In Cursor: **Plugins → fe4-oracle-readonly → Configure** → set `ORACLE_RO_PASSWORD`.
3. Reload the window. Never put the password in git, rules, or skills.

## Agent workflow

1. Prefer `session_info` if you need to confirm USER / SERVICE_NAME.
2. Use `schema_information` for object lists — do not invent dictionary queries unless needed.
3. Run data questions with `sql_run` and a single `SELECT` or `WITH ... SELECT`.
4. Use bind-style placeholders in SQL text only when the server supports them; otherwise literal filters with `FETCH FIRST n ROWS ONLY`.

## When a guard blocks

- Tell the user the call was blocked and why.
- Do not retry with DML, `sqlcl`, shell clients, or credentials from the codebase.
- Writes are out of scope for this plugin.

## Never

- `INSERT` / `UPDATE` / `DELETE` / `MERGE` / DDL / `FOR UPDATE` / PL/SQL blocks
- Logging in as any user other than the pinned read-only setup user
- Connecting to any host other than FE4
