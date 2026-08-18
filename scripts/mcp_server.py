"""Pinned FE4 read-only MCP server.

Connects only with config.PINNED_USERNAME + config.PINNED_DSN + ORACLE_RO_PASSWORD.
No connect / sqlcl_run / credential tools.
"""

from __future__ import annotations

import csv
import io
import os
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from config import (  # noqa: E402
    ALLOWED_DB_NAMES,
    ALLOWED_INSTANCE_NAMES,
    ALLOWED_SERVICE_NAMES,
    ALLOWED_SIDS,
    PINNED_HOST,
    PINNED_PORT,
    PINNED_SID,
    PINNED_USERNAME,
)
from session_pin import verify_session_row  # noqa: E402
from sql_guard import check_sql, reject_credential_args  # noqa: E402

try:
    import oracledb
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "python-oracledb is required. Run: py -3 -m pip install -r requirements.txt"
    ) from exc

from mcp.server import MCPServer  # noqa: E402

mcp = MCPServer(
    name="fe4-oracle-readonly",
    instructions=(
        "FE4 Oracle read-only. Use sql_run with a single SELECT or WITH statement only. "
        "Never pass username, password, host, or connection name."
    ),
)

_connection: oracledb.Connection | None = None
_session_ok = False


def _password() -> str:
    # Prefer local secrets file so a stale ORACLE_RO_PASSWORD in the MCP process
    # env (from an earlier Plugins Configure attempt) cannot override a fixed file.
    for name in ("secrets.local", ".env"):
        path = os.path.abspath(os.path.join(HERE, "..", name))
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.upper().startswith("ORACLE_RO_PASSWORD="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
                    return line
        except OSError:
            continue

    pwd = os.environ.get("ORACLE_RO_PASSWORD", "").strip()
    if pwd:
        return pwd

    raise RuntimeError(
        "ORACLE_RO_PASSWORD is not set. Create "
        "%USERPROFILE%\\.cursor\\plugins\\local\\fe4-oracle-readonly\\secrets.local "
        "with a single line containing the password (gitignored), or set the "
        "ORACLE_RO_PASSWORD environment variable. Never put the password in config.py."
    )

def _assert_pin_config() -> None:
    if "REPLACE_" in PINNED_HOST or "REPLACE_" in PINNED_USERNAME or "REPLACE_" in PINNED_SID:
        raise RuntimeError(
            "scripts/config.py still has REPLACE_ placeholders. Set PINNED_USERNAME, "
            "PINNED_HOST, PINNED_SID, and ALLOWED_SIDS to the FE4 read-only values."
        )
    if not ALLOWED_SIDS and not ALLOWED_SERVICE_NAMES:
        raise RuntimeError(
            "Set ALLOWED_SIDS (preferred for SID connections) or ALLOWED_SERVICE_NAMES in config.py."
        )


def _pinned_dsn() -> str:
    return oracledb.makedsn(PINNED_HOST, PINNED_PORT, sid=PINNED_SID)


def _close() -> None:
    global _connection, _session_ok
    _session_ok = False
    if _connection is not None:
        try:
            _connection.close()
        except Exception:
            pass
        _connection = None


def _verify_session(conn: oracledb.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              USER,
              SYS_CONTEXT('USERENV', 'SERVICE_NAME'),
              SYS_CONTEXT('USERENV', 'INSTANCE_NAME'),
              SYS_CONTEXT('USERENV', 'DB_NAME')
            FROM dual
            """
        )
        row = cur.fetchone()
    if not row:
        raise RuntimeError("session verification returned no row")

    user, service, instance, db_name = [((v or "").strip()) for v in row]
    try:
        verify_session_row(
            user,
            service,
            instance,
            db_name,
            pinned_username=PINNED_USERNAME,
            allowed_services=ALLOWED_SERVICE_NAMES,
            allowed_sids=ALLOWED_SIDS,
            allowed_instances=ALLOWED_INSTANCE_NAMES,
            allowed_dbs=ALLOWED_DB_NAMES,
        )
    except RuntimeError:
        _close()
        raise


def get_connection() -> oracledb.Connection:
    global _connection, _session_ok
    _assert_pin_config()
    if _connection is not None and _session_ok:
        try:
            _connection.ping()
            return _connection
        except Exception:
            _close()

    conn = oracledb.connect(
        user=PINNED_USERNAME,
        password=_password(),
        dsn=_pinned_dsn(),
    )
    _connection = conn
    try:
        _verify_session(conn)
    except Exception:
        _close()
        raise
    _session_ok = True
    return conn


def _rows_to_csv(columns: list[str], rows: list[tuple]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([("" if v is None else v) for v in row])
    return buf.getvalue()


def looks_like_injection(value: str) -> bool:
    bad = (";", "--", "/*", "*/", "'", '"')
    return any(b in value for b in bad)


@mcp.tool()
def sql_run(sql: str) -> str:
    """Run a single read-only SELECT or WITH statement against the pinned FE4 session.

    Do not pass username, password, host, or connection name. Those are fixed by the plugin.
    """
    reason = check_sql(sql)
    if reason:
        raise ValueError("refused: %s" % reason)

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(sql)
        if cur.description is None:
            raise ValueError("statement produced no result set (writes are not allowed)")
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(5000)
    return _rows_to_csv(columns, rows)


@mcp.tool()
def session_info() -> str:
    """Return the pinned session USER and SERVICE_NAME (no secrets)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              USER AS session_user,
              SYS_CONTEXT('USERENV', 'SERVICE_NAME') AS service_name,
              SYS_CONTEXT('USERENV', 'INSTANCE_NAME') AS instance_name,
              SYS_CONTEXT('USERENV', 'DB_NAME') AS db_name
            FROM dual
            """
        )
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return _rows_to_csv(columns, rows)


@mcp.tool()
def schema_information(level: str = "BRIEF", filter: str = "%") -> str:
    """List objects visible to the pinned read-only user (ALL_OBJECTS)."""
    level_u = (level or "BRIEF").upper()
    if level_u not in {"BRIEF", "OVERVIEW", "DETAILED", "TABLE_DETAILS"}:
        raise ValueError("level must be BRIEF, OVERVIEW, DETAILED, or TABLE_DETAILS")

    like = filter or "%"
    if looks_like_injection(like):
        raise ValueError("invalid filter")

    conn = get_connection()
    if level_u in {"BRIEF", "OVERVIEW"}:
        sql = """
            SELECT object_type, owner, object_name
            FROM all_objects
            WHERE object_type IN ('TABLE', 'VIEW', 'SYNONYM')
              AND object_name LIKE :filt
            ORDER BY object_type, owner, object_name
            FETCH FIRST 200 ROWS ONLY
        """
    else:
        sql = """
            SELECT owner, table_name, column_name, data_type, data_length, nullable
            FROM all_tab_columns
            WHERE table_name LIKE :filt
            ORDER BY owner, table_name, column_id
            FETCH FIRST 500 ROWS ONLY
        """
    with conn.cursor() as cur:
        cur.execute(sql, filt=like.upper())
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return _rows_to_csv(columns, rows)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
