from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5, NAMESPACE_DNS

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from src.config.settings import settings
from src.modules.users.domain.role import RoleName, ALL_ROLE_NAMES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

# Deterministic UUID mapping for roles (uuid5 based on DNS namespace)
ROLE_NAME_TO_UUID: dict[str, str] = {name: str(uuid5(NAMESPACE_DNS, name)) for name in ALL_ROLE_NAMES}
ROLE_UUID_TO_NAME: dict[str, str] = {v: k for k, v in ROLE_NAME_TO_UUID.items()}


class CurrentUser(BaseModel):
    id: UUID
    roles: list[str]


def create_access_token(user_id: UUID, roles: list[str]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # Store role UUIDs in JWT
    role_uuids = [ROLE_NAME_TO_UUID.get(r, r) for r in roles]
    payload = {"sub": str(user_id), "roles": role_uuids, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> UUID:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return UUID(payload["sub"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        # Map role UUIDs back to names and validate against enum
        raw_roles = payload.get("roles", [])
        role_names: list[str] = []
        for r in raw_roles:
            name = ROLE_UUID_TO_NAME.get(r, r)
            if RoleName.from_string(name) is not None:
                role_names.append(name)
        if not role_names:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has no valid roles",
            )
        return CurrentUser(
            id=UUID(payload["sub"]),
            roles=role_names,
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
