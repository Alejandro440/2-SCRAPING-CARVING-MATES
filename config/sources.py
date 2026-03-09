"""
Fuentes de scraping organizadas por tipo.
Cada fuente tiene un nombre, URL base, y los deportes/tipos que soporta.
Fácilmente extensible: solo agregar nuevas entradas al diccionario.
"""

# Directorios especializados por deporte
DIRECTORIOS = {
    "surf": [
        {
            "nombre": "BookSurfCamps",
            "url_base": "https://www.booksurfcamps.com",
            "url_busqueda": "https://www.booksurfcamps.com/all/s/{locacion}",
            "tipos": ["escuela", "camp", "retreat"],
        },
        {
            "nombre": "Surfline",
            "url_base": "https://www.surfline.com",
            "url_busqueda": None,  # Requiere scraping más específico
            "tipos": ["escuela"],
        },
    ],
    "yoga": [
        {
            "nombre": "BookYogaRetreats",
            "url_base": "https://www.bookyogaretreats.com",
            "url_busqueda": "https://www.bookyogaretreats.com/all/d/{locacion}",
            "tipos": ["retreat", "camp"],
        },
        {
            "nombre": "BookRetreats",
            "url_base": "https://www.bookretreats.com",
            "url_busqueda": "https://www.bookretreats.com/all/s/{locacion}",
            "tipos": ["retreat"],
        },
    ],
    "kitesurf": [
        {
            "nombre": "BookKitesurfCamps",
            "url_base": "https://www.booksurfcamps.com/kitesurf",
            "url_busqueda": "https://www.booksurfcamps.com/kitesurf/s/{locacion}",
            "tipos": ["escuela", "camp"],
        },
    ],
}

# Páginas internas donde buscar datos de contacto
CONTACT_PATHS = [
    "/contact",
    "/contacto",
    "/contact-us",
    "/about",
    "/about-us",
    "/sobre-nosotros",
    "/impressum",
    "/kontakt",
]

# User-Agents rotativos (se complementan con fake-useragent)
FALLBACK_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]
