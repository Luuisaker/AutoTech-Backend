from enum import StrEnum


class PartCondition(StrEnum):
    NEW = "NEW"
    USED = "USED"


class PartCategory(StrEnum):
    ENGINE = "ENGINE"
    ELECTRICAL = "ELECTRICAL"
    BODY = "BODY"
    SUSPENSION = "SUSPENSION"
    BRAKES = "BRAKES"
    TRANSMISSION = "TRANSMISSION"
    EXHAUST = "EXHAUST"
    COOLING = "COOLING"
    INTERIOR = "INTERIOR"
    CONSUMABLE = "CONSUMABLE"
    OTHER = "OTHER"
