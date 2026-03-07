"""
Clase base para todos los scrapers del sistema.
Encapsula lógica común: requests con retry, rate limiting, logging, y persistencia.
"""

import time
from abc import ABC, abstractmethod
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config.settings import MAX_RETRIES, REQUEST_TIMEOUT
from database.connection import get_session
from database.models import Negocio, LogScraping
from utils.helpers import get_headers
from utils.logger import get_logger
from utils.rate_limiter import rate_limiter


class BaseScraper(ABC):
    """
    Clase base abstracta para todos los pipelines de scraping.
    Cada pipeline debe implementar el método `ejecutar()`.
    """

    def __init__(self, nombre_pipeline: str):
        """
        Args:
            nombre_pipeline: Identificador del pipeline (ej: "web", "email", "phone").
        """
        self.nombre = nombre_pipeline
        self.logger = get_logger(f"scraper.{nombre_pipeline}")
        self.session = requests.Session()
        self.session.headers.update(get_headers())

        # Contadores para el log
        self._resultados_encontrados = 0
        self._resultados_nuevos = 0
        self._errores = 0

    def fetch(self, url: str, intentos: int = MAX_RETRIES) -> requests.Response | None:
        """
        Hace un GET request con rate limiting, retry y rotación de User-Agent.

        Args:
            url: URL a descargar.
            intentos: Número máximo de reintentos.

        Returns:
            Response si fue exitoso, None si falló tras todos los intentos.
        """
        dominio = urlparse(url).netloc

        for intento in range(1, intentos + 1):
            try:
                # Rate limiting por dominio
                rate_limiter.esperar(dominio)

                # Rotar User-Agent en cada intento
                self.session.headers.update(get_headers())

                self.logger.debug(f"GET {url} (intento {intento}/{intentos})")
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)

                # Detectar bloqueos comunes
                if response.status_code == 429:
                    self.logger.warning(f"Rate limited (429) en {url}")
                    rate_limiter.registrar_error(dominio)
                    continue

                if response.status_code == 403:
                    self.logger.warning(f"Acceso denegado (403) en {url}")
                    rate_limiter.registrar_error(dominio)
                    continue

                if response.status_code == 503:
                    self.logger.warning(f"Servicio no disponible (503) en {url}")
                    rate_limiter.registrar_error(dominio)
                    continue

                # 404 = la página no existe, no reintentar
                if response.status_code == 404:
                    self.logger.debug(f"No encontrado (404): {url}")
                    return None

                if response.status_code >= 400:
                    self.logger.warning(f"HTTP {response.status_code} en {url}")
                    continue

                rate_limiter.registrar_exito(dominio)
                return response

            except requests.exceptions.Timeout:
                self.logger.warning(f"Timeout en {url} (intento {intento})")
            except requests.exceptions.ConnectionError:
                self.logger.warning(f"Error de conexión en {url} (intento {intento})")
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Error en request a {url}: {e}")

            rate_limiter.registrar_error(dominio)

        self.logger.error(f"Fallaron todos los intentos para {url}")
        self._errores += 1
        return None

    def parse_html(self, response: requests.Response) -> BeautifulSoup | None:
        """
        Parsea el HTML de una response con BeautifulSoup.

        Args:
            response: Response del request.

        Returns:
            Objeto BeautifulSoup o None si falla el parseo.
        """
        if not response:
            return None

        try:
            return BeautifulSoup(response.text, "lxml")
        except Exception as e:
            self.logger.error(f"Error parseando HTML: {e}")
            self._errores += 1
            return None

    def guardar_negocio(self, datos: dict) -> bool:
        """
        Guarda o actualiza un negocio en la base de datos.
        Deduplicación por website (dominio) o por nombre+locación.

        Args:
            datos: Diccionario con los datos del negocio.

        Returns:
            True si se guardó como nuevo, False si ya existía (actualizado).
        """
        with get_session() as session:
            existente = None

            # Buscar por website (deduplicación principal)
            if datos.get("website"):
                dominio = urlparse(datos["website"]).netloc.lower().replace("www.", "")
                existente = session.query(Negocio).filter(
                    Negocio.website.ilike(f"%{dominio}%")
                ).first()

            # Buscar por nombre + país (deduplicación secundaria)
            if not existente and datos.get("nombre") and datos.get("pais"):
                existente = session.query(Negocio).filter(
                    Negocio.nombre == datos["nombre"],
                    Negocio.pais == datos.get("pais"),
                ).first()

            if existente:
                # Actualizar campos vacíos del registro existente
                self._merge_negocio(existente, datos)
                self._resultados_encontrados += 1
                self.logger.debug(f"Actualizado: {datos.get('nombre', 'N/A')}")
                return False
            else:
                negocio = Negocio(**datos)
                session.add(negocio)
                self._resultados_encontrados += 1
                self._resultados_nuevos += 1
                self.logger.info(f"Nuevo negocio: {datos.get('nombre', 'N/A')}")
                return True

    def _merge_negocio(self, existente: Negocio, nuevos_datos: dict):
        """
        Actualiza un negocio existente con datos nuevos sin sobreescribir datos ya existentes.
        Solo rellena campos que estaban vacíos.
        """
        campos_merge = [
            "descripcion", "direccion", "latitud", "longitud",
            "precio_referencia", "rating", "reviews_count",
            "pais", "region", "ciudad",
        ]
        for campo in campos_merge:
            if nuevos_datos.get(campo) and not getattr(existente, campo, None):
                setattr(existente, campo, nuevos_datos[campo])

        # Merge de listas (emails, teléfonos)
        for campo_lista in ["emails", "telefonos"]:
            existentes = getattr(existente, campo_lista, None) or []
            nuevos = nuevos_datos.get(campo_lista, [])
            merged = list(set(existentes + nuevos))
            if merged != existentes:
                setattr(existente, campo_lista, merged)

        # Merge de redes sociales
        redes_existentes = existente.redes_sociales or {}
        redes_nuevas = nuevos_datos.get("redes_sociales", {})
        for red, url in redes_nuevas.items():
            if url and not redes_existentes.get(red):
                redes_existentes[red] = url
        existente.redes_sociales = redes_existentes

        # Merge de deportes secundarios
        dep_existentes = existente.deportes_secundarios or []
        dep_nuevos = nuevos_datos.get("deportes_secundarios", [])
        merged_dep = list(set(dep_existentes + dep_nuevos))
        if merged_dep != dep_existentes:
            existente.deportes_secundarios = merged_dep

    def registrar_log(self, deporte: str = None, locacion: str = None,
                      fuente: str = None, duracion: float = None,
                      mensaje_error: str = None):
        """
        Registra una entrada en el log de scraping.

        Args:
            deporte: Deporte buscado.
            locacion: Locación buscada.
            fuente: Fuente de datos utilizada.
            duracion: Duración de la ejecución en segundos.
            mensaje_error: Mensaje de error si hubo alguno.
        """
        with get_session() as session:
            log = LogScraping(
                pipeline=self.nombre,
                deporte=deporte,
                locacion=locacion,
                fuente=fuente,
                resultados_encontrados=self._resultados_encontrados,
                resultados_nuevos=self._resultados_nuevos,
                errores=self._errores,
                mensaje_error=mensaje_error,
                duracion_segundos=duracion,
            )
            session.add(log)

        self.logger.info(
            f"Pipeline '{self.nombre}' completado: "
            f"{self._resultados_encontrados} encontrados, "
            f"{self._resultados_nuevos} nuevos, "
            f"{self._errores} errores"
        )

    def reset_contadores(self):
        """Resetea los contadores para una nueva ejecución."""
        self._resultados_encontrados = 0
        self._resultados_nuevos = 0
        self._errores = 0

    @abstractmethod
    def ejecutar(self, deporte: str, locacion: str, **kwargs) -> list[dict]:
        """
        Método principal que cada pipeline debe implementar.

        Args:
            deporte: Deporte a buscar (ej: "surf", "yoga").
            locacion: Locación a buscar (ej: "Bali", "Costa Rica").
            **kwargs: Parámetros adicionales específicos del pipeline.

        Returns:
            Lista de diccionarios con los resultados encontrados.
        """
        pass

    def run(self, deporte: str, locacion: str, **kwargs) -> list[dict]:
        """
        Wrapper público que ejecuta el pipeline con logging y timing.

        Args:
            deporte: Deporte a buscar.
            locacion: Locación a buscar.
            **kwargs: Parámetros adicionales.

        Returns:
            Lista de resultados.
        """
        self.reset_contadores()
        self.logger.info(f"Iniciando pipeline '{self.nombre}': {deporte} en {locacion}")
        inicio = time.time()
        error_msg = None

        try:
            resultados = self.ejecutar(deporte, locacion, **kwargs)
        except Exception as e:
            self.logger.error(f"Error fatal en pipeline '{self.nombre}': {e}", exc_info=True)
            error_msg = str(e)
            resultados = []

        duracion = time.time() - inicio
        self.registrar_log(
            deporte=deporte,
            locacion=locacion,
            duracion=duracion,
            mensaje_error=error_msg,
        )

        self.logger.info(f"Pipeline '{self.nombre}' finalizado en {duracion:.1f}s")
        return resultados
