from enum import Enum


class UserRole(str, Enum):
    CLIENT = "CLIENT"
    WORKSHOP_OWNER = "WORKSHOP_OWNER"
    ADMIN = "ADMIN"
