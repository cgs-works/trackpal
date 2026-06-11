"""Netflix mail code extraction patterns."""

from app.services.mail_code_extractor._types import ServiceEntry

SERVICE: ServiceEntry = {
    "service_name": "Netflix",
    "subject_patterns": [
        "Tu código de acceso temporal de Netflix",
        "Your Netflix temporary access code",
        "您的 Netflix 临时访问代码",
        "Tu código de inicio de sesión",
        "Netflix: Tu código de inicio de sesión",
        "Netflix：您的登录代码",
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
            "regex": r"Escribe este código para iniciar sesión(?:\r?\n\s*){1,3}(?:Escribe este código para iniciar sesión(?:\r?\n\s*){1,3})?(\d{4})",
            "type": "code",
            "desc": "4-digit sign-in (ES)",
        },
        {
            "regex": r"Ingresa este código para iniciar sesión(?:\r?\n\s*){1,3}(?:Ingresa este código para iniciar sesión(?:\r?\n\s*){1,3})?(\d{4})",
            "type": "code",
            "desc": "4-digit sign-in (ES alt)",
        },
        {
            "regex": r"Enter this code to sign in(?:\r?\n\s*){1,3}(?:Enter this code to sign in(?:\r?\n\s*){1,3})?(\d{4})",
            "type": "code",
            "desc": "4-digit sign-in (EN)",
        },
        {
            "regex": r"输入此代码登录(?:\r?\n\s*){1,3}(?:输入此代码登录(?:\r?\n\s*){1,3})?(\d{4})",
            "type": "code",
            "desc": "4-digit sign-in (ZH)",
        },
        {
            "regex": r'font-size: 28px; line-height: 32px; letter-spacing: 6px; font-family: NetflixSans-Regular, Helvetica, Roboto, Segoe UI, sans-serif; font-weight: 400; padding-top: 20px; color: #221f1f;">\s*(\d{4})\s*</td>',
            "type": "code",
            "desc": "4-digit sign-in (inline style HTML)",
        },
        {
            "regex": r"Confirma el cambio en tu cuenta con este código:(?:\r?\n\s*)+(\d{6})",
            "type": "code",
            "desc": "6-digit account change (ES)",
        },
        {
            "regex": r"Confirma el cambio de cuenta con este código:(?:\r?\n\s*)+(\d{6})",
            "type": "code",
            "desc": "6-digit account change (ES alt)",
        },
        {
            "regex": r"Confirm your account change with this code:(?:\r?\n\s*)+(\d{6})",
            "type": "code",
            "desc": "6-digit account change (EN)",
        },
        {
            "regex": r"Código de verificación:(?:\r?\n\s*)+(\d{6})",
            "type": "code",
            "desc": "6-digit access attempt code",
        },
    ],
}
