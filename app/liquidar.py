# Objetivo (Copilot):
# - Generar liquidación por entidad y rango (últimos 36 meses)
# - Crear encabezado (liquidacion), agregar detalle por pensionado/mes (liquidacion_detalle)
# - totalizar capital e interés
# - generar consecutivo: PREFIJO + AAAA + MM + secuencia
from datetime import date

def generar_liquidacion(session, entidad_id: int, periodo_inicio: date, periodo_fin: date) -> int:
    """
    Retorna liquidacion_id creado.
    """
    pass
