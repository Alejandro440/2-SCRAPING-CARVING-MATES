"""
Pipeline 3: Scraper de Teléfonos.
Extrae números de teléfono de las webs de negocios registrados.
Detecta formatos internacionales y normaliza a E.164.
"""

from urllib.parse import urljoin, urlparse

from scrapers.base_scraper import BaseScraper
from scrapers.email_scraper import DOMINIOS_NO_NEGOCIO
from database.connection import get_session
from database.models import Negocio
from utils.validators import extraer_telefonos_de_texto, validar_url
from config.sources import CONTACT_PATHS

# Mapeo de países a códigos ISO para mejorar detección de teléfonos
PAIS_A_CODIGO = {
    "spain": "ES", "españa": "ES", "spain": "ES",
    "united states": "US", "usa": "US", "estados unidos": "US",
    "united kingdom": "GB", "uk": "GB", "reino unido": "GB",
    "france": "FR", "francia": "FR",
    "portugal": "PT",
    "germany": "DE", "alemania": "DE",
    "italy": "IT", "italia": "IT",
    "indonesia": "ID",
    "australia": "AU",
    "brazil": "BR", "brasil": "BR",
    "mexico": "MX", "méxico": "MX",
    "costa rica": "CR",
    "morocco": "MA", "marruecos": "MA",
    "south africa": "ZA", "sudáfrica": "ZA",
    "sri lanka": "LK",
    "maldives": "MV", "maldivas": "MV",
    "japan": "JP", "japón": "JP",
    "peru": "PE", "perú": "PE",
    "chile": "CL",
    "argentina": "AR",
    "colombia": "CO",
    "panama": "PA", "panamá": "PA",
    "ecuador": "EC",
    "nicaragua": "NI",
    "el salvador": "SV",
    "philippines": "PH", "filipinas": "PH",
    "thailand": "TH", "tailandia": "TH",
    "india": "IN",
    "new zealand": "NZ", "nueva zelanda": "NZ",
    "canada": "CA", "canadá": "CA",
    "norway": "NO", "noruega": "NO",
    "sweden": "SE", "suecia": "SE",
    "denmark": "DK", "dinamarca": "DK",
    "greece": "GR", "grecia": "GR",
    "croatia": "HR", "croacia": "HR",
    "ireland": "IE", "irlanda": "IE",
    "netherlands": "NL", "holanda": "NL",
}


class PhoneScraper(BaseScraper):
    """
    Extrae números de teléfono de las webs de negocios.
    Usa la librería phonenumbers para detección robusta y normalización E.164.
    """

    def __init__(self):
        super().__init__("phone")

    def ejecutar(self, deporte: str, locacion: str, **kwargs) -> list[dict]:
        """
        Busca teléfonos en las webs de negocios ya registrados.

        Args:
            deporte: Filtrar negocios por deporte.
            locacion: Filtrar negocios por locación.
            forzar: Si True, re-procesa negocios que ya tienen teléfonos.

        Returns:
            Lista de dicts {negocio_id, telefonos} actualizados.
        """
        forzar = kwargs.get("forzar", False)
        resultados = []

        negocios = self._obtener_negocios_pendientes(deporte, locacion, forzar)
        self.logger.info(f"Negocios a procesar para teléfonos: {len(negocios)}")

        for negocio_id, nombre, website, pais in negocios:
            if not website or not validar_url(website):
                continue

            # Filtrar artículos/blogs
            dominio = urlparse(website).netloc.lower().replace("www.", "")
            if any(d in dominio for d in DOMINIOS_NO_NEGOCIO):
                continue

            # Determinar código de país para mejor detección
            codigo_pais = self._resolver_codigo_pais(pais, locacion)

            self.logger.debug(f"Extrayendo teléfonos de: {nombre} (país: {codigo_pais})")
            telefonos = self._extraer_telefonos_de_web(website, codigo_pais)

            if telefonos:
                self._actualizar_telefonos(negocio_id, telefonos)
                resultados.append({
                    "negocio_id": negocio_id,
                    "nombre": nombre,
                    "telefonos": telefonos,
                })
                self.logger.info(f"Teléfonos encontrados para '{nombre}': {telefonos}")

        return resultados

    def _obtener_negocios_pendientes(self, deporte: str, locacion: str,
                                     forzar: bool) -> list[tuple]:
        """Obtiene negocios que necesitan extracción de teléfonos."""
        with get_session() as session:
            query = session.query(
                Negocio.id, Negocio.nombre, Negocio.website, Negocio.pais
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
                query = query.filter(
                    (Negocio.telefonos == None) | (Negocio.telefonos == "[]")  # noqa: E711
                )

            return query.all()

    def _resolver_codigo_pais(self, pais: str, locacion: str) -> str:
        """Resuelve el código ISO del país a partir del nombre o la locación."""
        for texto in [pais, locacion]:
            if texto:
                codigo = PAIS_A_CODIGO.get(texto.lower().strip())
                if codigo:
                    return codigo
        return "US"  # Default si no se reconoce

    def _extraer_telefonos_de_web(self, website: str, codigo_pais: str) -> list[str]:
        """
        Visita la web del negocio y extrae teléfonos.
        Busca en página principal, páginas de contacto y links tel:.
        """
        todos_telefonos = set()
        parsed = urlparse(website)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # 1. Página principal
        telefonos_main = self._extraer_telefonos_de_url(website, codigo_pais)
        todos_telefonos.update(telefonos_main)

        # 2. Páginas de contacto en la RAÍZ del dominio
        if not todos_telefonos:
            for path in CONTACT_PATHS:
                url_contacto = base_url.rstrip("/") + "/" + path.lstrip("/")
                telefonos_contacto = self._extraer_telefonos_de_url(url_contacto, codigo_pais)
                todos_telefonos.update(telefonos_contacto)

                if todos_telefonos:
                    break

        return sorted(todos_telefonos)

    def _extraer_telefonos_de_url(self, url: str, codigo_pais: str) -> list[str]:
        """Descarga una URL y extrae teléfonos del HTML."""
        response = self.fetch(url)
        if not response:
            return []

        soup = self.parse_html(response)
        if not soup:
            return []

        telefonos = set()

        # 1. Buscar en enlaces tel:
        for link in soup.select("a[href^='tel:']"):
            href = link.get("href", "")
            numero = href.replace("tel:", "").strip()
            encontrados = extraer_telefonos_de_texto(numero, codigo_pais)
            telefonos.update(encontrados)

        # 2. Buscar en todo el texto
        texto_pagina = soup.get_text(separator=" ")
        telefonos_texto = extraer_telefonos_de_texto(texto_pagina, codigo_pais)
        telefonos.update(telefonos_texto)

        # 3. Buscar específicamente en el footer
        footer = soup.select_one("footer, #footer, .footer")
        if footer:
            telefonos_footer = extraer_telefonos_de_texto(
                footer.get_text(separator=" "), codigo_pais
            )
            telefonos.update(telefonos_footer)

        return list(telefonos)

    def _actualizar_telefonos(self, negocio_id: str, telefonos: list[str]):
        """Actualiza los teléfonos de un negocio en la base de datos."""
        with get_session() as session:
            negocio = session.query(Negocio).filter_by(id=negocio_id).first()
            if negocio:
                existentes = negocio.telefonos or []
                merged = list(set(existentes + telefonos))
                negocio.telefonos = merged
                self._resultados_encontrados += 1
                if not existentes:
                    self._resultados_nuevos += 1
