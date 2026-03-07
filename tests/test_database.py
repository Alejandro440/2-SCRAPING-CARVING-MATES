"""
Tests para la conexión a base de datos y modelos.
Ejecutar con: pytest tests/test_database.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Negocio, LogScraping, LogContacto


def get_test_session():
    """Crea una DB en memoria para tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestModelos:
    def test_crear_negocio(self):
        session = get_test_session()
        negocio = Negocio(
            nombre="Test Surf School",
            tipo_negocio="escuela",
            deporte="surf",
            pais="Indonesia",
            region="Bali",
            ciudad="Canggu",
            website="https://testsurfschool.com",
            emails=["info@testsurfschool.com"],
            telefonos=["+62812345678"],
        )
        session.add(negocio)
        session.commit()

        guardado = session.query(Negocio).first()
        assert guardado.nombre == "Test Surf School"
        assert guardado.deporte == "surf"
        assert guardado.pais == "Indonesia"
        assert "info@testsurfschool.com" in guardado.emails
        session.close()

    def test_to_dict(self):
        negocio = Negocio(
            nombre="Test School",
            tipo_negocio="escuela",
            deporte="surf",
        )
        d = negocio.to_dict()
        assert d["nombre"] == "Test School"
        assert isinstance(d["emails"], list)
        assert isinstance(d["redes_sociales"], dict)

    def test_log_scraping(self):
        session = get_test_session()
        log = LogScraping(
            pipeline="web",
            deporte="surf",
            locacion="Bali",
            resultados_encontrados=10,
            resultados_nuevos=7,
            errores=1,
        )
        session.add(log)
        session.commit()

        guardado = session.query(LogScraping).first()
        assert guardado.pipeline == "web"
        assert guardado.resultados_nuevos == 7
        session.close()

    def test_log_contacto(self):
        session = get_test_session()
        log = LogContacto(
            negocio_id="test-id-123",
            metodo="email",
            destinatario="info@test.com",
            template_usado="escuela_inicial",
            estado="enviado",
        )
        session.add(log)
        session.commit()

        guardado = session.query(LogContacto).first()
        assert guardado.metodo == "email"
        assert guardado.estado == "enviado"
        session.close()

    def test_negocio_defaults(self):
        session = get_test_session()
        negocio = Negocio(
            nombre="Default Test",
            tipo_negocio="escuela",
            deporte="surf",
        )
        session.add(negocio)
        session.commit()
        guardado = session.query(Negocio).filter_by(nombre="Default Test").first()
        assert guardado.contactado is False
        assert guardado.respuesta is None
        session.close()
