"""HBO Max mail code extraction patterns."""

from app.services.mail_code_extractor._types import ServiceEntry

SERVICE: ServiceEntry = {
    "service_name": "HBO Max",
    "subject_patterns": [
        "Urgente: Tu código de un solo uso de HBO Max",
        "Urgente: Tu código de un solo uso de Max",
    ],
    "extraction_rules": [
        {
            "regex": r"(?is)Tu c[oó]digo de un solo uso\s*-*\s*(\d{6})",
            "type": "code",
            "desc": "6-digit one-time code inline",
        },
        {
            "regex": r"(?is)Utiliza este c[oó]digo.*?Tu c[oó]digo de un solo uso.*?(\d{6})",
            "type": "code",
            "desc": "6-digit one-time code after usage text",
        },
        {
            "regex": r"(?im)^\s*(\d{6})\s*$",
            "type": "code",
            "desc": "6-digit code standalone line",
        },
    ],
}
