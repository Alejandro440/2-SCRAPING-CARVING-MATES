"""
Pipeline 1: Scraper de Paginas Web.
Busca negocios (escuelas, shops, retreats) por deporte y locacion.
Fuentes abiertas: DuckDuckGo HTML (sin API key) + directorios especializados.
"""

import re
from urllib.parse import quote_plus, urljoin, urlparse

import requests

from scrapers.base_scraper import BaseScraper
from config.sources import DIRECTORIOS
from utils.helpers import limpiar_texto, truncar
from utils.validators import validar_url, normalizar_url


class WebScraper(BaseScraper):
    """
    Busca negocios en la web por deporte y locacion.
    Estrategia: DuckDuckGo (principal) + directorios especializados.
    No requiere API keys. Totalmente open source.
    """

    def __init__(self):
        super().__init__("web")

    def ejecutar(self, deporte: str, locacion: str, **kwargs) -> list[dict]:
        """
        Ejecuta la busqueda de negocios.

        Args:
            deporte: Deporte a buscar (ej: "surf").
            locacion: Locacion a buscar (ej: "Bali").
            tipo_negocio: Filtro opcional por tipo (ej: "escuela").
            max_resultados: Maximo de resultados totales.
            idioma: Idioma de busqueda ("en", "es", etc.).

        Returns:
            Lista de negocios encontrados como diccionarios.
        """
        tipo_negocio = kwargs.get("tipo_negocio")
        max_resultados = kwargs.get("max_resultados", 50)

        resultados = []
        urls_vistas = set()

        # 1. DuckDuckGo como fuente principal (sin API key, siempre disponible)
        self.logger.info("Buscando en DuckDuckGo...")
        resultados_ddg = self._buscar_duckduckgo(
            deporte, locacion, tipo_negocio, max_resultados
        )
        for r in resultados_ddg:
            url = r.get("website", "")
            if url and url not in urls_vistas:
                urls_vistas.add(url)
                resultados.append(r)

        # 2. Buscar en directorios especializados
        self.logger.info("Buscando en directorios especializados...")
        resultados_directorios = self._buscar_directorios(deporte, locacion, tipo_negocio)
        for r in resultados_directorios:
            url = r.get("website", "")
            if url and url not in urls_vistas:
                urls_vistas.add(url)
                resultados.append(r)

        # 3. Guardar en base de datos
        for negocio in resultados[:max_resultados]:
            self.guardar_negocio(negocio)

        return resultados[:max_resultados]

    # =========================================================================
    # DuckDuckGo Search (sin API key, siempre disponible)
    # =========================================================================

    def _buscar_duckduckgo(self, deporte: str, locacion: str,
                           tipo_negocio: str = None,
                           max_resultados: int = 30) -> list[dict]:
        """
        Busca negocios en DuckDuckGo HTML.
        No requiere API key y no tiene limites estrictos.
        """
        resultados = []

        queries = self._generar_queries(deporte, locacion, tipo_negocio)

        for query in queries:
            if len(resultados) >= max_resultados:
                break

            self.logger.debug(f"DuckDuckGo query: {query}")
            nuevos = self._duckduckgo_search(query)

            for item in nuevos:
                item["deporte"] = deporte
                item["fuente"] = "duckduckgo"
                if tipo_negocio:
                    item["tipo_negocio"] = tipo_negocio
                item.setdefault("region", locacion)
                resultados.append(item)

        self.logger.info(f"DuckDuckGo: {len(resultados)} resultados totales")
        return resultados

    def _duckduckgo_search(self, query: str) -> list[dict]:
        """
        Ejecuta una busqueda en DuckDuckGo HTML y parsea los resultados.
        """
        url = "https://html.duckduckgo.com/html/"
        data = {"q": query, "b": ""}

        response = self.fetch_post(url, data=data)
        if not response:
            return []

        soup = self.parse_html(response)
        if not soup:
            return []

        resultados = []

        for result in soup.select(".result"):
            try:
                link_el = result.select_one("a.result__a")
                if not link_el:
                    continue

                titulo = limpiar_texto(link_el.get_text())
                href = link_el.get("href", "")

                website = self._extraer_url_ddg(href)
                if not website or not validar_url(website):
                    continue

                dominio = urlparse(website).netloc.lower()
                if self._es_dominio_irrelevante(dominio):
                    continue

                snippet_el = result.select_one(".result__snippet")
                snippet = limpiar_texto(snippet_el.get_text()) if snippet_el else ""

                negocio = {
                    "nombre": titulo,
                    "website": website,
                    "descripcion": truncar(snippet, 500),
                    "tipo_negocio": self._inferir_tipo_negocio(titulo + " " + snippet),
                }

                loc = self._extraer_locacion_snippet(snippet)
                if loc:
                    negocio.update(loc)

                resultados.append(negocio)

            except Exception as e:
                self.logger.debug(f"Error parseando resultado DuckDuckGo: {e}")
                continue

        return resultados

    def _extraer_url_ddg(self, href: str) -> str | None:
        """Extrae la URL real de un redirect de DuckDuckGo."""
        if not href:
            return None

        if href.startswith("http") and "duckduckgo.com" not in href:
            return href

        match = re.search(r'uddg=([^&]+)', href)
        if match:
            from urllib.parse import unquote
            return unquote(match.group(1))

        return None

    def _es_dominio_irrelevante(self, dominio: str) -> bool:
        """Filtra dominios que no son negocios reales."""
        irrelevantes = [
            "wikipedia.org", "youtube.com", "facebook.com", "instagram.com",
            "twitter.com", "x.com", "tiktok.com", "linkedin.com",
            "reddit.com", "pinterest.com", "amazon.com", "ebay.com",
            "tripadvisor.com", "yelp.com", "google.com", "maps.google.com",
        ]
        return any(irr in dominio for irr in irrelevantes)

    def fetch_post(self, url: str, data: dict = None) -> requests.Response | None:
        """
        Hace un POST request (necesario para DuckDuckGo HTML).
        Mismo rate limiting y retry que fetch().
        """
        from config.settings import MAX_RETRIES, REQUEST_TIMEOUT
        from utils.helpers import get_headers
        from utils.rate_limiter import rate_limiter

        dominio = urlparse(url).netloc

        for intento in range(1, MAX_RETRIES + 1):
            try:
                rate_limiter.esperar(dominio)
                headers = get_headers()

                self.logger.debug(f"POST {url} (intento {intento})")
                response = requests.post(
                    url, data=data, headers=headers, timeout=REQUEST_TIMEOUT
                )

                if response.status_code == 200:
                    rate_limiter.registrar_exito(dominio)
                    return response

                self.logger.warning(f"HTTP {response.status_code} en POST {url}")
                rate_limiter.registrar_error(dominio)

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Error en POST a {url}: {e}")
                rate_limiter.registrar_error(dominio)

        self._errores += 1
        return None

    # =========================================================================
    # Directorios especializados
    # =========================================================================

    def _buscar_directorios(self, deporte: str, locacion: str,
                            tipo_negocio: str = None) -> list[dict]:
        """Busca en directorios especializados configurados en sources.py."""
        resultados = []

        directorios = DIRECTORIOS.get(deporte, [])
        if not directorios:
            self.logger.info(f"No hay directorios configurados para '{deporte}'")
            return resultados

        for directorio in directorios:
            if tipo_negocio and tipo_negocio not in directorio["tipos"]:
                continue
            if not directorio.get("url_busqueda"):
                continue

            url = directorio["url_busqueda"].format(locacion=quote_plus(locacion))
            self.logger.info(f"Scrapeando directorio: {directorio['nombre']} -> {url}")

            response = self.fetch(url)
            if not response:
                continue

            soup = self.parse_html(response)
            if not soup:
                continue

            nombre_dir = directorio["nombre"].lower()
            if "booksurfcamps" in nombre_dir:
                nuevos = self._parsear_booksurfcamps(soup, deporte, directorio["nombre"])
            elif "bookyogaretreats" in nombre_dir or "bookretreats" in nombre_dir:
                nuevos = self._parsear_bookretreats(soup, deporte, directorio["nombre"])
            else:
                nuevos = self._parsear_generico(soup, deporte, directorio["nombre"])

            resultados.extend(nuevos)
            self.logger.info(f"{directorio['nombre']}: {len(nuevos)} resultados")

        return resultados

    def _parsear_booksurfcamps(self, soup, deporte: str, fuente: str) -> list[dict]:
        """Parsea resultados de BookSurfCamps."""
        resultados = []

        cards = soup.select("div.camp-card, article.camp-item, div.listing-card, a.camp-link")
        if not cards:
            cards = soup.select("a[href*='/surf-camp/'], a[href*='/surf-school/']")

        for card in cards:
            try:
                nombre_el = card.select_one("h2, h3, h4, .camp-name, .title")
                nombre = limpiar_texto(nombre_el.get_text()) if nombre_el else None
                if not nombre:
                    nombre = limpiar_texto(card.get_text()) if card.name == "a" else None
                if not nombre:
                    continue

                link = card.get("href") or ""
                if not link:
                    link_el = card.select_one("a[href]")
                    link = link_el.get("href", "") if link_el else ""
                if link and not link.startswith("http"):
                    link = urljoin("https://www.booksurfcamps.com", link)

                loc_el = card.select_one(".location, .camp-location, .subtitle")
                locacion_texto = limpiar_texto(loc_el.get_text()) if loc_el else ""

                precio_el = card.select_one(".price, .camp-price, .cost")
                precio = limpiar_texto(precio_el.get_text()) if precio_el else None

                rating = None
                rating_el = card.select_one(".rating, .stars, .score")
                if rating_el:
                    rating_match = re.search(r'[\d.]+', rating_el.get_text())
                    if rating_match:
                        rating = float(rating_match.group())

                negocio = {
                    "nombre": nombre,
                    "tipo_negocio": self._inferir_tipo_negocio(nombre),
                    "deporte": deporte,
                    "website": link if validar_url(link) else None,
                    "precio_referencia": precio,
                    "rating": rating,
                    "fuente": fuente.lower().replace(" ", "_"),
                }

                if locacion_texto:
                    partes = [p.strip() for p in locacion_texto.split(",")]
                    if len(partes) >= 2:
                        negocio["ciudad"] = partes[0]
                        negocio["pais"] = partes[-1]
                    elif len(partes) == 1:
                        negocio["pais"] = partes[0]

                resultados.append(negocio)
            except Exception as e:
                self.logger.debug(f"Error parseando card de {fuente}: {e}")

        return resultados

    def _parsear_bookretreats(self, soup, deporte: str, fuente: str) -> list[dict]:
        """Parsea resultados de BookYogaRetreats / BookRetreats."""
        resultados = []

        cards = soup.select(
            "div.retreat-card, article.retreat-item, div.listing-card, "
            "a[href*='/retreat/'], a[href*='/yoga-retreat/']"
        )

        for card in cards:
            try:
                nombre_el = card.select_one("h2, h3, h4, .retreat-name, .title")
                nombre = limpiar_texto(nombre_el.get_text()) if nombre_el else None
                if not nombre:
                    nombre = limpiar_texto(card.get_text()) if card.name == "a" else None
                if not nombre:
                    continue

                link = card.get("href") or ""
                if not link:
                    link_el = card.select_one("a[href]")
                    link = link_el.get("href", "") if link_el else ""
                if link and not link.startswith("http"):
                    link = urljoin("https://www.bookyogaretreats.com", link)

                precio_el = card.select_one(".price, .retreat-price")
                precio = limpiar_texto(precio_el.get_text()) if precio_el else None

                negocio = {
                    "nombre": nombre,
                    "tipo_negocio": "retreat",
                    "deporte": deporte,
                    "website": link if validar_url(link) else None,
                    "precio_referencia": precio,
                    "fuente": fuente.lower().replace(" ", "_"),
                }
                resultados.append(negocio)
            except Exception as e:
                self.logger.debug(f"Error parseando card de {fuente}: {e}")

        return resultados

    def _parsear_generico(self, soup, deporte: str, fuente: str) -> list[dict]:
        """Parser generico para directorios no reconocidos."""
        resultados = []

        selectores = [
            "article", "div.card", "div.listing", "div.item",
            "div.result", "li.result", "div.business",
        ]

        cards = []
        for selector in selectores:
            cards = soup.select(selector)
            if len(cards) >= 3:
                break

        for card in cards[:30]:
            try:
                titulo_el = card.select_one("h1, h2, h3, h4, .title, .name")
                if not titulo_el:
                    continue
                nombre = limpiar_texto(titulo_el.get_text())
                if not nombre or len(nombre) < 3:
                    continue

                link_el = card.select_one("a[href]")
                link = link_el.get("href", "") if link_el else ""
                if link and not link.startswith("http"):
                    link = urljoin(fuente, link)

                desc_el = card.select_one("p, .description, .excerpt, .summary")
                descripcion = truncar(limpiar_texto(desc_el.get_text())) if desc_el else None

                negocio = {
                    "nombre": nombre,
                    "tipo_negocio": self._inferir_tipo_negocio(nombre + " " + (descripcion or "")),
                    "deporte": deporte,
                    "website": link if validar_url(link) else None,
                    "descripcion": descripcion,
                    "fuente": fuente.lower().replace(" ", "_"),
                }
                resultados.append(negocio)
            except Exception as e:
                self.logger.debug(f"Error en parser generico: {e}")

        return resultados

    # =========================================================================
    # Helpers
    # =========================================================================

    def _generar_queries(self, deporte: str, locacion: str,
                        tipo_negocio: str = None) -> list[str]:
        """Genera queries de busqueda optimizadas."""
        queries = []

        if tipo_negocio:
            tipo_en = {
                "escuela": "school", "alquiler": "rental", "retreat": "retreat",
                "trip": "trip", "camp": "camp", "shop": "shop",
            }.get(tipo_negocio, tipo_negocio)
            queries.append(f"{deporte} {tipo_en} {locacion}")
            queries.append(f"best {deporte} {tipo_en} in {locacion}")
        else:
            queries.append(f"{deporte} school {locacion}")
            queries.append(f"{deporte} lessons {locacion}")
            queries.append(f"{deporte} camp {locacion}")
            queries.append(f"best {deporte} schools in {locacion}")
            queries.append(f"{deporte} rental {locacion}")

        return queries

    def _inferir_tipo_negocio(self, texto: str) -> str:
        """Infiere el tipo de negocio a partir del texto."""
        texto = texto.lower()

        tipos_keywords = {
            "retreat": ["retreat", "retiro"],
            "camp": ["camp", "campamento"],
            "escuela": ["school", "escuela", "lessons", "clases", "academy", "academia", "learn"],
            "trip": ["trip", "tour", "viaje", "adventure", "excursion"],
            "alquiler": ["rental", "alquiler", "hire", "rent"],
            "shop": ["shop", "store", "tienda", "outlet"],
        }

        for tipo, keywords in tipos_keywords.items():
            for keyword in keywords:
                if keyword in texto:
                    return tipo

        return "escuela"

    def _extraer_locacion_snippet(self, snippet: str) -> dict | None:
        """Intenta extraer pais/ciudad del snippet."""
        if not snippet:
            return None
        match = re.search(
            r'in\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)',
            snippet
        )
        if match:
            return {"ciudad": match.group(1), "pais": match.group(2)}
        return None
