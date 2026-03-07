"""
Pipeline 5: Scraper de Trips y Retreats.
Búsqueda especializada de surf trips, yoga retreats, adventure retreats.
Combina directorios especializados con Google Search.
"""

import re
from urllib.parse import quote_plus, urljoin

from scrapers.base_scraper import BaseScraper
from config.settings import GOOGLE_API_KEY, GOOGLE_SEARCH_ENGINE_ID
from utils.helpers import limpiar_texto, truncar
from utils.validators import (
    validar_url, extraer_emails_de_texto,
    extraer_telefonos_de_texto, extraer_redes_sociales,
)


# Fuentes específicas de trips/retreats con sus URLs de búsqueda
TRIP_SOURCES = {
    "surf": [
        {
            "nombre": "booksurfcamps",
            "url": "https://www.booksurfcamps.com/all/s/{locacion}",
            "selector_cards": "div.camp-card, a[href*='/surf-camp/'], a[href*='/surf-trip/']",
            "base_url": "https://www.booksurfcamps.com",
        },
    ],
    "yoga": [
        {
            "nombre": "bookyogaretreats",
            "url": "https://www.bookyogaretreats.com/all/d/{locacion}",
            "selector_cards": "div.retreat-card, a[href*='/retreat/']",
            "base_url": "https://www.bookyogaretreats.com",
        },
        {
            "nombre": "bookretreats",
            "url": "https://www.bookretreats.com/all/s/{locacion}",
            "selector_cards": "div.retreat-card, a[href*='/retreat/']",
            "base_url": "https://www.bookretreats.com",
        },
    ],
}

# Templates de búsqueda en Google específicos para trips/retreats
TRIP_SEARCH_TEMPLATES = [
    "{deporte} trip {locacion} 2026",
    "{deporte} retreat {locacion}",
    "{deporte} camp {locacion} packages",
    "{deporte} holiday {locacion} all inclusive",
    "best {deporte} retreat {locacion}",
    "{deporte} adventure trip {locacion}",
]


