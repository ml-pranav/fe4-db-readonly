"""Pinned FE4 connection identity. Edit only with DBA-approved RO credentials.

Password is NEVER here — it comes from secrets.local or ORACLE_RO_PASSWORD.
"""

# Oracle username for Cursor MCP only. Not an app/dev write account.
PINNED_USERNAME = "cursor"

# FE4 host / port / SID (not service name).
PINNED_HOST = "eag-scasf-ora04.saas.pvt"
PINNED_PORT = 1521
PINNED_SID = "OFS1"

# Session must report one of these via INSTANCE_NAME or DB_NAME (SID-style pin).
# Matched case-insensitively.
ALLOWED_SIDS = frozenset({
    "OFS1",
})

# Optional: also allow these SERVICE_NAME values (leave empty when connecting by SID).
ALLOWED_SERVICE_NAMES = frozenset()

# Optional extra checks (leave empty to skip). Matched case-insensitively.
ALLOWED_INSTANCE_NAMES = frozenset()
ALLOWED_DB_NAMES = frozenset()

MCP_SERVER_ID = "fe4-oracle-readonly"

# Other Oracle MCP server ids that must never be used while this plugin is installed.
BLOCKED_ORACLE_SERVERS = frozenset({
    "oracle-sqlcl",
    "sqlcl",
    "oracle",
    "oracle-db",
    "user-oracle-sqlcl",
})
