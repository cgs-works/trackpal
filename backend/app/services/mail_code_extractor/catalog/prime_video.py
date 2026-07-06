"""Prime Video mail code extraction patterns."""

from app.services.mail_code_extractor._types import ServiceEntry

SERVICE: ServiceEntry = {
    "service_name": "Prime Video",
    "subject_patterns": [
        "amazon.com: Intento de inicio de sesión",
        "amazon.com.mx: Intento de inicio de sesión",
        "amazon.com: Sign-in attempt",
        "amazon.co.uk: Sign-in attempt",
    ],
    "extraction_rules": [
        {
            "regex": r"(?is)tu c[óo]digo de verificación es:.*?(\d{6})",
            "type": "code",
            "desc": "6-digit after verification text (ES)",
        },
        {
            "regex": r"(?is)background-color:\s*#D3D3D3.*?>\s*(\d{6})\s*<",
            "type": "code",
            "desc": "6-digit in coloured background (HTML)",
        },
        {
            "regex": r"(?is)your verification code is:\s*(\d{6})",
            "type": "code",
            "desc": "6-digit after 'your verification code is:' (EN)",
        },
        {
            "regex": r"(?m)^\s*(\d{6})\s*$",
            "type": "code",
            "desc": "6-digit standalone line",
        },
        {
            "regex": r"(?is)c[óo]digo.*?(\d{6})",
            "type": "code",
            "desc": "6-digit after code text (fallback)",
        },
    ],
}
