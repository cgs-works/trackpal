"""Universal+ mail code extraction patterns."""

from app.services.mail_code_extractor._types import ServiceEntry

SERVICE: ServiceEntry = {
    "service_name": "Universal+",
    "subject_patterns": [
        "Universal+ código de activación",
    ],
    "extraction_rules": [
        {
            "regex": r"(?is)c[oó]digo de activaci[oó]n.*?<strong[^>]*>([A-Z0-9]{6})<\/strong>",
            "type": "code",
            "desc": "6-char alphanumeric in <strong> after activation text",
        },
        {
            "regex": r"(?is)<strong[^>]*>([A-Z0-9]{6})<\/strong>",
            "type": "code",
            "desc": "6-char alphanumeric in any <strong>",
        },
        {
            "regex": r"(?m)^\s*([A-Z0-9]{6})\s*$",
            "type": "code",
            "desc": "6-char alphanumeric standalone line",
        },
        {
            "regex": r"(?s)c[oó]digo de activaci[oó]n[\s\S]*?([A-Z0-9]{6})",
            "type": "code",
            "desc": "6-char alphanumeric after activation text",
        },
    ],
}
