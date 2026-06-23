from fastapi import Depends, HTTPException, status

from src.modules.users.infrastructure.auth import get_current_user, CurrentUser


def require_roles(*roles: str):
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not set(roles).intersection(current_user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para realizar esta acción",
            )
        return current_user

    return role_checker


require_admin = require_roles("ADMIN")
require_workshop_owner = require_roles("WORKSHOP_OWNER")
require_client = require_roles("CLIENT")
