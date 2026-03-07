"""
Tests para las funciones de validación y normalización.
Ejecutar con: pytest tests/test_validators.py -v
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.validators import (
    validar_email, normalizar_email,
    validar_telefono, normalizar_telefono,
    validar_url, normalizar_url,
    extraer_dominio,
    extraer_emails_de_texto,
    extraer_telefonos_de_texto,
    extraer_redes_sociales,
)


# === Tests de Email ===

class TestValidarEmail:
    def test_email_valido(self):
        assert validar_email("info@surfschool.com") is True
        assert validar_email("contact@yoga-retreat.co.uk") is True

    def test_email_invalido(self):
        assert validar_email("no-es-email") is False
        assert validar_email("@dominio.com") is False
        assert validar_email("") is False
        assert validar_email(None) is False

    def test_email_excluido(self):
        assert validar_email("noreply@surfschool.com") is False
        assert validar_email("test@example.com") is False

    def test_email_archivo(self):
        assert validar_email("logo@2x.png") is False

    def test_normalizar(self):
        assert normalizar_email("  Info@SurfSchool.COM  ") == "info@surfschool.com"


class TestExtraerEmails:
    def test_extraer_de_texto(self):
        texto = "Contáctanos en info@surf.com o ventas@surf.com para más info"
        emails = extraer_emails_de_texto(texto)
        assert "info@surf.com" in emails
        assert "ventas@surf.com" in emails

    def test_sin_emails(self):
        assert extraer_emails_de_texto("No hay emails aquí") == []
        assert extraer_emails_de_texto("") == []
        assert extraer_emails_de_texto(None) == []

    def test_deduplicacion(self):
        texto = "info@surf.com y otra vez info@surf.com"
        assert len(extraer_emails_de_texto(texto)) == 1


# === Tests de Teléfono ===

class TestValidarTelefono:
    def test_telefono_internacional(self):
        assert validar_telefono("+34612345678") is True
        assert validar_telefono("+1 212 555 1234") is True

    def test_telefono_invalido(self):
        assert validar_telefono("123") is False
        assert validar_telefono("") is False
        assert validar_telefono(None) is False

    def test_normalizar(self):
        resultado = normalizar_telefono("+34 612 345 678")
        assert resultado == "+34612345678"

    def test_normalizar_invalido(self):
        assert normalizar_telefono("no-es-telefono") is None


class TestExtraerTelefonos:
    def test_extraer_de_texto(self):
        texto = "Llámanos al +34 612 345 678 o al +1 555 123 4567"
        telefonos = extraer_telefonos_de_texto(texto)
        assert len(telefonos) >= 1  # phonenumbers puede variar según contexto


# === Tests de URL ===

class TestValidarUrl:
    def test_url_valida(self):
        assert validar_url("https://www.surfschool.com") is True
        assert validar_url("http://example.org/page") is True

    def test_url_invalida(self):
        assert validar_url("no-es-url") is False
        assert validar_url("ftp://algo.com") is False
        assert validar_url("") is False
        assert validar_url(None) is False

    def test_normalizar(self):
        assert normalizar_url("surfschool.com") == "https://surfschool.com"
        assert normalizar_url("https://surfschool.com/").endswith(".com/")

    def test_extraer_dominio(self):
        assert extraer_dominio("https://www.surfschool.com/about") == "surfschool.com"
        assert extraer_dominio("http://yoga-retreat.co.uk") == "yoga-retreat.co.uk"
        assert extraer_dominio(None) is None


# === Tests de Redes Sociales ===

class TestExtraerRedesSociales:
    def test_extraer_instagram(self):
        html = '<a href="https://www.instagram.com/surfschool">IG</a>'
        redes = extraer_redes_sociales(html)
        assert redes["instagram"] == "https://www.instagram.com/surfschool"

    def test_extraer_facebook(self):
        html = '<a href="https://facebook.com/mysurfcamp">FB</a>'
        redes = extraer_redes_sociales(html)
        assert redes["facebook"] == "https://facebook.com/mysurfcamp"

    def test_sin_redes(self):
        redes = extraer_redes_sociales("No hay links aquí")
        assert all(v is None for v in redes.values())

    def test_multiples_redes(self):
        html = """
        <a href="https://instagram.com/surf">IG</a>
        <a href="https://www.facebook.com/surf">FB</a>
        <a href="https://tiktok.com/@surf">TK</a>
        """
        redes = extraer_redes_sociales(html)
        assert redes["instagram"] is not None
        assert redes["facebook"] is not None
        assert redes["tiktok"] is not None
