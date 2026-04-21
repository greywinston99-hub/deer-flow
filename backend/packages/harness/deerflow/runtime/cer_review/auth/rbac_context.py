"""CER RBAC Context — FastAPI Dependencies.

Provides FastAPI `Depends`-style dependencies for extracting and validating
CER auth context from HTTP headers.

Frozen baseline: CER_RBAC_MODEL_V1.md
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, Request

from . import (
    AUTH_HEADER_USER_ID,
    AUTH_HEADER_USER_NAME,
    AUTH_HEADER_USER_ROLE,
    CERAuthContext,
    CERRole,
    is_dev_bypass,
    is_rbac_enabled,
    resolve_role,
)

logger = logging.getLogger(__name__)


async def get_cer_auth(request: Request) -> CERAuthContext:
    """FastAPI dependency: extract and validate CER auth context from request headers.

    Reads:
        X-CER-User-ID: required
        X-CER-User-Name: optional (defaults to user_id)
        X-CER-User-Role: required

    Returns:
        CERAuthContext with validated user_id, user_name, role

    Raises:
        HTTPException 401 if headers are missing or invalid
        HTTPException 403 if role value is not recognized
    """
    if not is_rbac_enabled():
        # RBAC disabled — return a default senior reviewer context for backward compat
        return CERAuthContext(
            user_id="rbac-disabled",
            user_name="RBAC Disabled",
            role=CERRole.SENIOR_REVIEWER,
        )

    user_id = request.headers.get(AUTH_HEADER_USER_ID)
    user_name = request.headers.get(AUTH_HEADER_USER_NAME, "")
    role_value = request.headers.get(AUTH_HEADER_USER_ROLE)

    if not user_id:
        logger.warning("CER RBAC: missing X-CER-User-ID header")
        raise HTTPException(
            status_code=401,
            detail="Authentication required: X-CER-User-ID header missing",
        )

    if not role_value:
        logger.warning(f"CER RBAC: missing X-CER-User-Role header for user {user_id}")
        raise HTTPException(
            status_code=401,
            detail="Authentication required: X-CER-User-Role header missing",
        )

    role = resolve_role(user_id, role_value)
    if role is None:
        logger.warning(
            f"CER RBAC: invalid role '{role_value}' for user {user_id}"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Invalid or unauthorized role: {role_value}",
        )

    resolved_name = user_name or user_id

    return CERAuthContext(
        user_id=user_id,
        user_name=resolved_name,
        role=role,
    )


async def get_optional_cer_auth(request: Request) -> Optional[CERAuthContext]:
    """FastAPI dependency: extract CER auth context if headers present, else None.

    Unlike get_cer_auth, this does NOT raise 401 if headers are missing.
    Used for read-only endpoints that should work with or without auth.
    """
    if not is_rbac_enabled():
        return None

    if is_dev_bypass():
        # In dev bypass mode, read endpoints don't require auth
        return None

    user_id = request.headers.get(AUTH_HEADER_USER_ID)
    if not user_id:
        return None

    role_value = request.headers.get(AUTH_HEADER_USER_ROLE)
    if not role_value:
        return None

    role = resolve_role(user_id, role_value)
    if role is None:
        return None

    user_name = request.headers.get(AUTH_HEADER_USER_NAME, "") or user_id
    return CERAuthContext(user_id=user_id, user_name=user_name, role=role)


async def get_cer_auth_with_gate_role(request: Request) -> CERAuthContext:
    """Combined FastAPI dependency: extract CER auth from headers AND validate gate decision role.

    This single dependency replaces the two-step pattern:
        get_cer_auth() + require_gate_decision_role()

    FastAPI 0.128.0 generates incorrect OpenAPI body schema when a route parameter
    uses Depends(intermediate_dep) where the intermediate dep itself has a Depends()
    on another dependency (a "two-step" dependency chain). The workaround is to
    combine extraction and validation into one async dependency function.

    Raises HTTPException 401 if auth headers are missing.
    Raises HTTPException 403 if the user's role cannot submit gate decisions.
    """
    if not is_rbac_enabled():
        return CERAuthContext(
            user_id="rbac-disabled",
            user_name="RBAC Disabled",
            role=CERRole.SENIOR_REVIEWER,
        )

    user_id = request.headers.get(AUTH_HEADER_USER_ID)
    user_name = request.headers.get(AUTH_HEADER_USER_NAME, "")
    role_value = request.headers.get(AUTH_HEADER_USER_ROLE)

    if not user_id:
        logger.warning("CER RBAC: missing X-CER-User-ID header")
        raise HTTPException(
            status_code=401,
            detail="Authentication required: X-CER-User-ID header missing",
        )

    if not role_value:
        logger.warning(f"CER RBAC: missing X-CER-User-Role header for user {user_id}")
        raise HTTPException(
            status_code=401,
            detail="Authentication required: X-CER-User-Role header missing",
        )

    role = resolve_role(user_id, role_value)
    if role is None:
        logger.warning(f"CER RBAC: invalid role '{role_value}' for user {user_id}")
        raise HTTPException(
            status_code=403,
            detail=f"Invalid or unauthorized role: {role_value}",
        )

    ctx = CERAuthContext(
        user_id=user_id,
        user_name=user_name or user_id,
        role=role,
    )

    if not ctx.can_submit_gate_decision():
        logger.warning(
            f"CER RBAC: user {ctx.user_id} with role {ctx.role.value} "
            f"attempted gate decision submission"
        )
        raise HTTPException(
            status_code=403,
            detail=(
                f"Permission denied: {ctx.role.value} cannot submit gate decisions. "
                f"Requires SENIOR_REVIEWER or ADMIN role."
            ),
        )

    return ctx


def require_gate_decision_role(auth: CERAuthContext) -> CERAuthContext:
    """Verify that the authenticated user can submit gate decisions.

    Raises HTTPException 403 if the user's role cannot submit gate decisions.
    Used as a secondary dependency after get_cer_auth.
    """
    if not auth.can_submit_gate_decision():
        logger.warning(
            f"CER RBAC: user {auth.user_id} with role {auth.role.value} "
            f"attempted gate decision submission"
        )
        raise HTTPException(
            status_code=403,
            detail=(
                f"Permission denied: {auth.role.value} cannot submit gate decisions. "
                f"Requires SENIOR_REVIEWER or ADMIN role."
            ),
        )
    return auth
