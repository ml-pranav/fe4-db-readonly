"""Hook integration tests for scripts/mcp_hook.py"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
HOOK = os.path.join(ROOT, "scripts", "mcp_hook.py")
PY = sys.executable

FE4 = {"server_name": "fe4-oracle-readonly", "tool_name": "sql_run"}


def sql(q):
    d = dict(FE4)
    d["tool_input"] = {"sql": q}
    return d


def run(payload):
    proc = subprocess.run(
        [PY, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    try:
        return json.loads(proc.stdout)["permission"]
    except Exception:
        return "PARSE_ERROR:%s|%s" % (proc.stdout[:120], proc.stderr[:120])


CASES = [
    ("plain select", sql("SELECT * FROM registrations WHERE id = 5"), "allow"),
    ("with cte", sql("WITH r AS (SELECT id FROM reg) SELECT * FROM r"), "allow"),
    ("literal DELETE", sql("SELECT * FROM audit WHERE action = 'DELETE'"), "allow"),
    ("bare delete", sql("DELETE FROM registrations"), "deny"),
    ("bare update", sql("UPDATE reg SET status = 'X'"), "deny"),
    ("insert", sql("INSERT INTO reg (id) VALUES (1)"), "deny"),
    ("stacked", sql("SELECT 1 FROM dual; DELETE FROM reg"), "deny"),
    ("for update", sql("SELECT * FROM reg FOR UPDATE"), "deny"),
    ("credential arg", {
        "server_name": "fe4-oracle-readonly",
        "tool_name": "sql_run",
        "tool_input": {"sql": "SELECT 1 FROM dual", "username": "scott"},
    }, "deny"),
    ("password arg", {
        "server_name": "fe4-oracle-readonly",
        "tool_name": "sql_run",
        "tool_input": {"sql": "SELECT 1 FROM dual", "password": "x"},
    }, "deny"),
    ("leftover oracle-sqlcl", {
        "server_name": "oracle-sqlcl",
        "tool_name": "sql_run",
        "tool_input": {"sql": "SELECT 1 FROM dual"},
    }, "deny"),
    ("leftover sqlcl_run", {
        "server_name": "oracle-sqlcl",
        "tool_name": "sqlcl_run",
        "tool_input": {"sqlcl": "help"},
    }, "deny"),
    ("connect tool denied", {
        "server_name": "fe4-oracle-readonly",
        "tool_name": "connect",
        "tool_input": {"connection_name": "anything"},
    }, "deny"),
    ("session_info allow", {
        "server_name": "fe4-oracle-readonly",
        "tool_name": "session_info",
        "tool_input": {},
    }, "allow"),
    ("other mcp passes", {
        "server_name": "plugin-atlassian-atlassian",
        "tool_name": "searchJiraIssuesUsingJql",
        "tool_input": {"jql": "status = Done"},
    }, "allow"),
    ("unattributed dml", {
        "tool_name": "mystery",
        "tool_input": {"q": "DELETE FROM reg"},
    }, "deny"),
    ("savepwd shaped", {
        "server_name": "fe4-oracle-readonly",
        "tool_name": "sql_run",
        "tool_input": {"sql": "SELECT 1 FROM dual", "note": "CONN x -savepwd y"},
    }, "deny"),
]

failures = 0
for label, payload, expected in CASES:
    got = run(payload)
    ok = got == expected
    if not ok:
        failures += 1
    print("%-4s %-28s expected=%-5s got=%s" % (
        "ok" if ok else "FAIL", label, expected, got,
    ))

print("\n%d failure(s)" % failures)
sys.exit(1 if failures else 0)
