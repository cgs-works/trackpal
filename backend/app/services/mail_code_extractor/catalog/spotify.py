"""Spotify mail code extraction patterns."""

from app.services.mail_code_extractor._types import ServiceEntry

SERVICE: ServiceEntry = {
    "service_name": "Spotify",
    "subject_patterns": [
        "Tu código de inicio de sesión de Spotify:",
        "Tu código de inicio de sesión de Spotify es",
        "Your Spotify login code",
    ],
    "extraction_rules": [
        {
            "regex": r"Tu código de inicio de sesión de Spotify:\s*(\d{6})",
            "type": "code",
            "desc": "6-digit code after colon (ES)",
        },
        {
            "regex": r"Tu código de inicio de sesión de Spotify es\s*(\d{6})",
            "type": "code",
            "desc": "6-digit code after 'es' (ES)",
        },
        {
            "regex": r"Ingresa este código.*?(\d{6})",
            "type": "code",
            "desc": "6-digit after enter prompt (ES)",
        },
        {
            "regex": r"(\d{6})\s*Este código es válido",
            "type": "code",
            "desc": "6-digit before valid text (ES)",
        },
        {
            "regex": r"(\d{6})\s*-\s*Your Spotify login code",
            "type": "code",
            "desc": "6-digit before label (EN)",
        },
        {
            "regex": r"Enter this code.*?(\d{6})",
            "type": "code",
            "desc": "6-digit after enter prompt (EN)",
        },
        {
            "regex": r"(\d{6})\s*This code is valid",
            "type": "code",
            "desc": "6-digit before valid text (EN)",
        },
    ],
}
