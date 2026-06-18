import re

CI_PATTERN = re.compile(r"^[VEJPG]?-?\d{6,9}$")
PHONE_PATTERN = re.compile(r"^(\+58|0)?(412|414|416|424|426)\d{7}$")
RIF_PATTERN = re.compile(r"^[VEJPG]?-?\d{8}-?\d$")


def validate_ci(v: str) -> str:
    cleaned = v.strip().upper()
    if not CI_PATTERN.match(cleaned):
        raise ValueError("CI inválida. Formato esperado: V/E-12345678 o solo números")
    normalized = cleaned.replace("-", "")
    if not normalized[0].isalpha():
        normalized = "V-" + normalized
    else:
        normalized = normalized[0] + "-" + normalized[1:]
    return normalized


def validate_phone(v: str) -> str:
    cleaned = re.sub(r"[\s\-\(\)]+", "", v.strip())
    if not PHONE_PATTERN.match(cleaned):
        raise ValueError(
            "Teléfono inválido. Debe ser un número venezolano (0412, 0414, 0416, 0424, 0426)"
        )
    if cleaned.startswith("0"):
        cleaned = "+58" + cleaned[1:]
    elif not cleaned.startswith("+"):
        cleaned = "+58" + cleaned
    return cleaned


def validate_rif(v: str) -> str:
    cleaned = v.strip().upper()
    if not RIF_PATTERN.match(cleaned):
        raise ValueError("RIF inválido. Formato esperado: J-12345678-9 o V-12345678-9")
    digits = re.sub(r"[^VEJPG\d]", "", cleaned)
    return f"{digits[0]}-{digits[1:9]}-{digits[9]}"
