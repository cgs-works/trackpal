import psycopg2  # Añadido psycopg2
from email.header import decode_header
import imaplib
import email
import re
import logging
import threading
import time
import asyncio  # Bucle asíncrono para polling IMAP
import os
from flask import Flask, jsonify  # Importar Flask y jsonify

# import mysql.connector # Eliminado mysql.connector
from datetime import datetime, timedelta
from app.subjects import SUBJECTS

import urllib3
import certifi
from urllib3.util.retry import Retry

# Cliente HTTP para solicitudes salientes (con SSL y reintentos)
http = urllib3.PoolManager(
    cert_reqs="CERT_REQUIRED",
    ca_certs=certifi.where(),
    retries=Retry(
        total=2, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504]
    ),
    timeout=urllib3.Timeout(connect=5, read=10),
)

IMAP_SERVER = os.environ["IMAP_SERVER"]
IMAP_PORT = int(os.environ["IMAP_PORT"])
EMAIL_ACCOUNT = os.environ["EMAIL_ACCOUNT"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

# Intervalo de polling (segundos) para reescanear correos
POLL_INTERVAL_SECONDS = int(os.environ.get("IMAP_POLL_INTERVAL_SECONDS", "10"))


def get_bot_mode():
    """
    Determina si el bot es centralizado o dedicado basándose en la variable ADMIN_ID.
    Returns: tuple (modo, admin_id)
        - ('centralizado', None) para bot centralizado
        - ('dedicado', admin_id) para bot dedicado
    """
    admin_id = os.environ.get("ADMIN_ID")
    if admin_id:
        try:
            return ("dedicado", int(admin_id))
        except ValueError:
            logging.error(f"ADMIN_ID inválido: {admin_id}. Debe ser un número entero.")
            return ("centralizado", None)
    else:
        return ("centralizado", None)


async def get_admin_id_for_email(email_address, bot_mode, dedicated_admin_id):
    """
    Obtiene admin_id según el modo del bot.

    Args:
        email_address: Email de destino del código
        bot_mode: 'centralizado' o 'dedicado'
        dedicated_admin_id: admin_id fijo para bot dedicado

    Returns:
        admin_id (int) o None
    """
    if bot_mode == "dedicado":
        # Bot dedicado: usar admin_id fijo de la instancia
        logging.info(
            f"Bot dedicado: Procesando email para admin_id {dedicated_admin_id}"
        )
        return dedicated_admin_id
    else:
        # Bot centralizado: buscar por suscripción
        logging.info(
            f"Bot centralizado: Buscando admin_id por suscripción para {email_address}"
        )
        return await find_admin_id_by_subscription_email(email_address)


def create_db_connection():
    """Crea una conexión a la base de datos PostgreSQL usando DATABASE_URL."""
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if not DATABASE_URL:
        logging.error("DATABASE_URL no está definida en el entorno.")
        print("Error: DATABASE_URL no está definida.")
        return None
    try:
        conexion = psycopg2.connect(DATABASE_URL)
        return conexion
    except psycopg2.Error as e:
        logging.error(f"No se pudo conectar a la base de datos PostgreSQL: {e}")
        print(f"Error al conectar a PostgreSQL: {e}")
        return None


async def check_admin_has_assigned_bot(admin_id: int) -> bool:
    """
    Verifica si un administrador tiene un bot asignado específicamente.

    NOTA: Esta función solo se usa en modo BOT CENTRALIZADO para evitar
    procesar emails de admins que tienen su propio bot dedicado.

    Args:
        admin_id: ID del administrador a verificar

    Returns:
        True si el admin tiene un bot asignado, False en caso contrario
    """
    conexion = None
    cursor = None
    has_bot = False
    try:
        conexion = create_db_connection()
        if conexion is None:
            return False

        cursor = conexion.cursor()
        # Buscar si existe una instancia de bot asignada a este admin
        query = """
            SELECT COUNT(*)
            FROM bot_instances
            WHERE admin_id = %s AND status IN ('running', 'stopped', 'pending_deployment');
        """
        cursor.execute(query, (admin_id,))
        result = cursor.fetchone()

        has_bot = result[0] > 0 if result else False
        logging.info(
            f"Admin ID {admin_id} {'tiene' if has_bot else 'NO tiene'} bot asignado"
        )

    except psycopg2.Error as error:
        logging.error(f"check_admin_has_assigned_bot - Error de base de datos: {error}")
        has_bot = False
    except Exception as error:
        logging.error(f"check_admin_has_assigned_bot - Error inesperado: {error}")
        has_bot = False
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()
    return has_bot


async def find_admin_id_by_subscription_email(email_address: str) -> int | None:
    """
    Busca el admin_id asociado a una suscripción activa por email.

    NOTA: Esta función solo se usa en modo BOT CENTRALIZADO.
    Para bots dedicados, se usa directamente el ADMIN_ID de variables de entorno.

    Args:
        email_address: Email de la suscripción a buscar

    Returns:
        admin_id (int) si se encuentra una suscripción única activa, None en caso contrario
    """
    conexion = None
    cursor = None
    admin_id = None
    try:
        conexion = create_db_connection()
        if conexion is None:
            return None

        cursor = conexion.cursor()
        # Consulta para encontrar un único admin_id para un email activo
        # Usamos DISTINCT para manejar el caso de múltiples suscripciones activas
        # para el mismo email bajo el MISMO admin. Si hay diferentes admins,
        # count > 1 y devolveremos None por ambigüedad.
        query = """
            SELECT DISTINCT admin_id
            FROM subscriptions
            WHERE LOWER(email) = LOWER(%s) AND status = 'Activa';
        """
        cursor.execute(query, (email_address,))
        results = cursor.fetchall()

        if len(results) == 1:
            admin_id = results[0][0]  # Extrae el admin_id de la tupla
            logging.info(f"Admin ID {admin_id} encontrado para email {email_address}")

            # Si es bot centralizado, verificar que el admin NO tenga bot asignado
            current_admin_id = os.environ.get("ADMIN_ID")
            if not current_admin_id:  # Bot centralizado
                has_assigned_bot = await check_admin_has_assigned_bot(admin_id)
                if has_assigned_bot:
                    logging.info(
                        f"Admin ID {admin_id} tiene bot asignado, el bot centralizado no procesará este email"
                    )
                    admin_id = None
                else:
                    logging.info(
                        f"Admin ID {admin_id} NO tiene bot asignado, el bot centralizado procesará este email"
                    )

        elif len(results) > 1:
            logging.warning(
                f"Múltiples admin_id encontrados para el email activo {email_address}. No se puede determinar el admin_id único."
            )
            admin_id = None  # Ambigüedad
        else:
            logging.warning(
                f"No se encontró admin_id para el email activo {email_address}."
            )
            admin_id = None  # No encontrado

    except psycopg2.Error as error:
        logging.error(
            f"find_admin_id_by_subscription_email - Error de base de datos: {error}"
        )
        admin_id = None
    except Exception as error:
        logging.error(
            f"find_admin_id_by_subscription_email - Error inesperado: {error}"
        )
        admin_id = None
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()
    return admin_id


def decode_subject(subject):
    decoded_fragments = decode_header(subject)
    decoded_subject = ""
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            if encoding is None:
                decoded_subject += fragment.decode("utf-8")
            else:
                decoded_subject += fragment.decode(encoding)
        else:
            decoded_subject += fragment
    return decoded_subject


def get_imap_connection():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    mail.select("inbox")
    return mail


async def readEmails():  # Marcar como async
    """Lee correos recientes sin depender solo de UNSEEN.

    Estrategia:
    - Buscar correos desde hace N días (ventana corta) usando ALL + SINCE
    - Aplicar filtro de subjects en process_email
    - La deduplicación se hará más adelante en la inserción a DB (por Message-ID/UID)
    """
    # días para la ventana de búsqueda inicial
    dias_ventana = 1
    last_uid: int | None = None  # último UID procesado en esta ejecución
    while True:
        print("Leyendo emails...")
        try:
            mail = get_imap_connection()

            # Calcular fecha SINCE (RFC 3501) – formato D-MMM-YYYY (ej: 20-Nov-2025)
            since_date = (datetime.utcnow() - timedelta(days=dias_ventana)).strftime(
                "%d-%b-%Y"
            )

            # Estrategia de búsqueda:
            # - Primera vez: usar ALL + SINCE para obtener todos los correos recientes (por UID)
            # - Siguientes veces: usar UID > last_uid para no re-iterar sobre los mismos mensajes
            if last_uid is None:
                result, data = mail.uid("search", None, "ALL", "SINCE", since_date)
            else:
                # Usar búsqueda por UID de forma explícita: 'UID' como clave y el rango como argumento
                # Algunos servidores IMAP se comportan mejor si no se envía "UID 123:*" como una sola cadena.
                result, data = mail.uid("search", None, "UID", f"{last_uid + 1}:*")

            if result == "OK":
                if data and data[0] != b"":
                    print(f"Found {len(data[0].split())} emails en rango UID.")

                    for uid in data[0].split():
                        uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)

                        # Convertir UID a entero para poder compararlo con last_uid
                        try:
                            uid_int = int(uid_str)
                        except ValueError:
                            # Si el UID no es numérico, se ignora este mensaje
                            continue

                        # Si ya hemos procesado este UID (o uno menor o igual), lo saltamos
                        if last_uid is not None and uid_int <= last_uid:
                            continue

                        result, fetch_data = mail.uid("fetch", uid_str, "(RFC822)")
                        if result != "OK":
                            continue

                        raw_email = (
                            fetch_data[0][1]
                            if isinstance(fetch_data[0], tuple)
                            else None
                        )
                        if not isinstance(raw_email, (bytes, bytearray)):
                            continue

                        email_message = email.message_from_bytes(raw_email)
                        subject = decode_subject(email_message.get("subject", ""))
                        subject = subject.strip()
                        service_mail = email_message.get("From", "")
                        og_mail = email_message.get("To", "")

                        email_pattern = r"<(.+?)>"
                        match = re.search(email_pattern, og_mail)
                        email_address = match.group(1) if match else og_mail

                        # Determinar modo del bot y obtener admin_id correspondiente
                        bot_mode, dedicated_admin_id = get_bot_mode()
                        admin_id = await get_admin_id_for_email(
                            email_address, bot_mode, dedicated_admin_id
                        )

                        if admin_id is not None:
                            # Procesar email con admin_id obtenido
                            if "Netflix" in service_mail:
                                process_email(
                                    email_message,
                                    email_address,
                                    subject,
                                    "Netflix",
                                    admin_id,
                                )
                            elif "Disney" in service_mail:
                                process_email(
                                    email_message,
                                    email_address,
                                    subject,
                                    "Disney",
                                    admin_id,
                                )
                            elif (
                                "HBO" in service_mail
                                or "hbomax" in service_mail.lower()
                            ):
                                process_email(
                                    email_message,
                                    email_address,
                                    subject,
                                    "HBO Max",
                                    admin_id,
                                )
                            elif (
                                "Spotify" in service_mail
                                or "spotify" in service_mail.lower()
                            ):
                                process_email(
                                    email_message,
                                    email_address,
                                    subject,
                                    "Spotify",
                                    admin_id,
                                )
                            elif "amazon" in service_mail.lower():
                                process_email(
                                    email_message,
                                    email_address,
                                    subject,
                                    "Prime Video",
                                    admin_id,
                                )
                            elif "universalplus" in service_mail.lower():
                                process_email(
                                    email_message,
                                    email_address,
                                    subject,
                                    "Universal",
                                    admin_id,
                                )
                        else:
                            # Solo loguear para bot centralizado (para bot dedicado esto no debería pasar)
                            if bot_mode == "centralizado":
                                logging.warning(
                                    f"Bot centralizado: No se procesará el correo para {email_address} (Subject: {subject}) porque no se pudo determinar un admin_id único."
                                )
                            else:
                                logging.error(
                                    f"Bot dedicado: Error inesperado - no se pudo obtener admin_id para {email_address}"
                                )

                        # Actualizar last_uid con el mayor UID visto (tanto si se procesó como si se ignoró por modo)
                        if last_uid is None or uid_int > last_uid:
                            last_uid = uid_int
                else:
                    print(
                        "No se encontraron emails nuevos en el rango definido (UID o ventana de tiempo)."
                    )

            # Cerrar la conexión y esperar antes de volver a escanear
            mail.logout()
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except Exception as error:
            print(f"An error occurred: {error}")
            logging.error(f"An error occurred: {error}")
            if "User-rate limit exceeded" in str(error):
                print(
                    "Account has been rate limited. Waiting 1 minute before trying again."
                )
                await asyncio.sleep(60)
            else:
                print("Waiting 15 seconds before trying again.")
                await asyncio.sleep(15)


