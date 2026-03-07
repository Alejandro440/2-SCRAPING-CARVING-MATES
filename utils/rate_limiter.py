"""
Control de rate limiting para evitar bloqueos durante el scraping.
Implementa delays adaptativos y control de frecuencia de requests.
"""

import time
import threading
from collections import deque
from config.settings import MAX_REQUESTS_PER_MINUTE, DEFAULT_DELAY_SECONDS
from utils.logger import get_logger

logger = get_logger("rate_limiter")


class RateLimiter:
    """
    Rate limiter thread-safe que controla la frecuencia de requests por dominio.
    Usa una ventana deslizante para respetar el límite de requests por minuto.
    """

    def __init__(self, requests_por_minuto: int = MAX_REQUESTS_PER_MINUTE,
                 delay_base: float = DEFAULT_DELAY_SECONDS):
        """
        Args:
            requests_por_minuto: Máximo de requests permitidos por minuto.
            delay_base: Delay mínimo entre requests en segundos.
        """
        self.requests_por_minuto = requests_por_minuto
        self.delay_base = delay_base
        self._lock = threading.Lock()
        # Historial de timestamps por dominio
        self._historial: dict[str, deque] = {}
        # Contador de errores consecutivos por dominio (para backoff)
        self._errores: dict[str, int] = {}

    def esperar(self, dominio: str = "default"):
        """
        Espera el tiempo necesario antes de hacer un request al dominio.
        Aplica delay base + delay adicional si se acerca al límite por minuto.

        Args:
            dominio: Dominio destino (para rate limiting por dominio).
        """
        with self._lock:
            ahora = time.time()

            if dominio not in self._historial:
                self._historial[dominio] = deque()

            historial = self._historial[dominio]

            # Limpiar requests de hace más de 60 segundos
            while historial and ahora - historial[0] > 60:
                historial.popleft()

            # Calcular delay necesario
            delay = self.delay_base

            # Si estamos cerca del límite, aplicar delay extra
            if len(historial) >= self.requests_por_minuto * 0.8:
                delay = max(delay, 60 / self.requests_por_minuto)
                logger.debug(f"Cerca del límite para {dominio}, delay aumentado a {delay:.1f}s")

            # Si estamos en el límite, esperar hasta que se libere un slot
            if len(historial) >= self.requests_por_minuto:
                tiempo_espera = 60 - (ahora - historial[0]) + 1
                if tiempo_espera > 0:
                    logger.info(f"Límite alcanzado para {dominio}, esperando {tiempo_espera:.1f}s")
                    delay = max(delay, tiempo_espera)

            # Backoff exponencial si hay errores consecutivos
            errores = self._errores.get(dominio, 0)
            if errores > 0:
                backoff = min(delay * (2 ** errores), 120)  # Máximo 2 minutos
                logger.debug(f"Backoff por {errores} errores en {dominio}: {backoff:.1f}s")
                delay = max(delay, backoff)

        # Esperar fuera del lock para no bloquear otros dominios
        if delay > 0:
            time.sleep(delay)

        # Registrar el request
        with self._lock:
            self._historial[dominio].append(time.time())

    def registrar_error(self, dominio: str = "default"):
        """Registra un error para activar backoff exponencial."""
        with self._lock:
            self._errores[dominio] = self._errores.get(dominio, 0) + 1
            logger.debug(f"Error #{self._errores[dominio]} para {dominio}")

    def registrar_exito(self, dominio: str = "default"):
        """Resetea el contador de errores tras un request exitoso."""
        with self._lock:
            if dominio in self._errores:
                self._errores[dominio] = 0

    def stats(self) -> dict:
        """Retorna estadísticas del rate limiter."""
        with self._lock:
            ahora = time.time()
            stats = {}
            for dominio, historial in self._historial.items():
                # Contar requests en el último minuto
                recientes = sum(1 for t in historial if ahora - t <= 60)
                stats[dominio] = {
                    "requests_ultimo_minuto": recientes,
                    "errores_consecutivos": self._errores.get(dominio, 0),
                }
            return stats


# Instancia global del rate limiter
rate_limiter = RateLimiter()
