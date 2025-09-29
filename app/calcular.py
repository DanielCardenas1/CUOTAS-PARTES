# Objetivo (Copilot): lógica de cálculo de capital + interés mensual
# - Dado pensionado, periodo y valor base, calcula capital (si aplica %) e interés usando DTF mensual
# - Fórmula: interes_mensual = capital * dtf_mes
# - Acumular meses desde 'Ultima fecha de pago' hasta 'fecha_corte'

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import text
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def calcular_interes_dtf(capital: float, meses: int, tasas: list[float]) -> float:
    """
    Calcula interés simple usando DTF mensual.
    
    Args:
        capital: Valor del capital base
        meses: Número de meses a calcular
        tasas: Lista de DTF mensual (decimales) en orden cronológico
        
    Returns:
        Total de intereses calculados
    """
    if not tasas or meses <= 0 or capital <= 0:
        return 0.0
    
    interes_total = 0.0
    for i in range(min(meses, len(tasas))):
        tasa_mes = tasas[i] / 100.0  # Convertir porcentaje a decimal
        interes_mes = capital * tasa_mes
        interes_total += interes_mes
        logger.debug(f"Mes {i+1}: Capital={capital}, Tasa={tasa_mes:.6f}, Interés={interes_mes:.2f}")
    
    return interes_total

def obtener_tasas_dtf_periodo(session, fecha_inicio: date, fecha_fin: date) -> list[float]:
    """
    Obtiene las tasas DTF para un período específico.
    
    Args:
        session: Sesión de SQLAlchemy
        fecha_inicio: Fecha de inicio del período
        fecha_fin: Fecha de fin del período
        
    Returns:
        Lista de tasas DTF ordenadas cronológicamente
    """
    try:
        query = text("""
            SELECT tasa 
            FROM dtf_mensual 
            WHERE periodo >= :fecha_inicio 
              AND periodo <= :fecha_fin 
            ORDER BY periodo ASC
        """)
        
        result = session.execute(query, {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin
        })
        
        tasas = [float(row[0]) for row in result.fetchall()]
        
        # Si no hay tasas específicas, usar tasa promedio del último año disponible
        if not tasas:
            query_promedio = text("""
                SELECT AVG(tasa) as tasa_promedio
                FROM dtf_mensual 
                WHERE periodo >= DATE_SUB(:fecha_fin, INTERVAL 12 MONTH)
            """)
            
            result_promedio = session.execute(query_promedio, {'fecha_fin': fecha_fin})
            tasa_promedio = result_promedio.scalar()
            
            if tasa_promedio:
                # Llenar con la tasa promedio para todos los meses del período
                meses_periodo = calcular_meses_entre_fechas(fecha_inicio, fecha_fin)
                tasas = [float(tasa_promedio)] * meses_periodo
            else:
                # Usar tasa por defecto si no hay datos DTF
                logger.warning("No se encontraron tasas DTF, usando tasa por defecto del 0.5% mensual")
                meses_periodo = calcular_meses_entre_fechas(fecha_inicio, fecha_fin)
                tasas = [0.5] * meses_periodo  # 0.5% mensual por defecto
        
        return tasas
        
    except Exception as e:
        logger.error(f"Error obteniendo tasas DTF: {e}")
        return []

def calcular_meses_entre_fechas(fecha_inicio: date, fecha_fin: date) -> int:
    """
    Calcula el número de meses entre dos fechas.
    """
    if fecha_inicio >= fecha_fin:
        return 0
    
    meses = 0
    fecha_actual = fecha_inicio
    
    while fecha_actual < fecha_fin:
        fecha_actual += relativedelta(months=1)
        meses += 1
    
    return meses

def calcular_cuota_parte_mensual(base_calculo: float, porcentaje_cuota: float = None) -> float:
    """
    Calcula la cuota parte mensual basada en la base de cálculo y porcentaje.
    
    Args:
        base_calculo: Base salarial para el cálculo
        porcentaje_cuota: Porcentaje de cuota parte (si es None, usa valor por defecto)
        
    Returns:
        Valor de la cuota parte mensual
    """
    if porcentaje_cuota is None:
        porcentaje_cuota = 0.02  # 2% por defecto
    
    return base_calculo * porcentaje_cuota

