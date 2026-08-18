"""SELECT-only SQL classifier. Pure library — no Cursor I/O."""

from __future__ import annotations

import re

FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|TRUNCATE|RENAME|"
    r"GRANT|REVOKE|LOCK|AUDIT|NOAUDIT|EXECUTE|BEGIN|DECLARE|INTO)\b",
    re.I,
)

IDENTIFIER_POSITION = re.compile(r"(?:\b(?:FROM|JOIN)\s+|[.,]\s*)$", re.I)

DANGEROUS_PKG = re.compile(
    r"\b(DBMS_\w+|UTL_\w+|OWA_\w+|HTTPURITYPE|DBURITYPE|XMLTYPE)\b",
    re.I,
)
ALLOWED_PKG = {"DBMS_LOB", "DBMS_RANDOM"}

STARTS_READONLY = re.compile(r"^[\s(]*(SELECT|WITH)\b", re.I)
LOOKS_LIKE_DML = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|BEGIN|DECLARE)\b",
    re.I,
)

FORBIDDEN_ARG_KEYS = frozenset({
    "username", "user", "password", "passwd", "pwd",
    "host", "hostname", "dsn", "connect_string", "connectstring",
    "connection_string", "connectionstring", "connection_name",
    "connectionname", "tns", "service", "service_name", "servicename",
})

CREDENTIAL_SHAPE = re.compile(
    r"(?:\bCONN\b.*-savepwd\b)|(?:\b[\w.$]+/[^\s@]+@[\w.\-:]+)|(?:jdbc:oracle)",
    re.I,
)


def strip_sql_noise(sql: str) -> str:
    """Blank comments, string literals, and quoted identifiers.

    Raises ValueError on Oracle alternative quoting (q'[...]').
    """
    out = []
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if (ch in "qQ") and nxt == "'":
            raise ValueError("alternative quoting (q'...') is not permitted")

        if ch == "'":
            i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(" 'lit' ")
            continue

        if ch == '"':
            i += 1
            while i < n and sql[i] != '"':
                i += 1
            i += 1
            out.append(" ident ")
            continue

        if ch == "-" and nxt == "-":
            while i < n and sql[i] != "\n":
                i += 1
            out.append(" ")
            continue

        if ch == "/" and nxt == "*":
            i += 2
            while i < n - 1 and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2
            out.append(" ")
            continue

        out.append(ch)
        i += 1
    return "".join(out)


def check_sql(sql: str) -> str | None:
    """Return None if the statement is an acceptable read, else a denial reason."""
    if not sql or not sql.strip():
        return "empty statement"

    try:
        code = strip_sql_noise(sql)
    except ValueError as exc:
        return str(exc)

    statements = [s for s in code.split(";") if s.strip()]
    if len(statements) > 1:
        return "multiple statements in one call (%d found)" % len(statements)

    body = statements[0] if statements else ""

    if not STARTS_READONLY.match(body):
        head = body.strip().split()[:1]
        return "statement does not begin with SELECT or WITH (starts with %r)" % (
            head[0] if head else "nothing"
        )

    for hit in FORBIDDEN.finditer(body):
        before = body[:hit.start()]
        after = body[hit.end():]
        if IDENTIFIER_POSITION.search(before) or after.startswith("."):
            continue
        return "contains the forbidden keyword %r" % hit.group(1).upper()

    for pkg in DANGEROUS_PKG.findall(body):
        if pkg.upper() not in ALLOWED_PKG:
            return "calls the restricted package %r" % pkg.upper()

    return None


def reject_credential_args(args: dict | None) -> str | None:
    """Reject tool payloads that try to pass alternate login material."""
    if not isinstance(args, dict):
        return None
    for key in args:
        if str(key).lower().replace("-", "_") in FORBIDDEN_ARG_KEYS:
            return "tool argument %r is not allowed (credentials/host are pinned)" % key
    return None


def looks_like_credential_smuggle(text: str) -> bool:
    if not text:
        return False
    return bool(CREDENTIAL_SHAPE.search(text))
