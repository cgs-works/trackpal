"""Synthetic TrackPal demo mail code extraction patterns."""

from app.services.mail_code_extractor._types import ServiceEntry

SERVICE: ServiceEntry = {
    "service_name": "TrackPal Demo",
    "subject_patterns": [
        "Your TrackPal demo access code",
        "Tu código de acceso de demostración de TrackPal",
    ],
    "extraction_rules": [
        {
            "regex": r"(?is)Your TrackPal demo code is.*?(\d{6})",
            "type": "code",
            "desc": "6-digit TrackPal demo code (EN)",
        },
        {
            "regex": r"(?is)Tu código de demostración de TrackPal es.*?(\d{6})",
            "type": "code",
            "desc": "6-digit TrackPal demo code (ES)",
        },
    ],
}
