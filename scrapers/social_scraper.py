"""
Pipeline 4: Scraper de Redes Sociales.
Extrae links a Instagram, Facebook, TikTok, YouTube, Twitter/X y LinkedIn
desde las webs de los negocios registrados.
"""

from urllib.parse import urlparse

from scrapers.base_scraper import BaseScraper
from scrapers.email_scraper import DOMINIOS_NO_NEGOCIO
from database.connection import get_session
from database.models import Negocio
from utils.validators import extraer_redes_sociales, validar_url


class SocialScraper(BaseScraper):
    """
    Extrae perfiles de redes sociales desde las webs de los negocios.
    Busca tanto en links <a> como en texto libre del HTML.
    """

    def __init__(self):
        super().__init__("social")

    def ejecutar(self, deporte: str, locacion: str, **kwargs) -> list[dict]:
        """
        Busca perfiles de redes sociales en las webs de negocios.

        Args:
            deporte: Filtrar negocios por deporte.
            locacion: Filtrar negocios por locación.
            forzar: Si True, re-procesa negocios que ya tienen redes.

        Returns:
            Lista de dicts {negocio_id, redes_sociales} actualizados.
        """
        forzar = kwargs.get("forzar", False)
        resultados = []

        negocios = self._obtener_negocios_pendientes(deporte, locacion, forzar)
        self.logger.info(f"Negocios a procesar para redes sociales: {len(negocios)}")

        for negocio_id, nombre, website in negocios:
            if not website or not validar_url(website):
                continue

            # Filtrar artículos/blogs
            dominio = urlparse(website).netloc.lower().replace("www.", "")
            if any(d in dominio for d in DOMINIOS_NO_NEGOCIO):
                continue

            self.logger.debug(f"Extrayendo redes sociales de: {nombre}")
            redes = self._extraer_redes_de_web(website)

            # Solo guardar si encontró al menos una red
            redes_encontradas = {k: v for k, v in redes.items() if v}
            if redes_encontradas:
                self._actualizar_redes(negocio_id, redes)
                resultados.append({
                    "negocio_id": negocio_id,
                    "nombre": nombre,
                    "redes_sociales": redes_encontradas,
                })
                self.logger.info(
                    f"Redes encontradas para '{nombre}': "
                    f"{', '.join(redes_encontradas.keys())}"
                )

        return resultados

    def _obtener_negocios_pendientes(self, deporte: str, locacion: str,
                                     forzar: bool) -> list[tuple]:
        """Obtiene negocios que necesitan extracción de redes sociales."""
        with get_session() as session:
            query = session.query(
                Negocio.id, Negocio.nombre, Negocio.website
            ).filter(
                Negocio.deporte == deporte,
                Negocio.website.isnot(None),
            )

            query = query.filter(
                (Negocio.pais.ilike(f"%{locacion}%")) |
                (Negocio.region.ilike(f"%{locacion}%")) |
                (Negocio.ciudad.ilike(f"%{locacion}%"))
            )

            if not forzar:
                # Solo negocios sin redes sociales
                query = query.filter(
                    (Negocio.redes_sociales == None) | (Negocio.redes_sociales == "{}")  # noqa: E711
                )

            return query.all()

    def _extraer_redes_de_web(self, website: str) -> dict:
        """
        Visita la web y extrae todos los links de redes sociales.
        Busca en la página principal (generalmente están en header/footer).
        """
        response = self.fetch(website)
        if not response:
            return {}

        soup = self.parse_html(response)
        if not soup:
            return {}

        redes = {
            "instagram": None,
            "facebook": None,
            "tiktok": None,
            "youtube": None,
            "twitter": None,
            "linkedin": None,
        }

        dominio_propio = urlparse(website).netloc.lower().replace("www.", "")

        # 1. Buscar en todos los links <a> de la página
        for link in soup.select("a[href]"):
            href = link.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            href_lower = href.lower()

            # Instagram
            if not redes["instagram"] and "instagram.com/" in href_lower:
                username = self._extraer_username_ig(href)
                if username and username not in ("p", "reel", "stories", "explore"):
                    redes["instagram"] = href.rstrip("/")

            # Facebook
            elif not redes["facebook"] and "facebook.com/" in href_lower:
                if "/sharer" not in href_lower and "/dialog" not in href_lower:
                    redes["facebook"] = href.rstrip("/")

            # TikTok
            elif not redes["tiktok"] and "tiktok.com/@" in href_lower:
                redes["tiktok"] = href.rstrip("/")

            # YouTube
            elif not redes["youtube"] and "youtube.com/" in href_lower:
                if any(x in href_lower for x in ["/@", "/channel/", "/c/", "/user/"]):
                    redes["youtube"] = href.rstrip("/")

            # Twitter / X
            elif not redes["twitter"] and ("twitter.com/" in href_lower or "x.com/" in href_lower):
                if "/intent/" not in href_lower and "/share" not in href_lower:
                    redes["twitter"] = href.rstrip("/")

            # LinkedIn
            elif not redes["linkedin"] and "linkedin.com/" in href_lower:
                if "/company/" in href_lower or "/in/" in href_lower:
                    redes["linkedin"] = href.rstrip("/")

        # 2. Fallback: buscar en el HTML completo (texto + atributos)
        if not any(redes.values()):
            html_completo = str(soup)
            redes_texto = extraer_redes_sociales(html_completo)
            for red, url in redes_texto.items():
                if url and not redes.get(red):
                    redes[red] = url

        return redes

    def _extraer_username_ig(self, url: str) -> str | None:
        """Extrae el username de Instagram de una URL."""
        try:
            path = urlparse(url).path.strip("/")
            partes = path.split("/")
            return partes[0] if partes else None
        except Exception:
            return None

    def _actualizar_redes(self, negocio_id: str, redes: dict):
        """Actualiza las redes sociales de un negocio en la base de datos."""
        with get_session() as session:
            negocio = session.query(Negocio).filter_by(id=negocio_id).first()
            if negocio:
                existentes = negocio.redes_sociales or {}
                # Solo agregar redes que no existían
                for red, url in redes.items():
                    if url and not existentes.get(red):
                        existentes[red] = url
                negocio.redes_sociales = existentes
                self._resultados_encontrados += 1
                self._resultados_nuevos += 1
