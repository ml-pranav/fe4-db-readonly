"""preToolUse: deny credential-shaped args before any tool runs."""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from sql_guard import looks_like_credential_smuggle, reject_credential_args  # noqa: E402

ARG_KEYS = ("tool_input", "toolInput", "arguments", "args", "input", "params", "parameters")


def walk_strings(node, acc):
    if isinstance(node, str):
        acc.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            walk_strings(v, acc)
    elif isinstance(node, list):
        for v in node:
            walk_strings(v, acc)


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.stdout.write(json.dumps({"permission": "allow"}))
        return

    if not isinstance(payload, dict):
        sys.stdout.write(json.dumps({"permission": "allow"}))
        return

    args = None
    for k in ARG_KEYS:
        v = payload.get(k)
        if isinstance(v, dict):
            args = v
            break
    if args is None:
        args = payload

    reason = reject_credential_args(args if isinstance(args, dict) else None)
    if reason:
        sys.stdout.write(json.dumps({
            "permission": "deny",
            "user_message": "FE4 Oracle guard: %s" % reason,
            "agent_message": (
                "BLOCKED: do not pass username/password/host into tools. "
                "The fe4-oracle-readonly plugin uses only the pinned FE4 read-only user."
            ),
        }))
        return

    strings = []
    walk_strings(args, strings)
    for s in strings:
        if looks_like_credential_smuggle(s):
            sys.stdout.write(json.dumps({
                "permission": "deny",
                "user_message": "FE4 Oracle guard blocked a connect-string / savepwd shaped argument.",
                "agent_message": (
                    "BLOCKED: never log in with credentials from the codebase or config files. "
                    "Use only fe4-oracle-readonly sql_run with SELECT/WITH."
                ),
            }))
            return

    sys.stdout.write(json.dumps({"permission": "allow"}))


if __name__ == "__main__":
    main()