def decode_email_body(raw_body):
    """
    Decodifica el cuerpo del email manejando diferentes encodings.
    Intenta UTF-8 primero, luego otros encodings comunes.
    """
    if isinstance(raw_body, str):
        return raw_body

    if raw_body is None:
        return ""

    # Lista de encodings a probar en orden
    encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252", "ascii"]

    for encoding in encodings:
        try:
            return raw_body.decode(encoding)
        except (UnicodeDecodeError, AttributeError):
            continue

    # Si ningún encoding funciona, usar 'utf-8' con errores ignorados
    try:
        return raw_body.decode("utf-8", errors="ignore")
    except AttributeError:
        return str(raw_body)


def process_email(email_message, og_mail, subject, service_name, admin_id: int):
    """Procesa un email y extrae códigos de verificación.

    Ahora también extrae el Message-ID para usarlo en la deduplicación en DB.

    Esta función funciona tanto para bot centralizado como dedicado,
    ya que recibe el admin_id como parámetro.
    """
    print(
        f"[{og_mail}] Processing email from {service_name}: {subject} for admin_id: {admin_id}"
    )

    # Extraer Message-ID para deduplicación fuerte en DB (si se configura la columna)
    message_id = email_message.get("Message-ID", "")

    # Preferir text/plain y hacer fallback a text/html para evitar body sin asignar
    if email_message.is_multipart():
        text_body = None
        html_body = None
        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition") or "")
            # omitir adjuntos
            if "attachment" in content_disposition.lower():
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            decoded = decode_email_body(payload)
            if content_type == "text/plain" and text_body is None:
                text_body = decoded
            elif content_type == "text/html" and html_body is None:
                html_body = decoded
        body = text_body or html_body or ""
    else:
        body = decode_email_body(email_message.get_payload(decode=True)) or ""

    try:
        for key, value in SUBJECTS.items():
            if any(pattern in subject for pattern in value["subject"]):
                regex = value["regex"]
                process_part(
                    body,
                    og_mail,
                    subject,
                    service_name,
                    regex,
                    value["url"],
                    admin_id,
                    message_id,
                )
                break
        else:
            print("Ignoring email with subject:", subject)
            logging.info(f"Processed email: og_mail: {og_mail}, Subject: {subject}")
    except Exception as error:
        print(f"An error occurred: {error}")
        logging.error(f"An error occurred: {error}")


