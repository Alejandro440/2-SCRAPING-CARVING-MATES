"""
Entry point principal del sistema de scraping.
Inicializa la base de datos y orquesta los pipelines.

Uso:
    python main.py                              → Muestra ayuda
    python main.py buscar surf Bali             → Pipeline completo: web + contacto
    python main.py buscar surf Bali --tipo escuela
    python main.py emails surf Bali             → Solo extraer emails
    python main.py telefonos surf Bali          → Solo extraer teléfonos
    python main.py redes surf Bali              → Solo extraer redes sociales
    python main.py trips yoga "Costa Rica"      → Buscar trips/retreats
    python main.py exportar surf Bali           → Exportar resultados a CSV
    python main.py stats                        → Mostrar estadísticas

    -- Contacto automatizado --
    python main.py contactar surf Bali          → Enviar emails a negocios pendientes
    python main.py contactar surf Bali --dry    → Simular sin enviar
    python main.py contactar surf Bali --template retreat_inicial
    python main.py followup                     → Enviar follow-up (7 días sin respuesta)
    python main.py whatsapp surf Bali           → Enviar WhatsApp a negocios
    python main.py whatsapp surf Bali --dry     → Simular sin enviar
    python main.py respuesta <negocio_id> interesado  → Marcar respuesta de un negocio
"""

import sys
import csv
from pathlib import Path
from datetime import datetime

# Asegurar que el directorio raíz esté en el path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.connection import init_db, get_session
from database.models import Negocio, LogScraping
from config.settings import EXPORTS_DIR
from utils.logger import get_logger

logger = get_logger("main")


def buscar(deporte: str, locacion: str, tipo_negocio: str = None,
           max_resultados: int = 50, idioma: str = "en"):
    """
    Pipeline completo: busca negocios y luego extrae contacto.
    Ejecuta Pipeline 1 (web) → Pipeline 2 (emails) → Pipeline 3 (teléfonos) → Pipeline 4 (redes).
    """
    from scrapers.web_scraper import WebScraper
    from scrapers.email_scraper import EmailScraper
    from scrapers.phone_scraper import PhoneScraper
    from scrapers.social_scraper import SocialScraper

    logger.info(f"=== Búsqueda completa: {deporte} en {locacion} ===")

    # 1. Buscar negocios en la web
    web = WebScraper()
    resultados = web.run(deporte, locacion, tipo_negocio=tipo_negocio,
                         max_resultados=max_resultados, idioma=idioma)
    logger.info(f"Negocios encontrados: {len(resultados)}")

    # 2. Extraer emails
    email_scraper = EmailScraper()
    emails = email_scraper.run(deporte, locacion)
    logger.info(f"Negocios con emails: {len(emails)}")

    # 3. Extraer teléfonos
    phone_scraper = PhoneScraper()
    telefonos = phone_scraper.run(deporte, locacion)
    logger.info(f"Negocios con teléfonos: {len(telefonos)}")

    # 4. Extraer redes sociales
    social_scraper = SocialScraper()
    redes = social_scraper.run(deporte, locacion)
    logger.info(f"Negocios con redes: {len(redes)}")

    logger.info("=== Búsqueda completa finalizada ===")
    return resultados


def buscar_trips(deporte: str, locacion: str, max_resultados: int = 30):
    """Pipeline específico para trips y retreats."""
    from scrapers.trips_scraper import TripsScraper

    logger.info(f"=== Búsqueda de trips: {deporte} en {locacion} ===")
    trips = TripsScraper()
    resultados = trips.run(deporte, locacion, max_resultados=max_resultados)
    logger.info(f"Trips encontrados: {len(resultados)}")
    return resultados


def extraer_emails(deporte: str, locacion: str):
    """Ejecuta solo el Pipeline 2 (emails)."""
    from scrapers.email_scraper import EmailScraper
    return EmailScraper().run(deporte, locacion)


def extraer_telefonos(deporte: str, locacion: str):
    """Ejecuta solo el Pipeline 3 (teléfonos)."""
    from scrapers.phone_scraper import PhoneScraper
    return PhoneScraper().run(deporte, locacion)


def extraer_redes(deporte: str, locacion: str):
    """Ejecuta solo el Pipeline 4 (redes sociales)."""
    from scrapers.social_scraper import SocialScraper
    return SocialScraper().run(deporte, locacion)


