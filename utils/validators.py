"""
Funciones de validación y normalización de datos.
Valida emails, teléfonos, URLs y normaliza formatos.
"""

import re
from urllib.parse import urlparse
import phonenumbers


def validar_email(email: str) -> bool:
    """
    Valida que un string sea un email con formato correcto.
    Filtra emails genéricos de ejemplo y no-reply.

    Args:
        email: Dirección de email a validar.

    Returns:
        True si el email es válido y útil para contacto.
    """
    if not email or not isinstance(email, str):
        return False

    email = email.strip().lower()

    # Patrón básico de email
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(patron, email):
        return False

    # Filtrar emails inútiles
    emails_excluidos = [
        "noreply@", "no-reply@", "mailer-daemon@",
        "postmaster@", "webmaster@", "admin@localhost",
        "example.com", "test.com", "ejemplo.com",
        "sentry.io", "wixpress.com",
    ]
    for excluido in emails_excluidos:
        if excluido in email:
            return False

    # Filtrar extensiones de imagen/archivo mal parseadas como email
    extensiones_falsas = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js"]
    for ext in extensiones_falsas:
        if email.endswith(ext):
            return False

    return True


def normalizar_email(email: str) -> str:
    """Normaliza un email a minúsculas y sin espacios."""
    return email.strip().lower()


def validar_telefono(telefono: str, codigo_pais: str = None) -> bool:
    """
    Valida que un string sea un número de teléfono válido.

    Args:
        telefono: Número de teléfono a validar.
        codigo_pais: Código ISO del país (ej: "ES", "US") para parseo regional.

    Returns:
        True si el número es un teléfono válido.
    """
    if not telefono or not isinstance(telefono, str):
        return False

    try:
        parsed = phonenumbers.parse(telefono, codigo_pais)
        return phonenumbers.is_valid_number(parsed)
    except phonenumbers.NumberParseException:
        return False


def normalizar_telefono(telefono: str, codigo_pais: str = None) -> str | None:
    """
    Normaliza un teléfono al formato internacional E.164.

    Args:
        telefono: Número de teléfono a normalizar.
        codigo_pais: Código ISO del país para parseo regional.

    Returns:
        Teléfono en formato E.164 (ej: "+34612345678") o None si no es válido.
    """
    if not telefono:
        return None

    try:
        parsed = phonenumbers.parse(telefono, codigo_pais)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass

    return None


def validar_url(url: str) -> bool:
    """
    Valida que un string sea una URL con formato correcto.

    Args:
        url: URL a validar.

    Returns:
        True si la URL tiene esquema y dominio válidos.
    """
    if not url or not isinstance(url, str):
        return False

    try:
        resultado = urlparse(url.strip())
        return all([
            resultado.scheme in ("http", "https"),
            resultado.netloc,
            "." in resultado.netloc,
        ])
    except Exception:
        return False


def normalizar_url(url: str) -> str:
    """
    Normaliza una URL: asegura que tenga esquema y elimina trailing slash.

    Args:
        url: URL a normalizar.

    Returns:
        URL normalizada.
    """
    url = url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Eliminar trailing slash (excepto si es solo el dominio)
    if url.endswith("/") and url.count("/") > 3:
        url = url.rstrip("/")

    return url


def extraer_dominio(url: str) -> str | None:
    """
    Extrae el dominio de una URL (sin www).

    Args:
        url: URL de la cual extraer el dominio.

    Returns:
        Dominio limpio (ej: "surfschool.com") o None.
    """
    if not url:
        return None

    try:
        parsed = urlparse(normalizar_url(url))
        dominio = parsed.netloc.lower()
        if dominio.startswith("www."):
            dominio = dominio[4:]
        return dominio
    except Exception:
        return None


def extraer_emails_de_texto(texto: str) -> list[str]:
    """
    Busca y extrae todas las direcciones de email de un bloque de texto.

    Args:
        texto: Texto donde buscar emails.

    Returns:
        Lista de emails válidos encontrados (normalizados, sin duplicados).
    """
    if not texto:
        return []

    patron = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    encontrados = re.findall(patron, texto)

    emails_validos = []
    vistos = set()
    for email in encontrados:
        email_normalizado = normalizar_email(email)
        if email_normalizado not in vistos and validar_email(email_normalizado):
            emails_validos.append(email_normalizado)
            vistos.add(email_normalizado)

    return emails_validos


def extraer_telefonos_de_texto(texto: str, codigo_pais: str = None) -> list[str]:
    """
    Busca y extrae números de teléfono de un bloque de texto.
    Usa la librería phonenumbers para detección robusta.

    Args:
        texto: Texto donde buscar teléfonos.
        codigo_pais: Código ISO del país para ayudar al parseo.

    Returns:
        Lista de teléfonos en formato E.164, sin duplicados.
    """
    if not texto:
        return []

    telefonos = []
    vistos = set()

    # phonenumbers puede encontrar números en texto libre
    for match in phonenumbers.PhoneNumberMatcher(texto, codigo_pais or "US"):
        normalizado = phonenumbers.format_number(
            match.number, phonenumbers.PhoneNumberFormat.E164
        )
        if normalizado not in vistos:
            telefonos.append(normalizado)
            vistos.add(normalizado)

    return telefonos


def extraer_redes_sociales(texto: str) -> dict:
    """
    Busca URLs de redes sociales en un bloque de texto (o HTML).

    Args:
        texto: Texto/HTML donde buscar links de redes sociales.

    Returns:
        Diccionario con las redes encontradas: {"instagram": "url", ...}
    """
    redes = {
        "instagram": None,
        "facebook": None,
        "tiktok": None,
        "youtube": None,
        "twitter": None,
        "linkedin": None,
    }

    patrones = {
        "instagram": r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+/?',
        "facebook": r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9_./-]+/?',
        "tiktok": r'https?://(?:www\.)?tiktok\.com/@[a-zA-Z0-9_.]+/?',
        "youtube": r'https?://(?:www\.)?youtube\.com/(?:@|channel/|c/)[a-zA-Z0-9_.-]+/?',
        "twitter": r'https?://(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9_]+/?',
        "linkedin": r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9_-]+/?',
    }

    for red, patron in patrones.items():
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            redes[red] = match.group(0).rstrip("/")

    return redes
