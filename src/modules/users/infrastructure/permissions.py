from fastapi import Depends, HTTPException, status

from src.modules.users.infrastructure.auth import get_current_user, CurrentUser
from src.modules.users.domain.role import RoleName


def require_roles(*roles: RoleName):
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        required = {str(r) for r in roles}
        if not required.intersection(current_user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para realizar esta acción",
            )
        return current_user

    return role_checker


require_admin = require_roles(RoleName.ADMIN, RoleName.SUPERADMIN)
require_superadmin = require_roles(RoleName.SUPERADMIN)
require_workshop_owner = require_roles(RoleName.WORKSHOP_OWNER)
require_client = require_roles(RoleName.CLIENT)
