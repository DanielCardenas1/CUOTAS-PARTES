from dotenv import load_dotenv
import os

load_dotenv()
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "liquidaciones")
DB_USER = os.getenv("DB_USER", "liq_user")
DB_PASS = os.getenv("DB_PASS", "liq_pass")

CONSECUTIVO_PREFIJO = os.getenv("CONSECUTIVO_PREFIJO", "CCP-")
DIAS_SILENCIO_ADMIN = int(os.getenv("DIAS_SILENCIO_ADMIN", "15"))

# Meses de prescripción para generación de cuentas (antes 36, ahora 30)
MESES_PRESCRIPCION = int(os.getenv("MESES_PRESCRIPCION", "30"))
