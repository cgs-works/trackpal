SUBJECTS = {
    "NETFLIX_SUBJECTS": {
        "subject": [
            # Travel verify link
            "Tu código de acceso temporal de Netflix",
            "Your Netflix temporary access code",
            "您的 Netflix 临时访问代码",
            # 4-digit sign-in
            "Tu código de inicio de sesión",
            "Netflix: Tu código de inicio de sesión",
            "Netflix：您的登录代码",
            "Netflix: Your sign-in code",
            # 6-digit account change verification
            "Tu código de verificación",
            "Your verification code",
            # 6-digit access attempt
            "Este código vence en 15 minutos",
        ],
        "url": "",
        "regex": [
            # Travel verify link - capture full URL
            r"\[(https:\/\/www\.netflix\.com\/account\/travel\/verify\?nftoken=[^\]]+)\]",
            r'href="(https:\/\/www\.netflix\.com\/account\/travel\/verify\?nftoken=[^"]+)"',
            # 4-digit sign-in
            r"Escribe este código para iniciar sesión\r\n\r\nEscribe este código para iniciar sesión\r\n\r\n(\d{4})\r\n\r\n",
            r"Ingresa este código para iniciar sesión\r\n\r\nIngresa este código para iniciar sesión\r\n\r\n(\d{4})\r\n\r\n",
            r"Enter this code to sign in\r\n\r\nEnter this code to sign in\r\n\r\n(\d{4})\r\n\r\n",
            r"输入此代码登录\r\n\r\n输入此代码登录\r\n\r\n(\d{4})\r\n\r\n",
            r'font-size: 28px; line-height: 32px; letter-spacing: 6px; font-family: NetflixSans-Regular, Helvetica, Roboto, Segoe UI, sans-serif; font-weight: 400; padding-top: 20px; color: #221f1f;">\s*(\d{4})\s*</td>',
            # 6-digit account change verification
            r"Confirma el cambio en tu cuenta con este código:\r\n\r\n(\d{6})\r\n\r\n",
            r"Confirma el cambio de cuenta con este código:\r\n\r\n(\d{6})\r\n\r\n",
            r"Confirm your account change with this code:\r\n\r\n(\d{6})\r\n\r\n",
            # 6-digit access attempt
            r"Código de verificación:\r\n\r\n(\d{6})\r\n\r\n",
        ],
    },
    "DISNEY_SUBJECTS": {
        "subject": [
            "Tu código de acceso único para Disney+",
            "¿Vas a actualizar tu Hogar de Disney+",
            "Your one-time passcode for My Disney",
            "Your one-time passcode for Disney+",
        ],
        "url": "",
        "regex": [
            r'exactly;">(\d{6})\s*<\/td>',
            r'line-height:38px; mso-line-height-rule: exactly;">\s*(\d{6})\s*<\/td>',
        ],
    },
    "HBO_MAX_SUBJECTS": {
        "subject": [
            "Urgente: Tu código de un solo uso de HBO Max",
            "Urgente: Tu código de un solo uso de Max",
        ],
        "url": "",
        "regex": [
            r"(?is)Tu c[oó]digo de un solo uso\s*-*\s*(\d{6})",
            r"(?is)Utiliza este c[oó]digo.*?Tu c[oó]digo de un solo uso.*?(\d{6})",
            r"(?im)^\s*(\d{6})\s*$",
        ],
    },
    "SPOTIFY_SUBJECTS": {
        "subject": [
            "Tu código de inicio de sesión de Spotify:",
            "Tu código de inicio de sesión de Spotify es",
            "رمز تسجيل الدخول على Spotify",
            "Your Spotify login code",
        ],
        "url": "",
        "regex": [
            r"Tu código de inicio de sesión de Spotify:\s*(\d{6})",
            r"Tu código de inicio de sesión de Spotify es\s*(\d{6})",
            r"Ingresa este código.*?(\d{6})",
            r"(\d{6})\s*Este código es válido",
            r"(\d{6})\s*-\s*رمز تسجيل الدخول على Spotify",
            r"اكتب الرمز ده.*?(\d{6})",
            r"(\d{6})\s*الرمز ده صالح",
            r"(\d{6})\s*-\s*Your Spotify login code",
            r"Enter this code.*?(\d{6})",
            r"(\d{6})\s*This code is valid",
        ],
    },
    "UNIVERSAL_SUBJECTS": {
        "subject": [
            "Universal+ código de activación",
        ],
        "url": "",
        "regex": [
            # HTML: code after "código de activación" in <strong>
            r"(?is)c[oó]digo de activaci[oó]n.*?<strong[^>]*>([A-Z0-9]{6})<\/strong>",
            # HTML: any <strong> with 6 alphanumeric chars
            r"(?is)<strong[^>]*>([A-Z0-9]{6})<\/strong>",
            # Plain text: standalone 6-char alphanumeric on its own line
            r"(?m)^\s*([A-Z0-9]{6})\s*$",
            r"(?s)c[oó]digo de activaci[oó]n[\s\S]*?([A-Z0-9]{6})",
        ],
    },
    "PRIME_VIDEO_SUBJECTS": {
        "subject": [
            "amazon.com: Intento de inicio de sesión",
            "amazon.com.mx: Intento de inicio de sesión",
            "amazon.com: Sign-in attempt",
        ],
        "url": "",
        "regex": [
            r"(?is)tu c[óo]digo de verificación es:.*?(\d{6})",
            r"(?is)background-color:\s*#D3D3D3.*?>\s*(\d{6})\s*<",
            r"(?m)^\s*(\d{6})\s*$",
            r"(?is)c[óo]digo.*?(\d{6})",
        ],
    },
}
