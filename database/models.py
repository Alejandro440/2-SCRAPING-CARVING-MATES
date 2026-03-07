"""
Modelos de datos SQLAlchemy.
Definen la estructura de las tablas para negocios, contactos y seguimiento.
"""

import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column, String, Float, Boolean, Date, DateTime,
    Integer, Text, JSON, Index
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Negocio(Base):
    """
    Modelo principal: representa un negocio (escuela, shop, retreat, etc.).
    Almacena toda la información recolectada por los distintos pipelines.
    """
    __tablename__ = "negocios"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # --- Información básica ---
    nombre = Column(String(255), nullable=False)
    tipo_negocio = Column(String(50), nullable=False)  # escuela | alquiler | retreat | trip | camp | shop
    deporte = Column(String(50), nullable=False)        # surf | snowboard | kitesurf | etc.
    deportes_secundarios = Column(JSON, default=list)   # ["yoga", "paddlesurf"]
    descripcion = Column(Text, nullable=True)

    # --- Ubicación ---
    pais = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    ciudad = Column(String(100), nullable=True)
    direccion = Column(String(500), nullable=True)
    latitud = Column(Float, nullable=True)
    longitud = Column(Float, nullable=True)

    # --- Contacto ---
    telefonos = Column(JSON, default=list)       # ["+34 612 345 678"]
    emails = Column(JSON, default=list)          # ["info@example.com"]
    website = Column(String(500), nullable=True)

    # --- Redes sociales ---
    redes_sociales = Column(JSON, default=dict)  # {"instagram": "url", "facebook": "url", ...}

    # --- Datos adicionales ---
    precio_referencia = Column(String(200), nullable=True)
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, nullable=True)

    # --- Metadata de scraping ---
    fuente = Column(String(100), nullable=True)        # google_maps | booksurfcamps | etc.
    fecha_scraping = Column(Date, default=date.today)

    # --- Tracking de contacto ---
    contactado = Column(Boolean, default=False)
    fecha_contacto = Column(DateTime, nullable=True)
    metodo_contacto = Column(String(50), nullable=True)  # email | whatsapp | ambos
    respuesta = Column(String(50), nullable=True)        # sin_respuesta | interesado | no_interesado
    notas_contacto = Column(Text, nullable=True)

    # --- Control ---
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Índices para búsquedas frecuentes
    __table_args__ = (
        Index("idx_deporte_locacion", "deporte", "pais", "region"),
        Index("idx_tipo_negocio", "tipo_negocio"),
        Index("idx_contactado", "contactado"),
        Index("idx_website", "website"),
    )

    def __repr__(self):
        return f"<Negocio(nombre='{self.nombre}', deporte='{self.deporte}', pais='{self.pais}')>"

    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario (útil para exports y APIs)."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "tipo_negocio": self.tipo_negocio,
            "deporte": self.deporte,
            "deportes_secundarios": self.deportes_secundarios or [],
            "descripcion": self.descripcion,
            "pais": self.pais,
            "region": self.region,
            "ciudad": self.ciudad,
            "direccion": self.direccion,
            "latitud": self.latitud,
            "longitud": self.longitud,
            "telefonos": self.telefonos or [],
            "emails": self.emails or [],
            "website": self.website,
            "redes_sociales": self.redes_sociales or {},
            "precio_referencia": self.precio_referencia,
            "rating": self.rating,
            "reviews_count": self.reviews_count,
            "fuente": self.fuente,
            "fecha_scraping": str(self.fecha_scraping) if self.fecha_scraping else None,
            "contactado": self.contactado,
            "fecha_contacto": str(self.fecha_contacto) if self.fecha_contacto else None,
            "metodo_contacto": self.metodo_contacto,
            "respuesta": self.respuesta,
        }


class LogScraping(Base):
    """
    Registro de cada ejecución de scraping.
    Permite trackear qué se buscó, cuántos resultados se obtuvieron, y errores.
    """
    __tablename__ = "log_scraping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline = Column(String(50), nullable=False)   # web | email | phone | social | trips
    deporte = Column(String(50), nullable=True)
    locacion = Column(String(200), nullable=True)
    fuente = Column(String(100), nullable=True)
    resultados_encontrados = Column(Integer, default=0)
    resultados_nuevos = Column(Integer, default=0)
    errores = Column(Integer, default=0)
    mensaje_error = Column(Text, nullable=True)
    duracion_segundos = Column(Float, nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LogScraping(pipeline='{self.pipeline}', deporte='{self.deporte}', locacion='{self.locacion}')>"


class LogContacto(Base):
    """
    Registro de cada intento de contacto enviado.
    """
    __tablename__ = "log_contacto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    negocio_id = Column(String(36), nullable=False)
    metodo = Column(String(50), nullable=False)      # email | whatsapp
    destinatario = Column(String(255), nullable=False)  # email o teléfono destino
    template_usado = Column(String(100), nullable=True)
    estado = Column(String(50), default="enviado")   # enviado | fallido | rebotado
    mensaje_error = Column(Text, nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LogContacto(negocio_id='{self.negocio_id}', metodo='{self.metodo}', estado='{self.estado}')>"