def process_part(
    body,
    og_mail,
    subject,
    service_name,
    regex,
    url,
    admin_id: int,
    message_id: str | None = None,
):
    """Procesa una parte del correo y, si encuentra un código, lo envía a la BD.

    La deduplicación ya no se hace en memoria con una lista global, sino únicamente
    en la base de datos (Message-ID + combinación de campos).
    """
    cuerpos_a_evaluar = [body]

    if service_name == "Disney":
        cuerpos_a_evaluar = [body.replace(" ", "").replace("\r", "").replace("\n", "")]
    elif service_name == "HBO Max":
        # HBO suele insertar separadores y saltos de línea entre el texto y el código.
        cuerpos_a_evaluar.append(re.sub(r"\s+", " ", body).strip())

    for cuerpo in cuerpos_a_evaluar:
        for regex_pattern in regex:
            code = re.search(regex_pattern, cuerpo)
            if not code:
                continue

            clean_code = code.group(1)
            full_url = url + clean_code

            # Extracción obligatoria para Netflix: solo guardamos si podemos extraer el código
            if (
                service_name == "Netflix"
                and "netflix.com/account/travel/verify" in full_url
            ):
                logging.info(
                    "[Netflix] Extracción obligatoria activada. Intentando obtener código desde verify URL"
                )
                extracted = fetch_netflix_code_from_url(full_url)
                if extracted:
                    print(
                        f"[Netflix] Código extraído desde verify: {extracted} para {og_mail}"
                    )
                    logging.info(
                        f"[Netflix] Guardando código extraído en columna 'url' (admin_id={admin_id})"
                    )
                    sendToPostgreSQL(
                        og_mail, extracted, service_name, admin_id, message_id
                    )
                else:
                    logging.error(
                        "[Netflix] No se pudo extraer el código; omitiendo guardado por política de obligatoriedad"
                    )
                return

            print(
                f"[{service_name}] Added new code for {og_mail} (admin_id: {admin_id})"
            )
            print(f"Code: {clean_code}")
            sendToPostgreSQL(
                og_mail, full_url, service_name, admin_id, message_id
            )  # Comportamiento estándar para otros servicios
            return

    with open("email_body.txt", "w+", encoding="utf-8") as f:
        f.write(body)
    logging.warning(f"No se encontró código para {service_name}. Subject: {subject}")
    print("save email body to email_body.txt")


