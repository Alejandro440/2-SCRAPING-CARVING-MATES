"""
Pipeline 2: Scraper de Emails.
A partir de URLs de negocios, visita sus webs y extrae emails de contacto.
Busca en página principal, /contact, /about, footer y mailto: links.
"""

from urllib.parse import urljoin, urlparse

from scrapers.base_scraper import BaseScraper
from database.connection import get_session
from database.models import Negocio
from utils.validators import extraer_emails_de_texto, validar_url
from config.sources import CONTACT_PATHS

# Dominios que son artículos/blogs/listas, no negocios contactables
DOMINIOS_NO_NEGOCIO = [
    "thesmartlocal.com", "theworldbucketlist.com", "theculturetrip.com",
    "lonelyplanet.com", "tripadvisor.com", "timeout.com",
    "nomadicmatt.com", "travelandleisure.com", "cntraveler.com",
    "hostelworld.com", "booking.com", "expedia.com",
    "medium.com", "reddit.com", "quora.com",
    "secretseaweed.com", "thesurfatlas.com", "magicseaweed.com",
    "surfline.com", "wannasurf.com",
    "wikipedia.org", "wikivoyage.org",
]


class EmailScraper(BaseScraper):
    """
    Extrae emails de contacto visitando las webs de los negocios.
    Filtra artículos/blogs y solo procesa webs de negocios reales.
    """

    def __init__(self):
        super().__init__("email")

    def ejecutar(self, deporte: str, locacion: str, **kwargs) -> list[dict]:
        """
        Busca emails en las webs de negocios ya registrados.

        Args:
            deporte: Filtrar negocios por deporte.
            locacion: Filtrar negocios por locación (país o región).
            forzar: Si True, re-procesa negocios que ya tienen emails.

        Returns:
            Lista de dicts {negocio_id, emails} actualizados.
        """
        forzar = kwargs.get("forzar", False)
        resultados = []

        negocios = self._obtener_negocios_pendientes(deporte, locacion, forzar)
        self.logger.info(f"Negocios a procesar para emails: {len(negocios)}")

        for negocio_id, nombre, website in negocios:
            if not website or not validar_url(website):
                continue

            # Filtrar URLs que son artículos/blogs, no negocios
            if self._es_articulo(website):
                self.logger.debug(f"Saltando artículo/blog: {website}")
                continue

            self.logger.debug(f"Extrayendo emails de: {nombre} ({website})")
            emails = self._extraer_emails_de_web(website)

            if emails:
                self._actualizar_emails(negocio_id, emails)
                resultados.append({"negocio_id": negocio_id, "nombre": nombre, "emails": emails})
                self.logger.info(f"Emails encontrados para '{nombre}': {emails}")
            else:
                self.logger.debug(f"No se encontraron emails para '{nombre}'")

        return resultados

    def _es_articulo(self, url: str) -> bool:
        """
        Detecta si una URL es un artículo/blog/lista en vez de un negocio real.
        Estos no tienen emails de contacto útiles.
        """
        dominio = urlparse(url).netloc.lower().replace("www.", "")
        path = urlparse(url).path.lower()

        # Dominio conocido como no-negocio
        for d in DOMINIOS_NO_NEGOCIO:
            if d in dominio:
                return True

        # Paths típicos de artículos
        patrones_articulo = [
            "/read/", "/blog/", "/article/", "/post/",
            "/best-", "/top-", "/guide-", "/list-",
            "/review/", "/news/",
        ]
        for patron in patrones_articulo:
            if patron in path:
                return True

        return False

    def _obtener_negocios_pendientes(self, deporte: str, locacion: str,
                                     forzar: bool) -> list[tuple]:
        """Obtiene negocios que necesitan extracción de emails."""
        with get_session() as session:
            query = session.query(
                Negocio.id, Negocio.nombre, Negocio.website
            ).filter(
                Negocio.deporte == deporte,
                Negocio.website.isnot(None),
            )

            # Filtrar por locación (país o región)
            query = query.filter(
                (Negocio.pais.ilike(f"%{locacion}%")) |
                (Negocio.region.ilike(f"%{locacion}%")) |
                (Negocio.ciudad.ilike(f"%{locacion}%"))
            )

            if not forzar:
                query = query.filter(
                    (Negocio.emails == None) | (Negocio.emails == "[]")  # noqa: E711
                )

            return query.all()

    def _extraer_emails_de_web(self, website: str) -> list[str]:
        """
        Visita la web del negocio y extrae emails.
        Las contact paths se buscan en la raíz del dominio, no relativas a la URL.
        """
        todos_emails = set()
        parsed = urlparse(website)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # 1. Página principal (la URL original)
        emails_main = self._extraer_emails_de_url(website)
        todos_emails.update(emails_main)

        # 2. Si la URL no era la raíz, probar también la home
        if parsed.path and parsed.path != "/":
            emails_home = self._extraer_emails_de_url(base_url)
            todos_emails.update(emails_home)

        # 3. Páginas de contacto en la RAÍZ del dominio (no relativas a la URL)
        if not todos_emails:
            for path in CONTACT_PATHS:
                url_contacto = base_url.rstrip("/") + "/" + path.lstrip("/")

                emails_contacto = self._extraer_emails_de_url(url_contacto)
                todos_emails.update(emails_contacto)

                if todos_emails:
                    break  # Ya encontramos emails

        return sorted(todos_emails)

    def _extraer_emails_de_url(self, url: str) -> list[str]:
        """
        Descarga una URL y extrae todos los emails del HTML.
        Busca en mailto: links, texto visible, footer, y meta tags.
        """
        response = self.fetch(url)
        if not response:
            return []

        soup = self.parse_html(response)
        if not soup:
            return []

        emails = set()

        # 1. Buscar en enlaces mailto:
        for link in soup.select("a[href^='mailto:']"):
            href = link.get("href", "")
            email = href.replace("mailto:", "").split("?")[0].strip()
            emails_validados = extraer_emails_de_texto(email)
            emails.update(emails_validados)

        # 2. Buscar en todo el texto de la página
        texto_pagina = soup.get_text(separator=" ")
        emails_texto = extraer_emails_de_texto(texto_pagina)
        emails.update(emails_texto)

        # 3. Buscar específicamente en el footer
        footer = soup.select_one("footer, #footer, .footer, [role='contentinfo']")
        if footer:
            emails_footer = extraer_emails_de_texto(footer.get_text(separator=" "))
            emails.update(emails_footer)

        # 4. Buscar en meta tags y structured data
        for meta in soup.select("meta[content*='@']"):
            content = meta.get("content", "")
            emails_meta = extraer_emails_de_texto(content)
            emails.update(emails_meta)

        return list(emails)

    def _actualizar_emails(self, negocio_id: str, emails: list[str]):
        """Actualiza los emails de un negocio en la base de datos."""
        with get_session() as session:
            negocio = session.query(Negocio).filter_by(id=negocio_id).first()
            if negocio:
                existentes = negocio.emails or []
                merged = list(set(existentes + emails))
                negocio.emails = merged
                self._resultados_encontrados += 1
                if not existentes:
                    self._resultados_nuevos += 1
