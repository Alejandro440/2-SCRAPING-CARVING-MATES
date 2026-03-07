"""
Conexión a la base de datos.
Usa SQLAlchemy para abstraer el motor de DB (SQLite en desarrollo, PostgreSQL en producción).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from config.settings import DATABASE_URL

# Crear motor de base de datos
# check_same_thread=False es necesario para SQLite con múltiples hilos
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # Cambiar a True para debug SQL
)

# Fábrica de sesiones
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_session() -> Session:
    """
    Context manager para obtener una sesión de base de datos.
    Hace commit automático al salir, rollback si hay error.

    Uso:
        with get_session() as session:
            session.add(negocio)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """
    Crea todas las tablas definidas en los modelos.
    Seguro de ejecutar múltiples veces (solo crea tablas que no existan).
    """
    from database.models import Base
    Base.metadata.create_all(bind=engine)
