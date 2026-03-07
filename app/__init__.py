"""
Flask application factory.
"""

from flask import Flask
from database.connection import init_db
from app.api.routes import api_bp


def create_app():
    """Crea y configura la aplicación Flask."""
    app = Flask(__name__)

    # Inicializar base de datos
    init_db()

    # Registrar blueprints
    app.register_blueprint(api_bp, url_prefix="/api")

    # Health check en la raíz
    @app.route("/")
    def health():
        return {"status": "ok", "service": "Surf Scraper API"}

    return app