def exportar_csv(deporte: str = None, locacion: str = None):
    """Exporta los negocios de la base de datos a un archivo CSV."""
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

        if not negocios:
            logger.warning("No hay negocios para exportar con esos filtros.")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filtro = f"_{deporte}" if deporte else ""
        filtro += f"_{locacion}" if locacion else ""
        filename = f"export{filtro}_{timestamp}.csv"
        filepath = EXPORTS_DIR / filename

        campos = [
            "nombre", "tipo_negocio", "deporte", "pais", "region", "ciudad",
            "website", "emails", "telefonos", "instagram", "facebook",
            "rating", "reviews_count", "precio_referencia", "fuente",
            "contactado", "respuesta",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()

            for n in negocios:
                redes = n.redes_sociales or {}
                writer.writerow({
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
                })

        logger.info(f"Exportados {len(negocios)} negocios a: {filepath}")
        return filepath


def mostrar_stats():
    """Muestra estadísticas generales de la base de datos."""
    with get_session() as session:
        total = session.query(Negocio).count()
        con_email = session.query(Negocio).filter(
            Negocio.emails.isnot(None), Negocio.emails != "[]"
        ).count()
        con_telefono = session.query(Negocio).filter(
            Negocio.telefonos.isnot(None), Negocio.telefonos != "[]"
        ).count()
        contactados = session.query(Negocio).filter(Negocio.contactado == True).count()  # noqa: E712

        # Por deporte
        from sqlalchemy import func
        por_deporte = session.query(
            Negocio.deporte, func.count(Negocio.id)
        ).group_by(Negocio.deporte).all()

        # Por tipo
        por_tipo = session.query(
            Negocio.tipo_negocio, func.count(Negocio.id)
        ).group_by(Negocio.tipo_negocio).all()

        # Logs recientes
        logs_recientes = session.query(LogScraping).order_by(
            LogScraping.fecha.desc()
        ).limit(5).all()

    print("\n=== ESTADÍSTICAS DEL SISTEMA ===\n")
    print(f"  Total negocios:     {total}")
    print(f"  Con email:          {con_email}")
    print(f"  Con teléfono:       {con_telefono}")
    print(f"  Contactados:        {contactados}")

    if por_deporte:
        print("\n  Por deporte:")
        for deporte, count in por_deporte:
            print(f"    {deporte}: {count}")

    if por_tipo:
        print("\n  Por tipo:")
        for tipo, count in por_tipo:
            print(f"    {tipo}: {count}")

    if logs_recientes:
        print("\n  Últimas ejecuciones:")
        for log in logs_recientes:
            print(
                f"    [{log.fecha:%Y-%m-%d %H:%M}] {log.pipeline} | "
                f"{log.deporte}/{log.locacion} | "
                f"{log.resultados_nuevos} nuevos, {log.errores} errores"
            )

    print()


def contactar_negocios(deporte: str = None, locacion: str = None,
                       tipo_negocio: str = None, template: str = "escuela_inicial",
                       max_envios: int = 50, dry_run: bool = False):
    """Envía emails a negocios pendientes de contacto."""
    from automation.email_sender import EmailSender

    logger.info(f"=== Contacto por email {'(DRY RUN)' if dry_run else ''} ===")
    sender = EmailSender()
    resultado = sender.enviar_a_negocios(
        deporte=deporte,
        locacion=locacion,
        tipo_negocio=tipo_negocio,
        template=template,
        max_envios=max_envios,
        dry_run=dry_run,
    )
    return resultado


def enviar_followup(dias: int = 7, max_envios: int = 30, dry_run: bool = False):
    """Envía follow-up a negocios sin respuesta."""
    from automation.email_sender import EmailSender

    logger.info(f"=== Follow-up (>{dias} días sin respuesta) {'(DRY RUN)' if dry_run else ''} ===")
    sender = EmailSender()
    return sender.enviar_followup(
        dias_desde_contacto=dias,
        max_envios=max_envios,
        dry_run=dry_run,
    )


def enviar_whatsapp(deporte: str = None, locacion: str = None,
                    max_envios: int = 20, dry_run: bool = False):
    """Envía mensajes de WhatsApp a negocios con teléfono."""
    from automation.whatsapp_sender import WhatsAppSender

    logger.info(f"=== WhatsApp {'(DRY RUN)' if dry_run else ''} ===")
    sender = WhatsAppSender()
    return sender.enviar_a_negocios(
        deporte=deporte,
        locacion=locacion,
        max_envios=max_envios,
        dry_run=dry_run,
    )


def marcar_respuesta(negocio_id: str, respuesta: str):
    """Marca la respuesta de un negocio: interesado | no_interesado | sin_respuesta."""
    respuestas_validas = ["interesado", "no_interesado", "sin_respuesta"]
    if respuesta not in respuestas_validas:
        logger.error(f"Respuesta inválida. Opciones: {respuestas_validas}")
        return

    with get_session() as session:
        negocio = session.query(Negocio).filter_by(id=negocio_id).first()
        if not negocio:
            logger.error(f"Negocio no encontrado: {negocio_id}")
            return
        negocio.respuesta = respuesta
        logger.info(f"Respuesta de '{negocio.nombre}' marcada como: {respuesta}")


def mostrar_ayuda():
    """Muestra el uso del sistema."""
    print(__doc__)


def main():
    """Punto de entrada principal desde línea de comandos."""
    init_db()

    args = sys.argv[1:]

    if not args:
        mostrar_ayuda()
        return

    comando = args[0].lower()
    dry_run = "--dry" in args

    if comando == "buscar" and len(args) >= 3:
        deporte, locacion = args[1], args[2]
        tipo = None
        for i, arg in enumerate(args):
            if arg == "--tipo" and i + 1 < len(args):
                tipo = args[i + 1]
        buscar(deporte, locacion, tipo_negocio=tipo)

    elif comando == "trips" and len(args) >= 3:
        buscar_trips(args[1], args[2])

    elif comando == "emails" and len(args) >= 3:
        extraer_emails(args[1], args[2])

    elif comando == "telefonos" and len(args) >= 3:
        extraer_telefonos(args[1], args[2])

    elif comando == "redes" and len(args) >= 3:
        extraer_redes(args[1], args[2])

    elif comando == "contactar" and len(args) >= 3:
        deporte, locacion = args[1], args[2]
        template = "escuela_inicial"
        for i, arg in enumerate(args):
            if arg == "--template" and i + 1 < len(args):
                template = args[i + 1]
        contactar_negocios(deporte, locacion, template=template, dry_run=dry_run)

    elif comando == "followup":
        enviar_followup(dry_run=dry_run)

    elif comando == "whatsapp" and len(args) >= 3:
        enviar_whatsapp(args[1], args[2], dry_run=dry_run)

    elif comando == "respuesta" and len(args) >= 3:
        marcar_respuesta(args[1], args[2])

    elif comando == "exportar":
        deporte = args[1] if len(args) > 1 else None
        locacion = args[2] if len(args) > 2 else None
        exportar_csv(deporte, locacion)

    elif comando == "stats":
        mostrar_stats()

    else:
        mostrar_ayuda()


if __name__ == "__main__":
    main()
