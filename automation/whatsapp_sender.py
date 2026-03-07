"""
Sistema de envío de mensajes por WhatsApp Business API (vía Twilio).
Envía mensajes personalizados a negocios con número de teléfono.
"""

from datetime import datetime

from config.settings import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
from database.connection import get_session
from database.models import Negocio, LogContacto
from utils.logger import get_logger

logger = get_logger("whatsapp_sender")


class WhatsAppSender:
    """
    Envía mensajes de WhatsApp a negocios usando Twilio API.
    Requiere cuenta de Twilio con WhatsApp Business habilitado.
    """

    def __init__(self):
        self.client = None
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            try:
                from twilio.rest import Client
                self.client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                logger.info("Twilio client inicializado correctamente.")
            except Exception as e:
                logger.error(f"Error inicializando Twilio: {e}")
        else:
            logger.warning(
                "Twilio no configurado. Configura TWILIO_ACCOUNT_SID "
                "y TWILIO_AUTH_TOKEN en .env"
            )

        self._enviados = 0
        self._fallidos = 0

    def enviar_a_negocios(self, deporte: str = None, locacion: str = None,
                          tipo_negocio: str = None,
                          max_envios: int = 20, dry_run: bool = False) -> dict:
        """
        Envía mensajes de WhatsApp a negocios con teléfono que no fueron contactados.

        Args:
            deporte: Filtrar por deporte.
            locacion: Filtrar por locación.
            tipo_negocio: Filtrar por tipo.
            max_envios: Máximo de mensajes a enviar.
            dry_run: Si True, no envía realmente.

        Returns:
            Resumen con contadores.
        """
        if not self.client and not dry_run:
            logger.error("Twilio client no disponible.")
            return {"enviados": 0, "fallidos": 0, "total": 0}

        negocios = self._obtener_negocios_pendientes(deporte, locacion, tipo_negocio)
        total = len(negocios)
        logger.info(f"Negocios pendientes para WhatsApp: {total}")

        self._enviados = 0
        self._fallidos = 0

        for negocio in negocios[:max_envios]:
            telefonos = negocio.telefonos or []
            if not telefonos:
                continue

            telefono = telefonos[0]
            mensaje = self._generar_mensaje(negocio)

            if dry_run:
                logger.info(f"[DRY RUN] WhatsApp a: {telefono} ({negocio.nombre})")
                self._enviados += 1
                continue

            exito = self._enviar_whatsapp(telefono, mensaje)
            self._registrar_envio(
                negocio_id=negocio.id,
                telefono=telefono,
                exito=exito,
            )

            if exito:
                self._marcar_contactado(negocio.id, "whatsapp")
                self._enviados += 1
            else:
                self._fallidos += 1

        return {"enviados": self._enviados, "fallidos": self._fallidos, "total": total}

    def _obtener_negocios_pendientes(self, deporte: str = None,
                                     locacion: str = None,
                                     tipo_negocio: str = None) -> list:
        """Obtiene negocios con teléfono no contactados (o contactados solo por email)."""
        with get_session() as session:
            query = session.query(Negocio).filter(
                Negocio.telefonos.isnot(None),
                Negocio.telefonos != "[]",
            )

            # No enviar WhatsApp si ya se envió WhatsApp
            query = query.filter(
                (Negocio.metodo_contacto != "whatsapp") &
                (Negocio.metodo_contacto != "ambos")
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

            return query.all()

    def _generar_mensaje(self, negocio: Negocio) -> str:
        """
        Genera un mensaje personalizado para WhatsApp.
        WhatsApp tiene límite de caracteres, así que es conciso.
        """
        nombre = negocio.nombre or "there"
        deporte = negocio.deporte or "sports"
        pais = negocio.pais or ""

        mensaje = (
            f"Hi {nombre}! 👋\n\n"
            f"We're Carving Mates, a platform connecting {deporte} enthusiasts "
            f"with the best schools and experiences worldwide.\n\n"
            f"We'd love to feature your business on our app and help you reach "
            f"more students and travelers"
        )

        if pais:
            mensaje += f" visiting {pais}"

        mensaje += (
            f".\n\n"
            f"Would you be interested in learning more? It's free to join! 🏄‍♂️\n\n"
            f"Best,\nThe Carving Mates Team\n"
            f"www.carvingmates.com"
        )

        return mensaje

    def _enviar_whatsapp(self, telefono: str, mensaje: str) -> bool:
        """Envía un mensaje de WhatsApp vía Twilio."""
        try:
            # Formatear número para WhatsApp
            whatsapp_to = f"whatsapp:{telefono}"

            message = self.client.messages.create(
                body=mensaje,
                from_=TWILIO_WHATSAPP_FROM,
                to=whatsapp_to,
            )

            logger.info(f"WhatsApp enviado a {telefono}: SID={message.sid}")
            return True

        except Exception as e:
            logger.error(f"Error enviando WhatsApp a {telefono}: {e}")
            return False

    def _registrar_envio(self, negocio_id: str, telefono: str, exito: bool):
        """Registra el envío en la tabla de logs."""
        with get_session() as session:
            log = LogContacto(
                negocio_id=negocio_id,
                metodo="whatsapp",
                destinatario=telefono,
                template_usado="whatsapp_default",
                estado="enviado" if exito else "fallido",
            )
            session.add(log)

    def _marcar_contactado(self, negocio_id: str, metodo: str):
        """Marca el negocio como contactado por WhatsApp."""
        with get_session() as session:
            negocio = session.query(Negocio).filter_by(id=negocio_id).first()
            if negocio:
                if negocio.contactado and negocio.metodo_contacto == "email":
                    negocio.metodo_contacto = "ambos"
                else:
                    negocio.contactado = True
                    negocio.metodo_contacto = "whatsapp"
                    negocio.respuesta = "sin_respuesta"
                negocio.fecha_contacto = datetime.utcnow()
