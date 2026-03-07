"""
Sistema de envío de emails automatizado.
Soporta SMTP directo y SendGrid API.
Incluye personalización por template, rate limiting y tracking.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime

from config.settings import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    EMAIL_FROM_NAME, EMAIL_FROM_ADDRESS, SENDGRID_API_KEY,
)
from database.connection import get_session
from database.models import Negocio, LogContacto
from utils.logger import get_logger

logger = get_logger("email_sender")

TEMPLATES_DIR = Path(__file__).parent / "templates"


class EmailSender:
    """
    Envía emails personalizados a los negocios recolectados.
    Soporta SMTP (Gmail, etc.) y SendGrid API como fallback.
    """

    def __init__(self, metodo: str = "auto"):
        """
        Args:
            metodo: "smtp", "sendgrid", o "auto" (detecta según config disponible).
        """
        if metodo == "auto":
            if SENDGRID_API_KEY:
                self.metodo = "sendgrid"
            elif SMTP_USER and SMTP_PASSWORD:
                self.metodo = "smtp"
            else:
                self.metodo = None
                logger.warning(
                    "No hay credenciales de email configuradas. "
                    "Configura SMTP o SendGrid en .env"
                )
        else:
            self.metodo = metodo

        self._templates_cache: dict[str, str] = {}
        self._enviados = 0
        self._fallidos = 0

    def enviar_a_negocios(self, deporte: str = None, locacion: str = None,
                          tipo_negocio: str = None, template: str = "escuela_inicial",
                          max_envios: int = 50, dry_run: bool = False) -> dict:
        """
        Envía emails a negocios que tienen email y no han sido contactados.

        Args:
            deporte: Filtrar por deporte.
            locacion: Filtrar por locación.
            tipo_negocio: Filtrar por tipo de negocio.
            template: Nombre del template a usar.
            max_envios: Máximo de emails a enviar en esta ejecución.
            dry_run: Si True, no envía realmente (solo muestra qué enviaría).

        Returns:
            Resumen con contadores de enviados, fallidos y total.
        """
        if not self.metodo and not dry_run:
            logger.error("No hay método de envío configurado. Configura SMTP o SendGrid en .env")
            return {"enviados": 0, "fallidos": 0, "total": 0}

        negocios = self._obtener_negocios_pendientes(deporte, locacion, tipo_negocio)
        total = len(negocios)
        logger.info(f"Negocios pendientes de contacto: {total}")

        if not negocios:
            logger.info("No hay negocios pendientes para contactar.")
            return {"enviados": 0, "fallidos": 0, "total": 0}

        self._enviados = 0
        self._fallidos = 0

        for negocio in negocios[:max_envios]:
            emails = negocio.emails or []
            if not emails:
                continue

            email_destino = emails[0]  # Usar el primer email
            asunto, cuerpo = self._renderizar_template(template, negocio)

            if dry_run:
                logger.info(f"[DRY RUN] Enviaría a: {email_destino} ({negocio.nombre})")
                logger.debug(f"  Asunto: {asunto}")
                self._enviados += 1
                continue

            exito = self._enviar_email(email_destino, asunto, cuerpo)

            # Registrar en base de datos
            self._registrar_envio(
                negocio_id=negocio.id,
                email=email_destino,
                template=template,
                exito=exito,
            )

            if exito:
                self._marcar_contactado(negocio.id)
                self._enviados += 1
            else:
                self._fallidos += 1

        resumen = {
            "enviados": self._enviados,
            "fallidos": self._fallidos,
            "total": total,
        }
        logger.info(
            f"Envío completado: {self._enviados} enviados, "
            f"{self._fallidos} fallidos, {total} pendientes totales"
        )
        return resumen

    def enviar_followup(self, dias_desde_contacto: int = 7,
                        template: str = "followup",
                        max_envios: int = 30, dry_run: bool = False) -> dict:
        """
        Envía follow-up a negocios contactados que no respondieron.

        Args:
            dias_desde_contacto: Días mínimos desde el primer contacto.
            template: Template de follow-up a usar.
            max_envios: Máximo de follow-ups.
            dry_run: Modo simulación.

        Returns:
            Resumen del envío.
        """
        with get_session() as session:
            from sqlalchemy import func
            fecha_limite = datetime.utcnow().replace(
                day=datetime.utcnow().day - dias_desde_contacto
            )

            negocios = session.query(Negocio).filter(
                Negocio.contactado == True,  # noqa: E712
                Negocio.respuesta.in_([None, "sin_respuesta"]),
                Negocio.fecha_contacto <= fecha_limite,
                Negocio.emails.isnot(None),
                Negocio.emails != "[]",
            ).limit(max_envios).all()

            # Materializar antes de cerrar sesión
            negocios_data = [
                {
                    "id": n.id,
                    "nombre": n.nombre,
                    "email": (n.emails or [])[0] if n.emails else None,
                    "tipo_negocio": n.tipo_negocio,
                    "deporte": n.deporte,
                    "pais": n.pais,
                    "website": n.website,
                }
                for n in negocios if n.emails
            ]

        logger.info(f"Negocios para follow-up: {len(negocios_data)}")
        self._enviados = 0
        self._fallidos = 0

        for data in negocios_data:
            asunto, cuerpo = self._renderizar_template_dict(template, data)

            if dry_run:
                logger.info(f"[DRY RUN] Follow-up a: {data['email']} ({data['nombre']})")
                self._enviados += 1
                continue

            exito = self._enviar_email(data["email"], asunto, cuerpo)
            self._registrar_envio(
                negocio_id=data["id"],
                email=data["email"],
                template=template,
                exito=exito,
            )

            if exito:
                self._enviados += 1
            else:
                self._fallidos += 1

        return {"enviados": self._enviados, "fallidos": self._fallidos}

    def _obtener_negocios_pendientes(self, deporte: str = None,
                                     locacion: str = None,
                                     tipo_negocio: str = None) -> list:
        """Obtiene negocios con email que no han sido contactados."""
        with get_session() as session:
            query = session.query(Negocio).filter(
                Negocio.contactado == False,  # noqa: E712
                Negocio.emails.isnot(None),
                Negocio.emails != "[]",
            )

            if deporte:
                query = query.filter(Negocio.deporte == deporte)
            if locacion:
                query = query.filter(
                    (Negocio.pais.ilike(f"%{locacion}%")) |
                    (Negocio.region.ilike(f"%{locacion}%")) |
                    (Negocio.ciudad.ilike(f"%{locacion}%"))
                )
            if tipo_negocio:
                query = query.filter(Negocio.tipo_negocio == tipo_negocio)

            # Materializar resultados antes de cerrar sesión
            return query.all()

    def _renderizar_template(self, nombre_template: str, negocio: Negocio) -> tuple[str, str]:
        """
        Renderiza un template HTML reemplazando variables con datos del negocio.

        Returns:
            Tupla (asunto, cuerpo_html).
        """
        variables = {
            "nombre_negocio": negocio.nombre or "your business",
            "tipo_negocio": negocio.tipo_negocio or "business",
            "deporte": negocio.deporte or "sports",
            "pais": negocio.pais or "",
            "ciudad": negocio.ciudad or "",
            "website": negocio.website or "",
        }
        return self._renderizar(nombre_template, variables)

    def _renderizar_template_dict(self, nombre_template: str, datos: dict) -> tuple[str, str]:
        """Renderiza un template con datos de un diccionario."""
        variables = {
            "nombre_negocio": datos.get("nombre", "your business"),
            "tipo_negocio": datos.get("tipo_negocio", "business"),
            "deporte": datos.get("deporte", "sports"),
            "pais": datos.get("pais", ""),
            "ciudad": datos.get("ciudad", ""),
            "website": datos.get("website", ""),
        }
        return self._renderizar(nombre_template, variables)

    def _renderizar(self, nombre_template: str, variables: dict) -> tuple[str, str]:
        """Lee el template y reemplaza las variables."""
        # Cargar template (con cache)
        if nombre_template not in self._templates_cache:
            template_path = TEMPLATES_DIR / f"{nombre_template}.html"
            if not template_path.exists():
                logger.error(f"Template no encontrado: {template_path}")
                return ("Carving Mates - Partnership", "<p>Template not found</p>")
            self._templates_cache[nombre_template] = template_path.read_text(encoding="utf-8")

        html = self._templates_cache[nombre_template]

        # Extraer asunto del template (primera línea: <!-- SUBJECT: ... -->)
        asunto = "Carving Mates - Partnership Opportunity"
        if html.startswith("<!-- SUBJECT:"):
            linea_asunto = html.split("\n")[0]
            asunto = linea_asunto.replace("<!-- SUBJECT:", "").replace("-->", "").strip()
            # Reemplazar variables en el asunto también
            for key, value in variables.items():
                asunto = asunto.replace(f"{{{{{key}}}}}", value)

        # Reemplazar variables en el cuerpo
        for key, value in variables.items():
            html = html.replace(f"{{{{{key}}}}}", value)

        return asunto, html

    def _enviar_email(self, destinatario: str, asunto: str, cuerpo_html: str) -> bool:
        """Envía un email usando el método configurado."""
        if self.metodo == "smtp":
            return self._enviar_smtp(destinatario, asunto, cuerpo_html)
        elif self.metodo == "sendgrid":
            return self._enviar_sendgrid(destinatario, asunto, cuerpo_html)
        else:
            logger.error("No hay método de envío configurado")
            return False

    def _enviar_smtp(self, destinatario: str, asunto: str, cuerpo_html: str) -> bool:
        """Envía un email vía SMTP (Gmail, etc.)."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = asunto
            msg["From"] = f"{EMAIL_FROM_NAME} <{EMAIL_FROM_ADDRESS}>"
            msg["To"] = destinatario

            msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"Email enviado (SMTP) a: {destinatario}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("Error de autenticación SMTP. Verifica SMTP_USER y SMTP_PASSWORD en .env")
            return False
        except smtplib.SMTPRecipientsRefused:
            logger.warning(f"Email rechazado por el servidor: {destinatario}")
            return False
        except Exception as e:
            logger.error(f"Error enviando email SMTP a {destinatario}: {e}")
            return False

    def _enviar_sendgrid(self, destinatario: str, asunto: str, cuerpo_html: str) -> bool:
        """Envía un email vía SendGrid API."""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=(EMAIL_FROM_ADDRESS, EMAIL_FROM_NAME),
                to_emails=destinatario,
                subject=asunto,
                html_content=cuerpo_html,
            )

            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)

            if response.status_code in (200, 201, 202):
                logger.info(f"Email enviado (SendGrid) a: {destinatario}")
                return True
            else:
                logger.warning(f"SendGrid respondió {response.status_code} para {destinatario}")
                return False

        except Exception as e:
            logger.error(f"Error enviando email SendGrid a {destinatario}: {e}")
            return False

    def _registrar_envio(self, negocio_id: str, email: str,
                         template: str, exito: bool):
        """Registra el intento de envío en la tabla de logs."""
        with get_session() as session:
            log = LogContacto(
                negocio_id=negocio_id,
                metodo="email",
                destinatario=email,
                template_usado=template,
                estado="enviado" if exito else "fallido",
            )
            session.add(log)

    def _marcar_contactado(self, negocio_id: str):
        """Marca un negocio como contactado en la base de datos."""
        with get_session() as session:
            negocio = session.query(Negocio).filter_by(id=negocio_id).first()
            if negocio:
                negocio.contactado = True
                negocio.fecha_contacto = datetime.utcnow()
                negocio.metodo_contacto = "email"
                negocio.respuesta = "sin_respuesta"
