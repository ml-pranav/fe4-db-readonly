"""Pin / session verification tests (no live database required)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)

from session_pin import verify_session_row  # noqa: E402
from sql_guard import reject_credential_args  # noqa: E402

failures = 0


def expect_ok(**kwargs):
    global failures
    try:
        verify_session_row(**kwargs)
        print("ok   verify_session_row")
    except Exception as exc:
        failures += 1
        print("FAIL verify_session_row raised %s" % exc)


def expect_fail(label, **kwargs):
    global failures
    try:
        verify_session_row(**kwargs)
        failures += 1
        print("FAIL %s (expected error)" % label)
    except RuntimeError:
        print("ok   %s" % label)
    except Exception as exc:
        failures += 1
        print("FAIL %s wrong error %s" % (label, exc))


expect_ok(
    user="MCP_READONLY",
    service="",
    instance="OFS1",
    db_name="OFS1",
    pinned_username="MCP_READONLY",
    allowed_sids=frozenset({"OFS1"}),
)

expect_fail(
    "wrong user",
    user="APP_WRITER",
    service="",
    instance="OFS1",
    pinned_username="MCP_READONLY",
    allowed_sids=frozenset({"OFS1"}),
)

expect_fail(
    "wrong sid",
    user="MCP_READONLY",
    service="PROD",
    instance="PROD",
    db_name="PROD",
    pinned_username="MCP_READONLY",
    allowed_sids=frozenset({"OFS1"}),
)

expect_fail(
    "wrong instance when pinned",
    user="MCP_READONLY",
    service="",
    instance="WRONG",
    pinned_username="MCP_READONLY",
    allowed_sids=frozenset({"OFS1"}),
    allowed_instances=frozenset({"FE4INST"}),
)

if reject_credential_args({"host": "otherdb", "sql": "SELECT 1 FROM dual"}) is None:
    failures += 1
    print("FAIL host arg should be rejected")
else:
    print("ok   host arg rejected")

print("\n%d failure(s)" % failures)
sys.exit(1 if failures else 0)
