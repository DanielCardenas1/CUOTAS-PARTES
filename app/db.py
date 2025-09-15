# Objetivo (Copilot): crear engine y sessionmaker SQLAlchemy a MySQL
# - Función get_session() que entrega una sesión
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import settings

def _dsn():
    return f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?charset=utf8mb4"

engine = create_engine(_dsn(), pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_session():
    """
    Objetivo (Copilot): Retorna una nueva sesión SQLAlchemy.
    """
    return SessionLocal()
