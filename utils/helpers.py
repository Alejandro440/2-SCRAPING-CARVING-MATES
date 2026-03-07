"""
Funciones auxiliares generales del proyecto.
"""

import hashlib
import random
from urllib.parse import urlparse
from fake_useragent import UserAgent
from config.sources import FALLBACK_USER_AGENTS


# Inicializar fake_useragent (con fallback si falla la conexión)
try:
    _ua = UserAgent()
except Exception:
    _ua = None


def get_random_user_agent() -> str:
    """Retorna un User-Agent aleatorio para rotar en los requests."""
    if _ua:
        try:
            return _ua.random
        except Exception:
            pass
    return random.choice(FALLBACK_USER_AGENTS)


def get_headers() -> dict:
    """Retorna headers HTTP realistas para un request de scraping."""
    return {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def generar_id_negocio(nombre: str, website: str = None, locacion: str = None) -> str:
    """
    Genera un ID determinístico para un negocio basado en su nombre y website/locación.
    Útil para deduplicación: el mismo negocio siempre genera el mismo ID.

    Args:
        nombre: Nombre del negocio.
        website: URL del website (opcional).
        locacion: Locación del negocio (opcional).

    Returns:
        UUID-like string determinístico.
    """
    clave = nombre.strip().lower()
    if website:
        dominio = extraer_dominio_simple(website)
        if dominio:
            clave += f"|{dominio}"
    elif locacion:
        clave += f"|{locacion.strip().lower()}"

    hash_hex = hashlib.sha256(clave.encode()).hexdigest()
    # Formato UUID: 8-4-4-4-12
    return f"{hash_hex[:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}-{hash_hex[16:20]}-{hash_hex[20:32]}"


def extraer_dominio_simple(url: str) -> str | None:
    """Extrae el dominio de una URL sin www."""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        dominio = parsed.netloc.lower()
        if dominio.startswith("www."):
            dominio = dominio[4:]
        return dominio or None
    except Exception:
        return None


def limpiar_texto(texto: str) -> str:
    """Limpia un texto: elimina espacios extra, saltos de línea múltiples."""
    if not texto:
        return ""
    import re
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def truncar(texto: str, max_len: int = 500) -> str:
    """Trunca un texto a un máximo de caracteres."""
    if not texto or len(texto) <= max_len:
        return texto or ""
    return texto[:max_len - 3] + "..."
