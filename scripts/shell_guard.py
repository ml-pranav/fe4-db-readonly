"""beforeShellExecution: block agent from launching Oracle clients outside the plugin MCP."""

from __future__ import annotations

import json
import re
import sys

CLIENTS = re.compile(
    r"(sqlcl(\.cmd|\.exe)?\b|\bsqlplus\b|\bsql\.exe\b|SqlCli\b|\bsql\s+/nolog\b|"
    r"\bsql\s+[\w.$]+/[^\s@]+@|\bimpdp\b|\bexpdp\b|"
    r"oracledb\.connect\b|cx_Oracle\.connect\b|jdbc:oracle)",
    re.I,
)

COMMAND_KEYS = ("command", "cmd", "shell_command", "shellCommand", "input")


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.stdout.write(json.dumps({"permission": "allow"}))
        return

    command = ""
    if isinstance(payload, dict):
        for k in COMMAND_KEYS:
            v = payload.get(k)
            if isinstance(v, str):
                command = v
                break

    hit = CLIENTS.search(command or "")
    if hit:
        sys.stdout.write(json.dumps({
            "permission": "deny",
            "user_message": (
                "Blocked an attempt to reach Oracle from the terminal (%r). Database access "
                "must go through the fe4-oracle-readonly MCP plugin (SELECT only). "
                "You can still run this yourself in your own terminal." % hit.group(1)
            ),
            "agent_message": (
                "BLOCKED by fe4-oracle-readonly shell guard: launching an Oracle client from "
                "the shell bypasses the read-only plugin. Use the fe4-oracle-readonly MCP "
                "instead. Do not obscure the command to get around this."
            ),
        }))
        return

    sys.stdout.write(json.dumps({"permission": "allow"}))


if __name__ == "__main__":
    main()
