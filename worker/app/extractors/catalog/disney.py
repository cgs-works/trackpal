"""Disney+ mail code extraction patterns."""

from app.extractors.types import ServiceEntry

SERVICE: ServiceEntry = {
    "service_name": "Disney+",
    "subject_patterns": [
        "Tu código de acceso único para Disney+",
        "Tu código de acceso único para MyDisney",
        "¿Vas a actualizar tu Hogar de Disney+",
        "Your one-time passcode for My Disney",
        "Your one-time passcode for Disney+",
    ],
    "extraction_rules": [
        {
            "regex": r"<td\b[^>]*>\s*(\d{6})\s*</td>",
            "type": "code",
            "desc": "6-digit code inside any <td>",
        },
        {
            "regex": r"\b(\d{6})\b",
            "type": "code",
            "desc": "Fallback standalone 6-digit code",
        },
    ],
}