class TripsScraper(BaseScraper):
    """
    Busca trips, retreats y experiencias de deportes/wellness.
    Extrae información más detallada que el WebScraper: precios, fechas, organizador.
    """

    def __init__(self):
        super().__init__("trips")

    def ejecutar(self, deporte: str, locacion: str, **kwargs) -> list[dict]:
        """
        Busca trips y retreats por deporte y locación.

        Args:
            deporte: Deporte/actividad (ej: "surf", "yoga").
            locacion: Locación (ej: "Bali", "Costa Rica").
            max_resultados: Máximo de resultados.

        Returns:
            Lista de trips/retreats encontrados.
        """
        max_resultados = kwargs.get("max_resultados", 30)
        resultados = []
        urls_vistas = set()

        # 1. Buscar en directorios especializados de trips
        self.logger.info("Buscando en directorios de trips/retreats...")
        trips_directorios = self._buscar_en_directorios(deporte, locacion)
        for trip in trips_directorios:
            url = trip.get("website", "")
            if url not in urls_vistas:
                urls_vistas.add(url)
                resultados.append(trip)

        # 2. Buscar en Google (si hay API key)
        if GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
            self.logger.info("Buscando trips en Google...")
            trips_google = self._buscar_en_google(deporte, locacion)
            for trip in trips_google:
                url = trip.get("website", "")
                if url not in urls_vistas:
                    urls_vistas.add(url)
                    resultados.append(trip)

        # 3. Enriquecer con datos de detalle (visitar cada URL)
        self.logger.info(f"Enriqueciendo {len(resultados)} trips con datos de detalle...")
        for trip in resultados[:max_resultados]:
            if trip.get("website") and validar_url(trip["website"]):
                detalles = self._enriquecer_trip(trip["website"])
                trip.update({k: v for k, v in detalles.items() if v and not trip.get(k)})

        # 4. Guardar en base de datos
        for trip in resultados[:max_resultados]:
            self.guardar_negocio(trip)

        return resultados[:max_resultados]

    def _buscar_en_directorios(self, deporte: str, locacion: str) -> list[dict]:
        """Busca en directorios especializados de trips/retreats."""
        resultados = []

        sources = TRIP_SOURCES.get(deporte, [])
        for source in sources:
            url = source["url"].format(locacion=quote_plus(locacion))
            self.logger.info(f"Scrapeando: {source['nombre']} -> {url}")

            response = self.fetch(url)
            if not response:
                continue

            soup = self.parse_html(response)
            if not soup:
                continue

            cards = soup.select(source["selector_cards"])
            self.logger.debug(f"{source['nombre']}: {len(cards)} cards encontrados")

            for card in cards:
                try:
                    trip = self._parsear_card_trip(card, source)
                    if trip and trip.get("nombre"):
                        trip["deporte"] = deporte
                        resultados.append(trip)
                except Exception as e:
                    self.logger.debug(f"Error parseando card: {e}")

        return resultados

    def _parsear_card_trip(self, card, source: dict) -> dict | None:
        """Parsea una tarjeta de trip/retreat de un directorio."""
        # Nombre
        nombre_el = card.select_one("h2, h3, h4, .title, .name, .camp-name, .retreat-name")
        nombre = limpiar_texto(nombre_el.get_text()) if nombre_el else None
        if not nombre:
            nombre = limpiar_texto(card.get_text()) if card.name == "a" else None
        if not nombre or len(nombre) < 5:
            return None

        # URL
        link = card.get("href") or ""
        if not link:
            link_el = card.select_one("a[href]")
            link = link_el.get("href", "") if link_el else ""
        if link and not link.startswith("http"):
            link = urljoin(source["base_url"], link)

        # Precio
        precio_el = card.select_one(".price, .cost, .amount, [class*='price']")
        precio = limpiar_texto(precio_el.get_text()) if precio_el else None

        # Duración
        duracion_el = card.select_one(".duration, .days, [class*='duration'], [class*='night']")
        duracion = limpiar_texto(duracion_el.get_text()) if duracion_el else None

        # Rating
        rating = None
        rating_el = card.select_one(".rating, .score, .stars")
        if rating_el:
            match = re.search(r'([\d.]+)', rating_el.get_text())
            if match:
                try:
                    rating = float(match.group(1))
                except ValueError:
                    pass

        # Reviews
        reviews = None
        reviews_el = card.select_one(".reviews, .review-count, [class*='review']")
        if reviews_el:
            match = re.search(r'(\d+)', reviews_el.get_text())
            if match:
                reviews = int(match.group(1))

        # Locación
        loc_el = card.select_one(".location, .place, [class*='location']")
        locacion_texto = limpiar_texto(loc_el.get_text()) if loc_el else ""

        trip = {
            "nombre": nombre,
            "tipo_negocio": "retreat" if "retreat" in nombre.lower() else "trip",
            "website": link if validar_url(link) else None,
            "precio_referencia": self._formatear_precio(precio, duracion),
            "rating": rating,
            "reviews_count": reviews,
            "fuente": source["nombre"],
        }

        # Parsear locación
        if locacion_texto:
            partes = [p.strip() for p in locacion_texto.split(",")]
            if len(partes) >= 2:
                trip["ciudad"] = partes[0]
                trip["pais"] = partes[-1]
            elif partes:
                trip["pais"] = partes[0]

        return trip

    def _buscar_en_google(self, deporte: str, locacion: str) -> list[dict]:
        """Busca trips/retreats en Google Custom Search."""
        import requests as req
        from utils.rate_limiter import rate_limiter

        resultados = []

        for template in TRIP_SEARCH_TEMPLATES[:3]:  # Limitar queries para no gastar cuota
            query = template.format(deporte=deporte, locacion=locacion)
            self.logger.debug(f"Google query (trips): {query}")

            try:
                rate_limiter.esperar("googleapis.com")
                resp = req.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "key": GOOGLE_API_KEY,
                        "cx": GOOGLE_SEARCH_ENGINE_ID,
                        "q": query,
                        "num": 10,
                    },
                    timeout=15,
                )

                if resp.status_code != 200:
                    continue

                items = resp.json().get("items", [])
                for item in items:
                    titulo = item.get("title", "")
                    snippet = item.get("snippet", "")
                    texto = (titulo + " " + snippet).lower()

                    # Filtrar: solo resultados relevantes a trips/retreats
                    keywords_trip = ["trip", "retreat", "camp", "package", "holiday", "tour"]
                    if not any(kw in texto for kw in keywords_trip):
                        continue

                    trip = {
                        "nombre": titulo.strip(),
                        "tipo_negocio": "retreat" if "retreat" in texto else "trip",
                        "deporte": deporte,
                        "website": item.get("link", ""),
                        "descripcion": truncar(snippet, 500),
                        "fuente": "google_search_trips",
                    }
                    resultados.append(trip)

            except Exception as e:
                self.logger.error(f"Error en Google Search (trips): {e}")
                self._errores += 1

        return resultados

    def _enriquecer_trip(self, url: str) -> dict:
        """
        Visita la URL de un trip/retreat y extrae datos adicionales:
        emails, teléfonos, redes sociales, descripción detallada.
        """
        datos = {}

        response = self.fetch(url)
        if not response:
            return datos

        soup = self.parse_html(response)
        if not soup:
            return datos

        html_completo = str(soup)
        texto = soup.get_text(separator=" ")

        # Emails
        emails = extraer_emails_de_texto(texto)
        if emails:
            datos["emails"] = emails

        # Teléfonos
        telefonos = extraer_telefonos_de_texto(texto)
        if telefonos:
            datos["telefonos"] = telefonos

        # Redes sociales
        redes = extraer_redes_sociales(html_completo)
        redes_encontradas = {k: v for k, v in redes.items() if v}
        if redes_encontradas:
            datos["redes_sociales"] = redes

        # Descripción (meta description o primer párrafo largo)
        meta_desc = soup.select_one("meta[name='description']")
        if meta_desc:
            datos["descripcion"] = truncar(meta_desc.get("content", ""), 500)
        else:
            for p in soup.select("p"):
                texto_p = limpiar_texto(p.get_text())
                if len(texto_p) > 100:
                    datos["descripcion"] = truncar(texto_p, 500)
                    break

        return datos

    def _formatear_precio(self, precio: str, duracion: str = None) -> str | None:
        """Combina precio y duración en un string legible."""
        if not precio:
            return None
        resultado = precio
        if duracion:
            resultado += f" ({duracion})"
        return resultado
