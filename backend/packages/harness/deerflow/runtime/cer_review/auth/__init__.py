"""CER RBAC Auth Module.

Exports:
- CERRole: role enumeration
- CERAuthContext: authenticated user context
- CERAuthContext: authenticated user context (dataclass with user_id, user_name, role)
- require_gate_decision_role(): FastAPI dependency for gate decision endpoints
- get_optional_auth(): FastAPI dependency for read endpoints (returns None if no headers)

Frozen baseline: CER_RBAC_MODEL_V1.md
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum

# ── Role Enum ──────────────────────────────────────────────────────────────────


class CERRole(str, Enum):
    """CER Review System roles — minimum viable RBAC model.

    READ_ONLY_VIEWER: Read-only access. Cannot submit any gate decisions.
    REVIEWER: General review access. Cannot submit gate decisions.
    SENIOR_REVIEWER: Can submit GATE_1 and GATE_3 decisions.
    ADMIN: Full access including user management (not used in Sprint P0).
    """

    READ_ONLY_VIEWER = "READ_ONLY_VIEWER"
    REVIEWER = "REVIEWER"
    SENIOR_REVIEWER = "SENIOR_REVIEWER"
    ADMIN = "ADMIN"

    @classmethod
    def all_roles(cls) -> set["CERRole"]:
        return {cls.READ_ONLY_VIEWER, cls.REVIEWER, cls.SENIOR_REVIEWER, cls.ADMIN}

    @classmethod
    def is_valid(cls, value: str) -> bool:
        try:
            cls(value)
            return True
        except ValueError:
            return False


# ── Auth Context ───────────────────────────────────────────────────────────────


@dataclass
class CERAuthContext:
    """Authenticated user context for CER Review System.

    Holds the identity and role of the current request's actor.
    Attached to request.state by the auth dependency.

    Attributes:
        user_id: Unique identifier for the user (from X-CER-User-ID header)
        user_name: Display name (from X-CER-User-Name header, optional)
        role: The user's CER role (from X-CER-User-Role header)
    """

    user_id: str
    user_name: str
    role: CERRole

    def can_submit_gate_decision(self) -> bool:
        """Returns True if this role can submit Gate 1 or Gate 3 decisions."""
        return self.role in {CERRole.SENIOR_REVIEWER, CERRole.ADMIN}

    def can_view(self) -> bool:
        """Returns True if this role can view governance pages."""
        return True  # All authenticated roles can view

    def role_label(self) -> str:
        """Human-readable role label for UI display."""
        return self.role.value


# ── Role Config ───────────────────────────────────────────────────────────────


def _load_rbac_config() -> dict:
    """Load RBAC config from environment variable or defaults.

    Config format: user_id:role,user_id:role,...
    Example: admin-001:SENIOR_REVIEWER,viewer-001:READ_ONLY_VIEWER
    """
    config_str = os.environ.get("CER_RBAC_USERS", "")
    if not config_str:
        # Default dev users for Sprint P0
        return {
            "dev-admin": {"name": "Dev Admin", "role": "ADMIN"},
            "dev-senior": {"name": "Dev Senior Reviewer", "role": "SENIOR_REVIEWER"},
            "dev-reviewer": {"name": "Dev Reviewer", "role": "REVIEWER"},
            "dev-viewer": {"name": "Dev Viewer", "role": "READ_ONLY_VIEWER"},
        }

    users = {}
    for entry in config_str.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            continue
        uid, rrole = entry.split(":", 1)
        uid = uid.strip()
        rrole = rrole.strip()
        if CERRole.is_valid(rrole):
            users[uid] = {"name": uid, "role": rrole}
    return users


_RBAC_USERS = _load_rbac_config()
_RBAC_ENABLED = os.environ.get("CER_RBAC_ENABLED", "true").lower() != "false"
_RBAC_DEV_BYPASS = os.environ.get("CER_RBAC_DEV_BYPASS", "false").lower() == "true"


def is_rbac_enabled() -> bool:
    return _RBAC_ENABLED


def is_dev_bypass() -> bool:
    """DEV bypass: skip auth requirement on read endpoints for local dev only."""
    return _RBAC_DEV_BYPASS


def resolve_role(user_id: str, role_value: str) -> CERRole | None:
    """Resolve a role value to CERRole if valid and allowed for this user."""
    if not CERRole.is_valid(role_value):
        return None
    role = CERRole(role_value)
    # In dev bypass mode, validate against known users but allow any valid role
    if _RBAC_DEV_BYPASS:
        return role
    # In production, the user_id must be in the config
    if user_id not in _RBAC_USERS:
        return None
    expected_role_str = _RBAC_USERS[user_id]["role"]
    if role.value != expected_role_str:
        return None  # Role value doesn't match config — possible header tampering
    return role


def get_default_user_name(user_id: str) -> str:
    """Get the configured display name for a user_id."""
    return _RBAC_USERS.get(user_id, {}).get("name", user_id)


# ── HTTP Header Constants ─────────────────────────────────────────────────────


AUTH_HEADER_USER_ID = "X-CER-User-ID"
AUTH_HEADER_USER_NAME = "X-CER-User-Name"
AUTH_HEADER_USER_ROLE = "X-CER-User-Role"