def sendToPostgreSQL(
    mail: str, url: str, serv: str, admin_id: int, message_id: str | None = None
):
    """Guarda un código en la base de datos PostgreSQL evitando duplicados.

    Estrategia de deduplicación en dos niveles:
    - Si existe columna message_id en la tabla codes y se proporciona, se prioriza
      (admin_id, service, message_id).
    - Si no, se usa el fallback anterior (admin_id, mail, url, service).
    """
    conexion = None  # Inicializar conexion a None
    cursor = None
    try:
        conexion = create_db_connection()
        if conexion is None:
            print("No se pudo establecer conexión con la base de datos.")
            return  # Salir si no hay conexión

        cursor = conexion.cursor()

        mail = mail.lower()
        used = False  # Usar valor booleano para PostgreSQL
        date = datetime.utcnow()

        # Si tenemos message_id, intentamos deduplicar usando esa columna primero
        # (asumiendo que la columna existe en la tabla codes).
        if message_id:
            try:
                check_sql_msg = (
                    "SELECT 1 FROM codes "
                    "WHERE admin_id = %s AND service = %s AND message_id = %s "
                    "LIMIT 1"
                )
                cursor.execute(check_sql_msg, (admin_id, serv, message_id))
                if cursor.fetchone():
                    logging.info(
                        f"Registro duplicado por message_id en codes para admin_id={admin_id}, "
                        f"service={serv}. Omitiendo inserción."
                    )
                    return
            except psycopg2.errors.UndefinedColumn:
                # Si la columna no existe aún (no se ha aplicado la migración),
                # caemos al mecanismo de deduplicación por combinación de campos.
                conexion.rollback()

        # Fallback: deduplicación por combinación (admin_id, mail, url, service)
        check_sql = (
            "SELECT 1 FROM codes "
            "WHERE admin_id = %s AND mail = %s AND url = %s AND service = %s "
            "LIMIT 1"
        )
        cursor.execute(check_sql, (admin_id, mail, url, serv))
        if cursor.fetchone():
            logging.info(
                f"Registro duplicado detectado en codes para admin_id={admin_id}, mail={mail}, service={serv}. Omitiendo inserción."
            )
            return

        # Consulta SQL con placeholders %s para psycopg2
        if message_id:
            sql = (
                "INSERT INTO codes (admin_id, mail, url, date, service, used, message_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            )
            val = (admin_id, mail, url, date, serv, used, message_id)
        else:
            sql = (
                "INSERT INTO codes (admin_id, mail, url, date, service, used) "
                "VALUES (%s, %s, %s, %s, %s, %s)"
            )
            val = (admin_id, mail, url, date, serv, used)

        try:
            cursor.execute(sql, val)
        except psycopg2.errors.UndefinedColumn:
            conexion.rollback()
            sql = (
                "INSERT INTO codes (admin_id, mail, url, date, service, used) "
                "VALUES (%s, %s, %s, %s, %s, %s)"
            )
            val = (admin_id, mail, url, date, serv, used)
            cursor.execute(sql, val)

        conexion.commit()

        print(f"Añadido nuevo registro a PostgreSQL para admin_id: {admin_id}")

    except psycopg2.Error as error:
        print(f"sendToPostgreSQL - Error de base de datos: {error}")
        logging.error(f"sendToPostgreSQL - Error de base de datos: {error}")
        if conexion:
            conexion.rollback()  # Revertir cambios en caso de error
    except Exception as error:
        print(f"sendToPostgreSQL - Ocurrió un error inesperado: {error}")
        logging.error(f"sendToPostgreSQL - Ocurrió un error inesperado: {error}")
    finally:
        if cursor:
            cursor.close()  # Asegurarse de cerrar el cursor
        if conexion:
            conexion.close()  # Asegurarse de cerrar la conexión


def fetch_netflix_code_from_url(full_url: str) -> str | None:
    """
    Abre el enlace de verificación de Netflix y extrae un código (idealmente 6 dígitos, aceptamos 4–6).
    - Evita placeholders (0000/000000 o repeticiones).
    - Prioriza coincidencias cerca de palabras clave (código/code/pin/otp/acceso/temporal).
    - Fallback: intenta leer JSON embebido.
    - Si no hay resultado válido, guarda HTML para diagnóstico.
    """
    DESKTOP_CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    try:
        logging.info(
            f"[Netflix] Solicitando verify URL con UA Desktop Chrome: {full_url}"
        )
        resp = http.request(
            "GET",
            full_url,
            headers={"User-Agent": DESKTOP_CHROME_UA},
            redirect=True,
        )
        logging.info(
            f"[Netflix] HTTP {resp.status} recibido; Content-Type: {resp.headers.get('Content-Type')}"
        )
        if resp.status not in (200, 301, 302):
            logging.warning(
                f"Respuesta HTTP inesperada {resp.status} al abrir {full_url}"
            )
            return None
        html = resp.data.decode("utf-8", errors="ignore")
        logging.debug(f"[Netflix] HTML recibido, longitud={len(html)} bytes")

        def looks_like_placeholder(code: str) -> bool:
            # Placeholders comunes o secuencias triviales
            if len(set(code)) == 1:  # 0000, 111111, etc.
                return True
            if code in {
                "0000",
                "000000",
                "1234",
                "123456",
                "1111",
                "2222",
                "3333",
                "4444",
                "5555",
                "6666",
                "7777",
                "8888",
                "9999",
            }:
                return True
            return False

        def yield_digit_windows(digits_only: str):
            # Prioriza ventanas de 6, luego 5, luego 4
            for L in (6, 5, 4):
                if len(digits_only) >= L:
                    for i in range(0, len(digits_only) - L + 1):
                        yield digits_only[i : i + L]

        candidates: list[tuple[int, str]] = []  # (score, code)
        keywords = (
            "código",
            "codigo",
            "code",
            "pin",
            "otp",
            "acceso",
            "access",
            "temporal",
            "iniciar",
            "ingresa",
            "introduce",
            "copiar",
            "copy",
        )

        # A0) Selector exacto travel-verification-otp + challenge-code
        for m in re.finditer(
            r'(?is)<div[^>]*data-uia="travel-verification-otp"[^>]*class="[^"]*challenge-code[^"]*"[^>]*>(.*?)</div>',
            html,
        ):
            inner = re.sub(r"<[^>]+>", " ", m.group(1))
            digits_only = re.sub(r"\D+", "", inner)
            for d in yield_digit_windows(digits_only):
                if 4 <= len(d) <= 6 and not looks_like_placeholder(d):
                    candidates.append((10 if len(d) == 6 else 9, d))

        # A1) Si el inner está vacío, intentar extraer dígitos desde atributos del tag de apertura
        for m in re.finditer(
            r'(?is)(<div[^>]*data-uia="travel-verification-otp"[^>]*class="[^"]*challenge-code[^"]*"[^>]*>)',
            html,
        ):
            tag = m.group(1)
            for attr_digits in re.findall(
                r'aria-label="(\d{4,6})"|data-[a-zA-Z0-9_-]+="[^"]*(\d{4,6})[^"]*"', tag
            ):
                dflat = next((x for x in attr_digits if x), None)
                if dflat and not looks_like_placeholder(dflat):
                    candidates.append((8 if len(dflat) == 6 else 7, dflat))

        # A2) data-uia genérico (code|otp|pin)
        for m in re.finditer(
            r'(?is)<[^>]+data-uia="[^"]*(?:code|otp|pin)[^"]*"[^>]*>(.*?)</[^>]+>', html
        ):
            inner = re.sub(r"<[^>]+>", " ", m.group(1))
            digits_only = re.sub(r"\D+", "", inner)
            for d in yield_digit_windows(digits_only):
                if 4 <= len(d) <= 6 and not looks_like_placeholder(d):
                    candidates.append((5 + (3 if len(d) == 6 else 0), d))

        # B) class con hints (challenge-code, code, otp, pin)
        for m in re.finditer(
            r'(?is)<(span|div)[^>]+class="[^"]*(?:challenge-code|code|otp|pin)[^"]*"[^>]*>(.*?)</\1>',
            html,
        ):
            inner = re.sub(r"<[^>]+>", " ", m.group(2))
            digits_only = re.sub(r"\D+", "", inner)
            for d in yield_digit_windows(digits_only):
                if 4 <= len(d) <= 6 and not looks_like_placeholder(d):
                    candidates.append((4 + (3 if len(d) == 6 else 0), d))

        if candidates:
            # Elegir el candidato con mayor score; en empate, priorizar el primero (orden de aparición)
            candidates.sort(key=lambda x: x[0], reverse=True)
            best = candidates[0][1]
            logging.info(f"[Netflix] Código elegido tras heurística: {best}")
            return best

        # E) Búsqueda en JSON embebido (React context u otros)
        json_blocks = re.findall(r"(?is)<script[^>]*>\s*(\{.*?\})\s*</script>", html)
        for block in json_blocks:
            for d in re.findall(r'"(?:otp|code|pin)[^"]*"\s*:\s*"?(\d{4,8})"?', block):
                if 4 <= len(d) <= 6 and not looks_like_placeholder(d):
                    logging.info(f"[Netflix] Código detectado en JSON embebido: {d}")
                    return d

        # Guardar HTML para inspección si no hallamos código válido
        try:
            with open("netflix_verify_response.html", "w+", encoding="utf-8") as f:
                f.write(html)
            logging.warning(
                "[Netflix] No se pudo extraer un código válido; se guardó netflix_verify_response.html"
            )
        except Exception as fe:
            logging.error(f"[Netflix] Falló guardado de HTML de diagnóstico: {fe}")
        return None
    except Exception as e:
        logging.error(f"fetch_netflix_code_from_url - Error: {e}")
        return None


# --- Health Check Server ---
def run_health_check_server(port=3000):
    """Ejecuta un servidor Flask simple para health checks."""
    app = Flask(__name__)
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)  # Deshabilitar logs de Flask/Werkzeug

    @app.route("/health")
    def health_check():
        admin_id = os.environ.get("ADMIN_ID")
        return jsonify(
            {
                "status": "ok",
                "admin_id": admin_id if admin_id else "centralizado",
                "instance": os.environ.get("INSTANCE_NAME"),
                "mode": "centralizado" if not admin_id else "individual",
            }
        )

    print(f"🏥 Health check server running on port {port}")
    try:
        # Deshabilitar reloader y debug en producción/entorno real
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        logging.error(f"Health check server failed: {e}")
        print(f"Health check server failed: {e}")


