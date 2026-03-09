"""
API endpoints del sistema de scraping.
"""

import csv
import io
from functools import wraps
from datetime import datetime

from flask import Blueprint, request, jsonify

from config.settings import API_KEY_ENABLED, API_KEY
from app.services.scraping_service import ScrapingService
from database.connection import get_session
from database.models import Negocio, LogScraping

api_bp = Blueprint("api", __name__)
scraping_service = ScrapingService()


# =========================================================================
# Middleware: API Key Authentication
# =========================================================================

def require_api_key(f):
    """Decorator que valida el header X-API-KEY si está habilitado."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not API_KEY_ENABLED:
            return f(*args, **kwargs)

        key = request.headers.get("X-API-KEY")
        if not key or key != API_KEY:
            return jsonify({
                "status": "error",
                "message": "API key inválida o faltante. Envía el header X-API-KEY.",
            }), 401

        return f(*args, **kwargs)
    return decorated


# =========================================================================
# Helpers
# =========================================================================

def error_response(message: str, status_code: int = 400) -> tuple:
    """Genera una respuesta de error JSON."""
    return jsonify({"status": "error", "message": message}), status_code


def validar_search_input(data: dict) -> str | None:
    """Valida los campos del request de búsqueda. Retorna mensaje de error o None."""
    if not data:
        return "El body debe ser JSON válido"

    if not data.get("deporte"):
        return "El campo 'deporte' es obligatorio"

    if not data.get("locacion"):
        return "El campo 'locacion' es obligatorio"

    if "max_resultados" in data:
        try:
            val = int(data["max_resultados"])
            if val < 1 or val > 200:
                return "max_resultados debe ser un entero entre 1 y 200"
        except (ValueError, TypeError):
            return "max_resultados debe ser un entero válido"

    return None


# =========================================================================
# Endpoints
# =========================================================================

@api_bp.route("/scraping/search", methods=["POST"])
@require_api_key
def search():
    """
    Busqueda principal multi-fuente (Google + DuckDuckGo + directorios).
    Solo busca negocios. No ejecuta enriquecimiento (emails/phones/social).
    Responde en ~20-40 segundos.

    Body JSON:
        deporte (str, obligatorio): "surf", "yoga", "kitesurf", etc.
        locacion (str, obligatorio): "Bali", "Costa Rica", "Portugal", etc.
        tipo_negocio (str, opcional): "escuela", "camp", "retreat", etc.
        max_resultados (int, opcional): maximo de resultados (default 50)
        idioma (str, opcional): idioma de busqueda (default "en")

    Returns:
        JSON con status, summary y resultados.
    """
    data = request.get_json(silent=True) or {}

    # Validar input
    error = validar_search_input(data)
    if error:
        return error_response(error)

    deporte = data["deporte"].strip().lower()
    locacion = data["locacion"].strip()
    tipo_negocio = data.get("tipo_negocio")
    max_resultados = int(data.get("max_resultados", 50))
    idioma = data.get("idioma", "en")

    try:
        resultado = scraping_service.buscar(
            deporte=deporte,
            locacion=locacion,
            tipo_negocio=tipo_negocio,
            max_resultados=max_resultados,
            idioma=idioma,
        )

        return jsonify({
            "status": "success",
            "message": "Busqueda completada correctamente",
            "input": {
                "deporte": deporte,
                "locacion": locacion,
                "tipo_negocio": tipo_negocio,
                "max_resultados": max_resultados,
                "idioma": idioma,
            },
            "summary": resultado["summary"],
            "resultados": resultado["resultados"],
        })

    except Exception as e:
        return error_response(f"Error interno: {str(e)}", 500)


@api_bp.route("/scraping/enrich", methods=["POST"])
@require_api_key
def enrich():
    """
    Enriquece negocios ya encontrados con emails, telefonos y redes sociales.
    Ejecuta los pipelines de email + phone + social sobre negocios en la DB.
    Proceso lento (~1-2 min). Llamar despues de /search.

    Body JSON:
        deporte (str, obligatorio)
        locacion (str, obligatorio)
        max_resultados (int, opcional, default 50)
    """
    data = request.get_json(silent=True) or {}

    error = validar_search_input(data)
    if error:
        return error_response(error)

    deporte = data["deporte"].strip().lower()
    locacion = data["locacion"].strip()
    max_resultados = int(data.get("max_resultados", 50))

    try:
        resultado = scraping_service.enriquecer(
            deporte=deporte,
            locacion=locacion,
            max_resultados=max_resultados,
        )

        return jsonify({
            "status": "success",
            "message": "Enriquecimiento completado",
            "input": {
                "deporte": deporte,
                "locacion": locacion,
                "max_resultados": max_resultados,
            },
            "summary": resultado["summary"],
            "resultados": resultado["resultados"],
        })

    except Exception as e:
        return error_response(f"Error interno: {str(e)}", 500)


@api_bp.route("/scraping/trips", methods=["POST"])
@require_api_key
def search_trips():
    """
    Busca trips y retreats específicamente.

    Body JSON:
        deporte (str, obligatorio)
        locacion (str, obligatorio)
        max_resultados (int, opcional, default 30)
    """
    data = request.get_json(silent=True) or {}

    error = validar_search_input(data)
    if error:
        return error_response(error)

    deporte = data["deporte"].strip().lower()
    locacion = data["locacion"].strip()
    max_resultados = int(data.get("max_resultados", 30))

    try:
        resultado = scraping_service.buscar_trips(
            deporte=deporte,
            locacion=locacion,
            max_resultados=max_resultados,
        )

        return jsonify({
            "status": "success",
            "message": "Búsqueda de trips completada",
            "input": {
                "deporte": deporte,
                "locacion": locacion,
                "max_resultados": max_resultados,
            },
            "summary": resultado["summary"],
            "resultados": resultado["resultados"],
        })

    except Exception as e:
        return error_response(f"Error interno: {str(e)}", 500)


@api_bp.route("/scraping/export", methods=["POST"])
@require_api_key
def export():
    """
    Exporta negocios de la base de datos.

    Body JSON:
        deporte (str, opcional): filtrar por deporte
        locacion (str, opcional): filtrar por locación
        formato (str, opcional): "json" (default) o "csv"
    """
    data = request.get_json(silent=True) or {}
    deporte = data.get("deporte")
    locacion = data.get("locacion")
    formato = data.get("formato", "json").lower()

    if formato not in ("json", "csv"):
        return error_response("formato debe ser 'json' o 'csv'")

    try:
        negocios = scraping_service.exportar(deporte=deporte, locacion=locacion)

        if formato == "csv":
            output = io.StringIO()
            if negocios:
                writer = csv.DictWriter(output, fieldnames=negocios[0].keys())
                writer.writeheader()
                writer.writerows(negocios)

            from flask import Response
            return Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment; filename=export_{datetime.now():%Y%m%d_%H%M%S}.csv"},
            )

        return jsonify({
            "status": "success",
            "total": len(negocios),
            "resultados": negocios,
        })

    except Exception as e:
        return error_response(f"Error interno: {str(e)}", 500)


@api_bp.route("/stats", methods=["GET"])
@require_api_key
def stats():
    """Devuelve estadísticas de la base de datos."""
    try:
        with get_session() as session:
            from sqlalchemy import func

            total = session.query(Negocio).count()
            con_email = session.query(Negocio).filter(
                Negocio.emails.isnot(None), Negocio.emails != "[]"
            ).count()
            con_telefono = session.query(Negocio).filter(
                Negocio.telefonos.isnot(None), Negocio.telefonos != "[]"
            ).count()
            contactados = session.query(Negocio).filter(
                Negocio.contactado == True  # noqa: E712
            ).count()

            por_deporte = dict(
                session.query(Negocio.deporte, func.count(Negocio.id))
                .group_by(Negocio.deporte).all()
            )
            por_tipo = dict(
                session.query(Negocio.tipo_negocio, func.count(Negocio.id))
                .group_by(Negocio.tipo_negocio).all()
            )

            logs = session.query(LogScraping).order_by(
                LogScraping.fecha.desc()
            ).limit(10).all()
            logs_data = [
                {
                    "pipeline": l.pipeline,
                    "deporte": l.deporte,
                    "locacion": l.locacion,
                    "resultados_nuevos": l.resultados_nuevos,
                    "errores": l.errores,
                    "fecha": str(l.fecha),
                }
                for l in logs
            ]

        return jsonify({
            "status": "success",
            "stats": {
                "total_negocios": total,
                "con_email": con_email,
                "con_telefono": con_telefono,
                "contactados": contactados,
                "por_deporte": por_deporte,
                "por_tipo": por_tipo,
            },
            "ultimas_ejecuciones": logs_data,
        })

    except Exception as e:
        return error_response(f"Error interno: {str(e)}", 500)


@api_bp.route("/contact/email", methods=["POST"])
@require_api_key
def contact_email():
    """
    Envía emails a negocios pendientes.

    Body JSON:
        deporte (str, opcional)
        locacion (str, opcional)
        template (str, opcional, default "escuela_inicial")
        max_envios (int, opcional, default 50)
        dry_run (bool, opcional, default true)
    """
    data = request.get_json(silent=True) or {}

    try:
        resultado = scraping_service.contactar(
            deporte=data.get("deporte"),
            locacion=data.get("locacion"),
            template=data.get("template", "escuela_inicial"),
            max_envios=int(data.get("max_envios", 50)),
            dry_run=data.get("dry_run", True),
        )

        return jsonify({
            "status": "success",
            "message": "Contacto completado" + (" (dry run)" if data.get("dry_run", True) else ""),
            "resultado": resultado,
        })

    except Exception as e:
        return error_response(f"Error interno: {str(e)}", 500)
