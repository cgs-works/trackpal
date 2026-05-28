"""Netflix mail code extraction patterns."""

from app.services.mail_code_extractor._types import ServiceEntry

SERVICE: ServiceEntry = {
    "service_name": "Netflix",
    "subject_patterns": [
        "Tu código de acceso temporal de Netflix",
        "Your Netflix temporary access code",
        "Tu código de inicio de sesión",
        "Netflix: Tu código de inicio de sesión",
        "Netflix: Your sign-in code",
        "Tu código de verificación",
        "Your verification code",
        "Este código vence en 15 minutos",
    ],
    "extraction_rules": [
        {
            "regex": r"\[(https:\/\/www\.netflix\.com\/account\/travel\/verify\?nftoken=[^\]]+)\]",
            "type": "url",
            "desc": "Travel verify link (markdown)",
        },
        {
            "regex": r'href="(https:\/\/www\.netflix\.com\/account\/travel\/verify\?nftoken=[^"]+)"',
            "type": "url",
            "desc": "Travel verify link (HTML href)",
        },
        {
            "regex": r"Escribe este código para iniciar sesión\r\n\r\nEscribe este código para iniciar sesión\r\n\r\n(\d{4})\r\n\r\n",
            "type": "code",
            "desc": "4-digit sign-in (ES)",
        },
        {
            "regex": r"Ingresa este código para iniciar sesión\r\n\r\nIngresa este código para iniciar sesión\r\n\r\n(\d{4})\r\n\r\n",
            "type": "code",
            "desc": "4-digit sign-in (ES alt)",
        },
        {
            "regex": r"Enter this code to sign in\r\n\r\nEnter this code to sign in\r\n\r\n(\d{4})\r\n\r\n",
            "type": "code",
            "desc": "4-digit sign-in (EN)",
        },
        {
            "regex": r'font-size: 28px; line-height: 32px; letter-spacing: 6px; font-family: NetflixSans-Regular, Helvetica, Roboto, Segoe UI, sans-serif; font-weight: 400; padding-top: 20px; color: #221f1f;">\s*(\d{4})\s*</td>',
            "type": "code",
            "desc": "4-digit sign-in (inline style HTML)",
        },
        {
            "regex": r"Confirma el cambio en tu cuenta con este código:\r\n\r\n(\d{6})\r\n\r\n",
            "type": "code",
            "desc": "6-digit account change (ES)",
        },
        {
            "regex": r"Confirma el cambio de cuenta con este código:\r\n\r\n(\d{6})\r\n\r\n",
            "type": "code",
            "desc": "6-digit account change (ES alt)",
        },
        {
            "regex": r"Confirm your account change with this code:\r\n\r\n(\d{6})\r\n\r\n",
            "type": "code",
            "desc": "6-digit account change (EN)",
        },
        {
            "regex": r"Código de verificación:\r\n\r\n(\d{6})\r\n\r\n",
            "type": "code",
            "desc": "6-digit access attempt code",
        },
    ],
}
