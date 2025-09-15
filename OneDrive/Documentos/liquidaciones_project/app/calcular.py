# Objetivo (Copilot): lógica de cálculo de capital + interés mensual
# - Dado pensionado, periodo y valor base, calcula capital (si aplica %) e interés usando DTF mensual
# - Fórmula: interes_mensual = capital * dtf_mes
# - Acumular meses desde 'Ultima fecha de pago' hasta 'fecha_corte'
from datetime import date

def calcular_interes_dtf(capital: float, meses: int, tasas: list[float]) -> float:
    """
    tasas: lista de DTF mensual (decimales) en orden cronológico.
    interés simple mes a mes: sum(capital * tasa_mes)
    """
    pass
