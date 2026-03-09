"""
Capa de servicio que orquesta los scrapers.
Separa la busqueda principal (rapida) del enriquecimiento (lento).
"""

from database.connection import get_session
from database.models import Negocio
from utils.logger import get_logger

logger = get_logger("service")


class ScrapingService:
    """
    Servicio central que coordina los pipelines de scraping.
    Los endpoints de la API llaman a este servicio, nunca a los scrapers directamente.
    """

    def buscar(self, deporte: str, locacion: str, tipo_negocio: str = None,
               max_resultados: int = 50, idioma: str = "en") -> dict:
        """
        Busqueda principal: solo WebScraper (Google + DuckDuckGo + directorios).
        Responde rapido (~20-40s). No ejecuta email/phone/social.

        Returns:
            Dict con "summary" y "resultados".
        """
        from scrapers.web_scraper import WebScraper

        errores = []
        fuentes = []

        web = WebScraper()
        resultados_web = web.run(deporte, locacion, tipo_negocio=tipo_negocio,
                                 max_resultados=max_resultados, idioma=idioma)

        if web._google_api_funciona and (
            __import__('config.settings', fromlist=['GOOGLE_API_KEY']).GOOGLE_API_KEY
        ):
            fuentes.append("google")
        fuentes.append("duckduckgo")
        fuentes.append("directorios")

        if web._errores > 0:
            errores.append(f"web_scraper: {web._errores} errores")

        negocios = self._leer_negocios(deporte, locacion, tipo_negocio, max_resultados)

        return {
            "summary": {
                "total_resultados": len(negocios),
                "negocios_encontrados_web": len(resultados_web),
                "fuentes_utilizadas": fuentes,
                "errores": errores,
            },
            "resultados": negocios,
        }

    def enriquecer(self, deporte: str, locacion: str,
                   max_resultados: int = 50) -> dict:
        """
        Enriquecimiento: ejecuta email + phone + social sobre negocios ya en la DB.
        Este proceso es lento (~1-2 min) y se llama por separado.

        Returns:
            Dict con "summary" y "resultados".
        """
        from scrapers.email_scraper import EmailScraper
        from scrapers.phone_scraper import PhoneScraper
        from scrapers.social_scraper import SocialScraper

        errores = []
        pipelines_ejecutados = []

        # Emails
        try:
            email_scraper = EmailScraper()
            email_scraper.run(deporte, locacion)
            pipelines_ejecutados.append("email")
        except Exception as e:
            errores.append(f"email_scraper: {str(e)}")

        # Telefonos
        try:
            phone_scraper = PhoneScraper()
            phone_scraper.run(deporte, locacion)
            pipelines_ejecutados.append("phone")
        except Exception as e:
            errores.append(f"phone_scraper: {str(e)}")

        # Redes sociales
        try:
            social_scraper = SocialScraper()
            social_scraper.run(deporte, locacion)
            pipelines_ejecutados.append("social")
        except Exception as e:
            errores.append(f"social_scraper: {str(e)}")

        negocios = self._leer_negocios(deporte, locacion, max_resultados=max_resultados)

        return {
            "summary": {
                "total_resultados": len(negocios),
                "pipelines_ejecutados": pipelines_ejecutados,
                "errores": errores,
            },
            "resultados": negocios,
        }

    def buscar_trips(self, deporte: str, locacion: str,
                     max_resultados: int = 30) -> dict:
        """Pipeline especifico para trips y retreats."""
        from scrapers.trips_scraper import TripsScraper

        errores = []
        trips = TripsScraper()
        resultados = trips.run(deporte, locacion, max_resultados=max_resultados)

        if trips._errores > 0:
            errores.append(f"trips_scraper: {trips._errores} errores")

        negocios = self._leer_negocios(deporte, locacion, max_resultados=max_resultados)

        return {
            "summary": {
                "total_resultados": len(negocios),
                "errores": errores,
            },
            "resultados": negocios,
        }

    def exportar(self, deporte: str = None, locacion: str = None) -> list[dict]:
        """Exporta negocios de la DB como lista de diccionarios."""
        with get_session() as session:
            query = session.query(Negocio)

            if deporte:
                query = query.filter(Negocio.deporte == deporte)
            if locacion:
                query = query.filter(
                    (Negocio.pais.ilike(f"%{locacion}%")) |
                    (Negocio.region.ilike(f"%{locacion}%")) |
                    (Negocio.ciudad.ilike(f"%{locacion}%"))
                )

            negocios = query.all()

            return [self._negocio_to_export(n) for n in negocios]

    def contactar(self, deporte: str = None, locacion: str = None,
                  template: str = "escuela_inicial",
                  max_envios: int = 50, dry_run: bool = True) -> dict:
        """Envia emails a negocios pendientes."""
        from automation.email_sender import EmailSender

        sender = EmailSender()
        resultado = sender.enviar_a_negocios(
            deporte=deporte,
            locacion=locacion,
            template=template,
            max_envios=max_envios,
            dry_run=dry_run,
        )
        return resultado

    def _leer_negocios(self, deporte: str, locacion: str,
                       tipo_negocio: str = None,
                       max_resultados: int = 50) -> list[dict]:
        """Lee negocios de la DB y los devuelve como diccionarios."""
        with get_session() as session:
            query = session.query(Negocio).filter(Negocio.deporte == deporte)

            query = query.filter(
                (Negocio.pais.ilike(f"%{locacion}%")) |
                (Negocio.region.ilike(f"%{locacion}%")) |
                (Negocio.ciudad.ilike(f"%{locacion}%"))
            )

            if tipo_negocio:
                query = query.filter(Negocio.tipo_negocio == tipo_negocio)

            negocios = query.order_by(Negocio.created_at.desc()).limit(max_resultados).all()
            return [n.to_dict() for n in negocios]

    def _negocio_to_export(self, n: Negocio) -> dict:
        """Convierte un negocio a formato de exportacion plano."""
        redes = n.redes_sociales or {}
        return {
            "nombre": n.nombre,
            "tipo_negocio": n.tipo_negocio,
            "deporte": n.deporte,
            "pais": n.pais,
            "region": n.region,
            "ciudad": n.ciudad,
            "website": n.website,
            "emails": ", ".join(n.emails or []),
            "telefonos": ", ".join(n.telefonos or []),
            "instagram": redes.get("instagram", ""),
            "facebook": redes.get("facebook", ""),
            "rating": n.rating,
            "reviews_count": n.reviews_count,
            "precio_referencia": n.precio_referencia,
            "fuente": n.fuente,
            "contactado": n.contactado,
            "respuesta": n.respuesta,
        }
