"""Disney+ mail code extraction patterns."""

from app.services.mail_code_extractor._types import ServiceEntry

SERVICE: ServiceEntry = {
    "service_name": "Disney+",
    "subject_patterns": [
        "Tu código de acceso único para Disney+",
        "¿Vas a actualizar tu Hogar de Disney+",
        "Your one-time passcode for My Disney",
        "Your one-time passcode for Disney+",
    ],
    "extraction_rules": [
        {
            "regex": r'exactly;">(\d{6})\s*<\/td>',
            "type": "code",
            "desc": "6-digit code in <td> with inline style",
        },
        {
            "regex": r'line-height:38px; mso-line-height-rule: exactly;">\s*(\d{6})\s*<\/td>',
            "type": "code",
            "desc": "6-digit code in <td> with mso style",
        },
    ],
}
