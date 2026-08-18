"""Unit tests for scripts/sql_guard.py"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)

from sql_guard import (  # noqa: E402
    check_sql,
    looks_like_credential_smuggle,
    reject_credential_args,
)

ALLOW = [
    "SELECT * FROM registrations WHERE id = 5",
    "WITH r AS (SELECT id FROM reg) SELECT * FROM r",
    "SELECT last_update, created_date FROM tds_v5.reg",
    "SELECT updated_by, deleted_flag FROM reg",
    "SELECT * FROM audit WHERE action = 'DELETE'",
    "SELECT * FROM lock l JOIN audit a ON a.id = l.id",
    "SELECT a.audit, b.lock FROM x a, y b",
    "SELECT id, audit FROM reg",
    "SELECT DBMS_LOB.SUBSTR(notes,100,1) FROM reg",
    "select a.id from reg a join slot b on a.id=b.reg_id",
]

DENY = [
    "DELETE FROM registrations",
    "UPDATE reg SET status = 'X'",
    "INSERT INTO reg (id) VALUES (1)",
    "MERGE INTO reg USING dual ON (1=1)",
    "DROP TABLE reg",
    "TRUNCATE TABLE reg",
    "SELECT 1 FROM dual; DELETE FROM reg",
    "SELECT 1 FROM dual; -- x\nDROP TABLE reg",
    "/* SELECT */ UPDATE reg SET a=1",
    "SELECT * FROM reg FOR UPDATE",
    "BEGIN DELETE FROM reg; END;",
    "DECLARE x NUMBER; BEGIN NULL; END;",
    "SELECT 1 FROM dual WHERE 1=1 AND EXECUTE IMMEDIATE 'x' IS NULL",
    "SELECT UTL_HTTP.REQUEST('http://evil') FROM dual",
    "SELECT DBMS_XMLGEN.GETXML('DELETE FROM reg') FROM dual",
    "SELECT q'[anything]' FROM dual",
    "COMMIT",
    "GRANT DBA TO scott",
    "   ",
]

failures = 0
for q in ALLOW:
    got = check_sql(q)
    if got is not None:
        failures += 1
        print("FAIL allow: %r -> %s" % (q, got))
    else:
        print("ok   allow: %s" % q[:60])

for q in DENY:
    got = check_sql(q)
    if got is None:
        failures += 1
        print("FAIL deny:  %r" % q)
    else:
        print("ok   deny:  %s (%s)" % (q[:40], got[:40]))

# credential args
if reject_credential_args({"sql": "SELECT 1 FROM dual"}) is not None:
    failures += 1
    print("FAIL reject_credential_args clean")
else:
    print("ok   reject_credential_args clean")

for bad in ({"username": "scott"}, {"password": "x"}, {"host": "db"}, {"dsn": "x"}):
    if reject_credential_args(bad) is None:
        failures += 1
        print("FAIL reject_credential_args %r" % bad)
    else:
        print("ok   reject_credential_args %r" % bad)

if not looks_like_credential_smuggle("SELECT 1 FROM dual"):
    print("ok   no false credential smuggle")
else:
    failures += 1
    print("FAIL false credential smuggle")

for s in ("scott/tiger@fe4", "CONN -savepwd x", "jdbc:oracle:thin:@//h/s"):
    if looks_like_credential_smuggle(s):
        print("ok   credential smuggle %r" % s)
    else:
        failures += 1
        print("FAIL credential smuggle %r" % s)

print("\n%d failure(s)" % failures)
sys.exit(1 if failures else 0)
