"""beforeMCPExecution: allow only fe4-oracle-readonly SELECT/WITH; deny other Oracle MCPs."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from config import MCP_SERVER_ID  # noqa: E402
from sql_guard import (  # noqa: E402
    LOOKS_LIKE_DML,
    check_sql,
    looks_like_credential_smuggle,
    reject_credential_args,
)

LOG = os.path.join(HERE, "..", "fe4-oracle-guard.log")

ALLOWED_SERVERS = {MCP_SERVER_ID, "plugin-fe4-oracle-readonly-fe4-oracle-readonly"}

BLOCKED_TOOLS = {
    "run-sqlcl", "run_sqlcl", "runsqlcl", "sqlcl_run", "sqlcl-run",
    "connect", "connections_list", "list-connections", "list_connections",
    "disconnect",
}

READONLY_TOOLS = {"sql_run", "sql-run", "run-sql", "run_sql", "schema_information",
                  "schema-information", "session_info", "session-info"}

SERVER_KEYS = ("server_name", "serverName", "server", "mcp_server", "mcpServer", "serverId")
TOOL_KEYS = ("tool_name", "toolName", "tool", "name", "method")
ARG_KEYS = ("tool_input", "toolInput", "arguments", "args", "input", "params", "parameters")


def log(decision, detail, excerpt=""):
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write("%s\t%s\t%s\t%s\n" % (
                datetime.now().isoformat(), decision, detail,
                (excerpt or "")[:500].replace("\n", " "),
            ))
    except Exception:
        pass


def respond(obj):
    sys.stdout.write(json.dumps(obj))
    sys.exit(0)


def allow(reason=""):
    log("ALLOW", reason)
    respond({"permission": "allow"})


def deny(reason, excerpt=""):
    log("DENY", reason, excerpt)
    respond({
        "permission": "deny",
        "user_message": "FE4 Oracle read-only guard blocked this call: %s" % reason,
        "agent_message": (
            "BLOCKED by fe4-oracle-readonly: %s. Use only the fe4-oracle-readonly MCP with a "
            "single SELECT or WITH statement. Do not retry, reword, switch tools, or log in "
            "with credentials from the codebase. If a write is required, tell the user to "
            "run it themselves." % reason
        ),
    })


def walk_strings(node, acc):
    if isinstance(node, str):
        acc.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            walk_strings(v, acc)
    elif isinstance(node, list):
        for v in node:
            walk_strings(v, acc)


def first_of(payload, keys, want_dict=False):
    for k in keys:
        v = payload.get(k)
        if want_dict and isinstance(v, dict):
            return v
        if not want_dict and isinstance(v, str) and v.strip():
            return v.strip()
    return None


def normalize_server(name: str) -> str:
    return (name or "").strip().lower()


def is_blocked_oracle_server(server: str, tool: str) -> bool:
    s = normalize_server(server)
    t = (tool or "").lower()
    # Never treat this plugin's server as blocked (name contains "oracle").
    if MCP_SERVER_ID in s or MCP_SERVER_ID in t:
        return False
    blocked_tokens = (
        "oracle-sqlcl",
        "user-oracle-sqlcl",
        "oracle-db",
    )
    if any(tok in s for tok in blocked_tokens) or any(tok in t for tok in blocked_tokens):
        return True
    # Exact short names only — do not substring-match bare "oracle".
    if s in {"sqlcl", "oracle"} or t in {"sqlcl", "oracle"}:
        return True
    if s.endswith("/sqlcl") or s.endswith(".sqlcl"):
        return True
    return False


def is_allowed_server(server: str, tool: str) -> bool:
    s = normalize_server(server)
    t = (tool or "").lower()
    if MCP_SERVER_ID in s or MCP_SERVER_ID in t:
        return True
    for allowed in ALLOWED_SERVERS:
        if allowed.lower() == s or allowed.lower() in t:
            return True
    return False


_LAST_RAW = ""


def main():
    global _LAST_RAW
    _LAST_RAW = sys.stdin.read()
    raw = _LAST_RAW

    try:
        payload = json.loads(raw)
    except Exception:
        low = (raw or "").lower()
        # Cursor sometimes feeds a non-JSON envelope to hooks. Do not fail closed
        # merely because our server id appears in that blob.
        if any(tok in low for tok in ("oracle-sqlcl", "user-oracle-sqlcl", "sqlcl_run", "run-sqlcl")):
            deny("non-JSON hook payload referenced a blocked Oracle MCP", raw)
        allow("hook payload was not JSON; leaving alone")

    if not isinstance(payload, dict):
        allow("MCP hook payload was not an object; leaving alone")

    server = first_of(payload, SERVER_KEYS) or ""
    tool = first_of(payload, TOOL_KEYS) or ""
    args = first_of(payload, ARG_KEYS, want_dict=True)
    if args is None:
        args = {}

    strings = []
    walk_strings(args, strings)

    if is_blocked_oracle_server(server, tool):
        deny(
            "blocked Oracle MCP server %r (only %s is permitted)" % (server or tool, MCP_SERVER_ID),
            tool,
        )

    if not is_allowed_server(server, tool):
        for s in strings:
            if LOOKS_LIKE_DML.match(s.strip()) or looks_like_credential_smuggle(s):
                deny(
                    "unattributed call looked like Oracle write/login "
                    "(server=%r tool=%r)" % (server, tool),
                    s,
                )
        allow("out of scope: server=%r tool=%r" % (server, tool))

    tool_l = tool.lower()
    base = tool_l.rsplit("_", 1)[-1] if "_" in tool_l else tool_l
    base = base.rsplit("-", 1)[-1] if "-" in base else base

    if any(b in tool_l for b in BLOCKED_TOOLS) or base in BLOCKED_TOOLS:
        deny("tool %r is disabled on the FE4 read-only plugin" % tool)

    cred = reject_credential_args(args if isinstance(args, dict) else None)
    if cred:
        deny(cred)

    for s in strings:
        if looks_like_credential_smuggle(s):
            deny("argument looks like a connect string or savepwd command", s)

    meta = any(
        name in tool_l
        for name in (
            "session_info", "session-info",
            "schema_information", "schema-information",
        )
    )
    if meta:
        allow("metadata tool %r" % tool)

    sql = None
    if isinstance(args, dict) and isinstance(args.get("sql"), str):
        sql = args["sql"]
    else:
        sql_candidates = [s for s in strings if s.strip()]
        if not sql_candidates:
            deny("FE4 tool %r called with no inspectable SQL" % tool)
        sql = sql_candidates[0]

    reason = check_sql(sql)
    if reason:
        deny(reason, sql)

    allow("select-only: tool=%r" % tool)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        low = (_LAST_RAW or "").lower()
        if any(tok in low for tok in ("oracle-sqlcl", "user-oracle-sqlcl", "sqlcl_run", "run-sqlcl")):
            deny("guard raised an unexpected error (%s)" % exc.__class__.__name__)
        allow("MCP hook hit unexpected error (%s); leaving alone" % (
            exc.__class__.__name__,
        ))
