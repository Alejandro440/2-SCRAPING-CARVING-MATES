"""
Tests para el sistema de contacto automatizado.
Ejecutar con: pytest tests/test_automation.py -v
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Negocio


def get_test_session():
    """Crea una DB en memoria para tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestEmailSender:
    def test_renderizar_template(self):
        from automation.email_sender import EmailSender

        sender = EmailSender(metodo="smtp")
        negocio = Negocio(
            nombre="Bali Surf School",
            tipo_negocio="escuela",
            deporte="surf",
            pais="Indonesia",
            ciudad="Canggu",
            website="https://balisurfschool.com",
        )

        asunto, cuerpo = sender._renderizar_template("escuela_inicial", negocio)

        assert "Bali Surf School" in asunto
        assert "Carving Mates" in asunto
        assert "Bali Surf School" in cuerpo
        assert "surf" in cuerpo

    def test_renderizar_template_retreat(self):
        from automation.email_sender import EmailSender

        sender = EmailSender(metodo="smtp")
        negocio = Negocio(
            nombre="Yoga Paradise Retreat",
            tipo_negocio="retreat",
            deporte="yoga",
            pais="Costa Rica",
        )

        asunto, cuerpo = sender._renderizar_template("retreat_inicial", negocio)

        assert "Yoga Paradise Retreat" in asunto
        assert "Yoga Paradise Retreat" in cuerpo
        assert "yoga" in cuerpo

    def test_renderizar_followup(self):
        from automation.email_sender import EmailSender

        sender = EmailSender(metodo="smtp")
        negocio = Negocio(
            nombre="Wave Riders",
            tipo_negocio="escuela",
            deporte="surf",
        )

        asunto, cuerpo = sender._renderizar_template("followup", negocio)

        assert "follow-up" in asunto.lower()
        assert "Wave Riders" in cuerpo

    def test_sin_credenciales(self):
        from automation.email_sender import EmailSender

        with patch("automation.email_sender.SENDGRID_API_KEY", ""), \
             patch("automation.email_sender.SMTP_USER", ""), \
             patch("automation.email_sender.SMTP_PASSWORD", ""):
            sender = EmailSender(metodo="auto")
            assert sender.metodo is None

    def test_dry_run_no_envia(self):
        from automation.email_sender import EmailSender

        sender = EmailSender(metodo="smtp")

        # Crear negocio mock
        negocio_mock = MagicMock()
        negocio_mock.id = "test-123"
        negocio_mock.nombre = "Test School"
        negocio_mock.emails = ["test@school.com"]
        negocio_mock.tipo_negocio = "escuela"
        negocio_mock.deporte = "surf"
        negocio_mock.pais = "Spain"
        negocio_mock.ciudad = "Barcelona"
        negocio_mock.website = "https://test.com"

        with patch.object(sender, '_obtener_negocios_pendientes', return_value=[negocio_mock]), \
             patch.object(sender, '_enviar_email') as mock_enviar:
            resultado = sender.enviar_a_negocios(dry_run=True)

            # En dry_run no debe llamar a _enviar_email
            mock_enviar.assert_not_called()
            assert resultado["enviados"] == 1


class TestWhatsAppSender:
    def test_generar_mensaje(self):
        from automation.whatsapp_sender import WhatsAppSender

        with patch("automation.whatsapp_sender.TWILIO_ACCOUNT_SID", ""), \
             patch("automation.whatsapp_sender.TWILIO_AUTH_TOKEN", ""):
            sender = WhatsAppSender()

        negocio = Negocio(
            nombre="Beach Surf School",
            deporte="surf",
            pais="Portugal",
            tipo_negocio="escuela",
        )

        mensaje = sender._generar_mensaje(negocio)

        assert "Beach Surf School" in mensaje
        assert "surf" in mensaje
        assert "Portugal" in mensaje
        assert "Carving Mates" in mensaje

    def test_sin_twilio_config(self):
        from automation.whatsapp_sender import WhatsAppSender

        with patch("automation.whatsapp_sender.TWILIO_ACCOUNT_SID", ""), \
             patch("automation.whatsapp_sender.TWILIO_AUTH_TOKEN", ""):
            sender = WhatsAppSender()
            assert sender.client is None


class TestTemplates:
    """Verifica que todos los templates existan y tengan la estructura correcta."""

    def test_templates_existen(self):
        templates_dir = Path(__file__).parent.parent / "automation" / "templates"
        assert (templates_dir / "escuela_inicial.html").exists()
        assert (templates_dir / "retreat_inicial.html").exists()
        assert (templates_dir / "followup.html").exists()

    def test_templates_tienen_subject(self):
        templates_dir = Path(__file__).parent.parent / "automation" / "templates"

        for template_file in templates_dir.glob("*.html"):
            contenido = template_file.read_text()
            assert contenido.startswith("<!-- SUBJECT:"), \
                f"Template {template_file.name} no tiene línea SUBJECT"

    def test_templates_tienen_variables(self):
        templates_dir = Path(__file__).parent.parent / "automation" / "templates"

        for template_file in templates_dir.glob("*.html"):
            contenido = template_file.read_text()
            assert "{{nombre_negocio}}" in contenido, \
                f"Template {template_file.name} no usa {{{{nombre_negocio}}}}"

    def test_templates_tienen_unsubscribe(self):
        templates_dir = Path(__file__).parent.parent / "automation" / "templates"

        for template_file in templates_dir.glob("*.html"):
            contenido = template_file.read_text().lower()
            assert "unsubscribe" in contenido, \
                f"Template {template_file.name} no tiene link de unsubscribe"