def main():
    # Detectar y mostrar el modo del bot
    bot_mode, dedicated_admin_id = get_bot_mode()
    if bot_mode == "dedicado":
        print(f"🤖 Bot IMAP Dedicado iniciado para Admin ID: {dedicated_admin_id}")
        logging.info(f"Bot IMAP Dedicado iniciado para Admin ID: {dedicated_admin_id}")
    else:
        print("🤖 Bot IMAP Centralizado iniciado (procesa todos los administradores)")
        logging.info(
            "Bot IMAP Centralizado iniciado (procesa todos los administradores)"
        )

    # Iniciar el servidor de health check en un hilo daemon
    health_thread = threading.Thread(target=run_health_check_server, daemon=True)
    health_thread.start()

    print("Connecting to mail server...")
    # Nota: Ejecutar asyncio.run en un hilo separado puede ser problemático
    # si el hilo principal también usa asyncio. Considerar un enfoque diferente
    # si se integra con un framework async más grande.
    # Por ahora, asumimos que este es el punto de entrada principal.
    try:
        asyncio.run(readEmails())  # Ejecutar la corutina readEmails
    except KeyboardInterrupt:
        print("IMAP bot detenido manualmente.")
    except Exception as e:
        logging.error(f"Error fatal en IMAP bot main loop: {e}")
        print(f"Error fatal en IMAP bot: {e}")
    finally:
        print("IMAP bot finalizado.")
