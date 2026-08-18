"""Shell guard tests."""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
GUARD = os.path.join(ROOT, "scripts", "shell_guard.py")
PY = sys.executable


def run(command):
    proc = subprocess.run(
        [PY, GUARD],
        input=json.dumps({"command": command}),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return json.loads(proc.stdout)["permission"]


CASES = [
    ("dir", "allow"),
    ("git status", "allow"),
    ("sqlplus scott/tiger@fe4", "deny"),
    ("sqlcl /nolog", "deny"),
    ("C:\\x\\sql.exe user/pass@db", "deny"),
    ("impdp system/x", "deny"),
    ("python -c \"import oracledb; oracledb.connect(user='a')\"", "deny"),
]

failures = 0
for cmd, expected in CASES:
    got = run(cmd)
    ok = got == expected
    if not ok:
        failures += 1
    print("%-4s %-50s expected=%-5s got=%s" % (
        "ok" if ok else "FAIL", cmd[:50], expected, got,
    ))

print("\n%d failure(s)" % failures)
sys.exit(1 if failures else 0)