def calcular_liquidacion_pensionado(session, pensionado_id: int, fecha_corte: date) -> dict:
    """
    Calcula la liquidación completa de un pensionado hasta una fecha de corte.
    
    Args:
        session: Sesión de SQLAlchemy
        pensionado_id: ID del pensionado
        fecha_corte: Fecha hasta la cual calcular
        
    Returns:
        Diccionario con los resultados del cálculo
    """
    try:
        # Obtener datos del pensionado
        query_pensionado = text("""
            SELECT 
                p.identificacion,
                p.nombre,
                p.ultima_fecha_pago,
                p.base_calculo_cuota_parte,
                p.porcentaje_cuota_parte,
                p.capital_pendiente,
                p.intereses_pendientes,
                p.fecha_ingreso_nomina
            FROM pensionado p
            WHERE p.pensionado_id = :pensionado_id
        """)
        
        pensionado = session.execute(query_pensionado, {'pensionado_id': pensionado_id}).fetchone()
        
        if not pensionado:
            raise ValueError(f"Pensionado con ID {pensionado_id} no encontrado")
        
        # Determinar fecha de inicio para el cálculo
        fecha_inicio = pensionado.ultima_fecha_pago or pensionado.fecha_ingreso_nomina
        if not fecha_inicio:
            raise ValueError("No se puede determinar fecha de inicio para el cálculo")
        
        # Si la fecha de inicio es posterior a la fecha de corte, no hay nada que calcular
        if fecha_inicio >= fecha_corte:
            return {
                'pensionado_id': pensionado_id,
                'identificacion': pensionado.identificacion,
                'nombre': pensionado.nombre,
                'fecha_inicio': fecha_inicio,
                'fecha_corte': fecha_corte,
                'meses_calculados': 0,
                'capital_mensual': 0.0,
                'interes_calculado': 0.0,
                'total_liquidacion': 0.0,
                'observaciones': 'Sin períodos pendientes de liquidación'
            }
        
        # Calcular cuota parte mensual
        base_calculo = float(pensionado.base_calculo_cuota_parte or 0)
        porcentaje_cuota = float(pensionado.porcentaje_cuota_parte or 0.02)
        capital_mensual = calcular_cuota_parte_mensual(base_calculo, porcentaje_cuota)
        
        # Calcular meses a liquidar
        meses_liquidar = calcular_meses_entre_fechas(fecha_inicio, fecha_corte)
        
        # Obtener tasas DTF para el período
        tasas_dtf = obtener_tasas_dtf_periodo(session, fecha_inicio, fecha_corte)
        
        # Calcular intereses
        capital_total_periodo = capital_mensual * meses_liquidar
        interes_calculado = calcular_interes_dtf(capital_total_periodo, meses_liquidar, tasas_dtf)
        
        resultado = {
            'pensionado_id': pensionado_id,
            'identificacion': pensionado.identificacion,
            'nombre': pensionado.nombre,
            'fecha_inicio': fecha_inicio,
            'fecha_corte': fecha_corte,
            'meses_calculados': meses_liquidar,
            'base_calculo': base_calculo,
            'porcentaje_cuota': porcentaje_cuota,
            'capital_mensual': capital_mensual,
            'capital_total_periodo': capital_total_periodo,
            'interes_calculado': interes_calculado,
            'total_liquidacion': capital_total_periodo + interes_calculado,
            'tasas_dtf_utilizadas': tasas_dtf[:5] if tasas_dtf else [],  # Primeras 5 tasas para referencia
            'observaciones': f'Liquidación calculada para {meses_liquidar} meses'
        }
        
        logger.info(f"Liquidación calculada para pensionado {pensionado.identificacion}: "
                   f"Capital={capital_total_periodo:.2f}, Interés={interes_calculado:.2f}, "
                   f"Total={resultado['total_liquidacion']:.2f}")
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error calculando liquidación para pensionado {pensionado_id}: {e}")
        raise
