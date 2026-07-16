from enum import StrEnum


class RoleName(StrEnum):
    CLIENT = "CLIENT"
    WORKSHOP_OWNER = "WORKSHOP_OWNER"
    ADMIN = "ADMIN"
    SUPERADMIN = "SUPERADMIN"

    @classmethod
    def from_string(cls, value: str) -> "RoleName | None":
        """Safely convert a string to RoleName, returning None if invalid."""
        try:
            return cls(value)
        except ValueError:
            return None


ALL_ROLE_NAMES = list(RoleName)
