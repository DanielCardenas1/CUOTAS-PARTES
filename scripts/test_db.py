import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.models import Base, Entidad
from app.db import engine

# Crear tablas si no existen
def crear_tablas():
    Base.metadata.create_all(engine)
    print("Tablas creadas (si no existían)")

# Consulta sencilla a la tabla entidad
def consultar_entidades():
    with engine.connect() as connection:
        result = connection.execute("SELECT * FROM entidad")
        for row in result:
            print(row)

if __name__ == "__main__":
    crear_tablas()
    consultar_entidades()
