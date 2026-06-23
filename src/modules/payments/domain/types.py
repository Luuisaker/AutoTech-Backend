from enum import StrEnum


class PaymentAccountType(StrEnum):
    BANK_TRANSFER = "BANK_TRANSFER"
    MOBILE_PAYMENT = "MOBILE_PAYMENT"
