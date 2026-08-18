"""Session identity checks for the pinned FE4 read-only connection."""

from __future__ import annotations


def verify_session_row(
    user: str,
    service: str,
    instance: str = "",
    db_name: str = "",
    *,
    pinned_username: str,
    allowed_services: frozenset[str] = frozenset(),
    allowed_sids: frozenset[str] = frozenset(),
    allowed_instances: frozenset[str] = frozenset(),
    allowed_dbs: frozenset[str] = frozenset(),
) -> None:
    """Raise RuntimeError if the session is not the pinned FE4 read-only identity."""
    user = (user or "").strip()
    service = (service or "").strip()
    instance = (instance or "").strip()
    db_name = (db_name or "").strip()

    if user.upper() != pinned_username.upper():
        raise RuntimeError(
            "session user %r does not match pinned FE4 read-only user %r; connection dropped"
            % (user, pinned_username)
        )

    if allowed_services:
        if service.upper() not in {s.upper() for s in allowed_services}:
            raise RuntimeError(
                "service_name %r is not in the FE4 allowlist %s; connection dropped"
                % (service, sorted(allowed_services))
            )

    if allowed_sids:
        allowed = {s.upper() for s in allowed_sids}
        candidates = {service.upper(), instance.upper(), db_name.upper()} - {""}
        if not (candidates & allowed):
            raise RuntimeError(
                "session SID markers %r do not match allowlist %s; connection dropped"
                % (sorted(candidates), sorted(allowed_sids))
            )

    if allowed_instances:
        if instance.upper() not in {s.upper() for s in allowed_instances}:
            raise RuntimeError(
                "instance_name %r is not allowed; connection dropped" % instance
            )

    if allowed_dbs:
        if db_name.upper() not in {s.upper() for s in allowed_dbs}:
            raise RuntimeError("db_name %r is not allowed; connection dropped" % db_name)

    if not allowed_services and not allowed_sids and not allowed_instances and not allowed_dbs:
        raise RuntimeError(
            "no FE4 allowlist configured (set ALLOWED_SIDS or ALLOWED_SERVICE_NAMES)"
        )
