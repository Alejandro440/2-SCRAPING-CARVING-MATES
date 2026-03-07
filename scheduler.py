"""
Scheduler para ejecución periódica de los pipelines.
Permite programar búsquedas automáticas por deporte y locación.

Uso:
    python scheduler.py                     → Ejecuta el scheduler con las tareas por defecto
    python scheduler.py --once              → Ejecuta todas las tareas una vez y sale

Configuración:
    Edita la lista TAREAS_PROGRAMADAS abajo para definir qué buscar y con qué frecuencia.
"""

import sys
import signal
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from database.connection import init_db
from utils.logger import get_logger

logger = get_logger("scheduler")

# ============================================================================
# CONFIGURACIÓN DE TAREAS PROGRAMADAS
# Edita esta lista para definir qué búsquedas ejecutar automáticamente.
#
# Cada tarea tiene:
#   - deporte: str
#   - locacion: str
#   - tipo_negocio: str (opcional)
#   - pipelines: list de pipelines a ejecutar ("web", "email", "phone", "social", "trips")
#   - cron: expresión cron para la frecuencia (día_semana hora:minuto)
# ============================================================================

TAREAS_PROGRAMADAS = [
    # Surf — búsquedas semanales (lunes a las 8am)
    {
        "deporte": "surf",
        "locacion": "Bali",
        "pipelines": ["web", "email", "phone", "social"],
        "cron": {"day_of_week": "mon", "hour": 8, "minute": 0},
    },
    {
        "deporte": "surf",
        "locacion": "Portugal",
        "pipelines": ["web", "email", "phone", "social"],
        "cron": {"day_of_week": "mon", "hour": 9, "minute": 0},
    },
    {
        "deporte": "surf",
        "locacion": "Costa Rica",
        "pipelines": ["web", "email", "phone", "social"],
        "cron": {"day_of_week": "mon", "hour": 10, "minute": 0},
    },
    {
        "deporte": "surf",
        "locacion": "Australia",
        "pipelines": ["web", "email", "phone", "social"],
        "cron": {"day_of_week": "tue", "hour": 8, "minute": 0},
    },
    {
        "deporte": "surf",
        "locacion": "Morocco",
        "pipelines": ["web", "email", "phone", "social"],
        "cron": {"day_of_week": "tue", "hour": 9, "minute": 0},
    },

    # Yoga retreats — búsqueda semanal (miércoles)
    {
        "deporte": "yoga",
        "locacion": "Bali",
        "pipelines": ["trips"],
        "cron": {"day_of_week": "wed", "hour": 8, "minute": 0},
    },
    {
        "deporte": "yoga",
        "locacion": "Costa Rica",
        "pipelines": ["trips"],
        "cron": {"day_of_week": "wed", "hour": 9, "minute": 0},
    },

    # Kitesurf — búsqueda quincenal (primer y tercer viernes)
    {
        "deporte": "kitesurf",
        "locacion": "Tarifa",
        "pipelines": ["web", "email", "social"],
        "cron": {"day_of_week": "fri", "hour": 8, "minute": 0},
    },
]


def ejecutar_tarea(deporte: str, locacion: str, pipelines: list,
                   tipo_negocio: str = None):
    """
    Ejecuta una tarea programada: corre los pipelines indicados en orden.
    """
    logger.info(f"=== Tarea programada: {deporte} en {locacion} | Pipelines: {pipelines} ===")

    try:
        if "web" in pipelines:
            from scrapers.web_scraper import WebScraper
            WebScraper().run(deporte, locacion, tipo_negocio=tipo_negocio)

        if "email" in pipelines:
            from scrapers.email_scraper import EmailScraper
            EmailScraper().run(deporte, locacion)

        if "phone" in pipelines:
            from scrapers.phone_scraper import PhoneScraper
            PhoneScraper().run(deporte, locacion)

        if "social" in pipelines:
            from scrapers.social_scraper import SocialScraper
            SocialScraper().run(deporte, locacion)

        if "trips" in pipelines:
            from scrapers.trips_scraper import TripsScraper
            TripsScraper().run(deporte, locacion)

        logger.info(f"=== Tarea completada: {deporte} en {locacion} ===")

    except Exception as e:
        logger.error(f"Error en tarea {deporte}/{locacion}: {e}", exc_info=True)


def ejecutar_todo_una_vez():
    """Ejecuta todas las tareas programadas una sola vez (modo --once)."""
    logger.info("Ejecutando todas las tareas una vez...")
    for tarea in TAREAS_PROGRAMADAS:
        ejecutar_tarea(
            deporte=tarea["deporte"],
            locacion=tarea["locacion"],
            pipelines=tarea["pipelines"],
            tipo_negocio=tarea.get("tipo_negocio"),
        )
    logger.info("Todas las tareas ejecutadas.")


def iniciar_scheduler():
    """Inicia el scheduler con las tareas programadas."""
    scheduler = BlockingScheduler()

    for i, tarea in enumerate(TAREAS_PROGRAMADAS):
        job_id = f"{tarea['deporte']}_{tarea['locacion']}_{i}".replace(" ", "_").lower()

        scheduler.add_job(
            ejecutar_tarea,
            trigger=CronTrigger(**tarea["cron"]),
            id=job_id,
            kwargs={
                "deporte": tarea["deporte"],
                "locacion": tarea["locacion"],
                "pipelines": tarea["pipelines"],
                "tipo_negocio": tarea.get("tipo_negocio"),
            },
            name=f"{tarea['deporte']} en {tarea['locacion']}",
            misfire_grace_time=3600,  # 1 hora de gracia si se pierde la ejecución
        )
        logger.info(f"Tarea programada: {job_id} -> cron {tarea['cron']}")

    # Manejar cierre limpio con Ctrl+C
    def shutdown(signum, frame):
        logger.info("Apagando scheduler...")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(f"Scheduler iniciado con {len(TAREAS_PROGRAMADAS)} tareas. Ctrl+C para detener.")

    # Mostrar próximas ejecuciones
    print("\nPróximas ejecuciones programadas:")
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        if next_run:
            print(f"  {job.name}: {next_run:%Y-%m-%d %H:%M}")
    print()

    scheduler.start()


if __name__ == "__main__":
    init_db()

    if "--once" in sys.argv:
        ejecutar_todo_una_vez()
    else:
        iniciar_scheduler()
