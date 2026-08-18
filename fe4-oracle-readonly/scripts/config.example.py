"""Pinned FE4 connection identity — example template.

Copy to config.py (install.ps1 does this if config.py is missing).
Password is NEVER here — use secrets.local.
"""

PINNED_USERNAME = "cursor"

PINNED_HOST = "eag-scasf-ora04.saas.pvt"
PINNED_PORT = 1521
PINNED_SID = "OFS1"

ALLOWED_SIDS = frozenset({
    "OFS1",
})

ALLOWED_SERVICE_NAMES = frozenset()
ALLOWED_INSTANCE_NAMES = frozenset()
ALLOWED_DB_NAMES = frozenset()

MCP_SERVER_ID = "fe4-oracle-readonly"

BLOCKED_ORACLE_SERVERS = frozenset({
    "oracle-sqlcl",
    "sqlcl",
    "oracle",
    "oracle-db",
    "user-oracle-sqlcl",
})
