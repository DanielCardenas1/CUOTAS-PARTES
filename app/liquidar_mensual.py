#!/usr/bin/env python3
"""
Nuevo sistema de liquidación mensual (no acumulativo)
Calcula solo el mes específico con intereses según vencimiento
"""

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import text
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def calcular_liquidacion_mensual(session, pensionado_id: int, año: int, mes: int, fecha_calculo: date = None) -> dict:
    """
    Calcula la liquidación de un mes específico (no acumulativo).
    
    Args:
        session: Sesión de SQLAlchemy
        pensionado_id: ID del pensionado
        año: Año a liquidar
        mes: Mes a liquidar (1-12)
        fecha_calculo: Fecha actual para calcular vencimiento (default: hoy)
        
    Returns:
        Diccionario con los resultados del cálculo mensual
    """
    if fecha_calculo is None:
        fecha_calculo = date.today()
    
    try:
        # Obtener datos del pensionado
        query_pensionado = text("""
            SELECT 
                p.identificacion,
                p.nombre,
                p.base_calculo_cuota_parte,
                p.porcentaje_cuota_parte,
                p.fecha_ingreso_nomina,
                p.nit_entidad
            FROM pensionado p
            WHERE p.pensionado_id = :pensionado_id
        """)
        
        pensionado = session.execute(query_pensionado, {'pensionado_id': pensionado_id}).fetchone()
        
        if not pensionado:
            raise ValueError(f"Pensionado con ID {pensionado_id} no encontrado")
        
        # Fecha del mes a liquidar
        fecha_mes_liquidar = date(año, mes, 1)
        fecha_fin_mes = fecha_mes_liquidar + relativedelta(months=1) - relativedelta(days=1)
        
        # Verificar si el pensionado ya estaba activo en ese mes
        if pensionado.fecha_ingreso_nomina and pensionado.fecha_ingreso_nomina > fecha_fin_mes:
            return {
                'pensionado_id': pensionado_id,
                'identificacion': pensionado.identificacion,
                'nombre': pensionado.nombre,
                'año': año,
                'mes': mes,
                'capital_mes': 0.0,
                'intereses': 0.0,
                'total': 0.0,
                'tiene_intereses': False,
                'motivo_sin_intereses': 'Pensionado no estaba activo en este período',
                'observaciones': f'Ingreso en nómina: {pensionado.fecha_ingreso_nomina}'
            }
        
        # Por ahora, asumimos que no hay pagos (simplificado para demostración)
        ya_pagado = False
        
        # Calcular capital mensual
        base_calculo = float(pensionado.base_calculo_cuota_parte or 0)
        porcentaje_cuota = float(pensionado.porcentaje_cuota_parte or 0.02)
        capital_mes = base_calculo * porcentaje_cuota
        
        # Lógica de cuotas partes (mes vencido)
        # Solo se puede generar cuenta de cobro del mes anterior al actual
        mes_actual = fecha_calculo.month
        año_actual = fecha_calculo.year
        
        # Verificar si es un mes que se puede liquidar (mes vencido)
        if año > año_actual or (año == año_actual and mes >= mes_actual):
            return {
                'pensionado_id': pensionado_id,
                'identificacion': pensionado.identificacion,
                'nombre': pensionado.nombre,
                'año': año,
                'mes': mes,
                'capital_mes': 0.0,
                'intereses': 0.0,
                'total': 0.0,
                'tiene_intereses': False,
                'motivo_sin_intereses': f'No se puede liquidar mes {mes:02d}/{año} desde {fecha_calculo.strftime("%m/%Y")} (solo mes vencido)',
                'observaciones': 'Las cuotas partes se cobran mes vencido'
            }
        
        # Determinar si debe generar intereses
        debe_generar_intereses = False
        motivo_sin_intereses = ""
        meses_vencimiento = 0
        
        if ya_pagado:
            debe_generar_intereses = False
            motivo_sin_intereses = "Ya fue pagado"
        else:
            # Fecha límite para pago sin intereses (mes siguiente al liquidado)
            fecha_limite_pago = date(año, mes, 1) + relativedelta(months=2)  # Primer día del mes siguiente al que se puede cobrar
            
            if fecha_calculo < fecha_limite_pago:
                debe_generar_intereses = False
                motivo_sin_intereses = f"Sin intereses (límite: {fecha_limite_pago.strftime('%Y-%m-%d')})"
            else:
                debe_generar_intereses = True
                # Calcular meses vencidos desde la fecha límite
                meses_vencidos = 0
                fecha_temp = fecha_limite_pago
                while fecha_temp <= fecha_calculo:
                    fecha_temp += relativedelta(months=1)
                    meses_vencidos += 1
                meses_vencimiento = meses_vencidos
        
        # Calcular intereses si corresponde
        intereses = 0.0
        if debe_generar_intereses and meses_vencimiento > 0:
            # Obtener tasas DTF para el período de vencimiento
            fecha_inicio_intereses = fecha_fin_mes + relativedelta(months=1)
            tasas_dtf = obtener_tasas_dtf_periodo(session, fecha_inicio_intereses, fecha_calculo)
            
            if tasas_dtf:
                for i in range(min(meses_vencimiento, len(tasas_dtf))):
                    tasa_decimal = float(tasas_dtf[i]) / 100.0
                    interes_mes = capital_mes * tasa_decimal
                    intereses += interes_mes
        
        total = capital_mes + intereses
        
        resultado = {
            'pensionado_id': pensionado_id,
            'identificacion': pensionado.identificacion,
            'nombre': pensionado.nombre,
            'año': año,
            'mes': mes,
            'fecha_mes': fecha_mes_liquidar,
            'base_calculo': base_calculo,
            'porcentaje_cuota': porcentaje_cuota,
            'capital_mes': capital_mes,
            'intereses': intereses,
            'total': total,
            'tiene_intereses': debe_generar_intereses,
            'meses_vencimiento': meses_vencimiento,
            'motivo_sin_intereses': motivo_sin_intereses,
            'ya_pagado': ya_pagado,
            'fecha_calculo': fecha_calculo,
            'observaciones': f'Liquidación mensual para {mes:02d}/{año}'
        }
        
        logger.info(f"Liquidación mensual calculada para {pensionado.identificacion} - {mes:02d}/{año}: "
                   f"Capital=${capital_mes:.2f}, Interés=${intereses:.2f}, Total=${total:.2f}")
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error calculando liquidación mensual para pensionado {pensionado_id}: {e}")
        raise

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
        
        tasas = [row.tasa for row in result]
        logger.debug(f"Obtenidas {len(tasas)} tasas DTF para período {fecha_inicio} - {fecha_fin}")
        
        return tasas
        
    except Exception as e:
        logger.error(f"Error obteniendo tasas DTF: {e}")
        return []

def generar_liquidacion_mensual_entidad(session, entidad_nit: str, año: int, mes: int, fecha_calculo: date = None) -> dict:
    """
    Genera liquidación mensual para toda una entidad.
    
    Args:
        session: Sesión de SQLAlchemy
        entidad_nit: NIT de la entidad
        año: Año a liquidar
        mes: Mes a liquidar
        fecha_calculo: Fecha actual para cálculo de vencimiento
        
    Returns:
        Dict con liquidación completa de la entidad
    """
    if fecha_calculo is None:
        fecha_calculo = date.today()
    
    try:
        # Verificar que la entidad existe
        entidad = session.execute(
            text("SELECT entidad_id, nombre FROM entidad WHERE nit = :nit"),
            {"nit": entidad_nit}
        ).fetchone()
        
        if not entidad:
            raise ValueError(f"Entidad con NIT {entidad_nit} no encontrada")
        
        # Obtener pensionados activos de la entidad
        pensionados = session.execute(
            text("""
                SELECT pensionado_id, identificacion, nombre
                FROM pensionado 
                WHERE nit_entidad = :nit 
                  AND estado_cartera = 'ACTIVO'
                ORDER BY nombre
            """),
            {"nit": entidad_nit}
        ).fetchall()
        
        liquidacion_data = {
            'entidad': {
                'nit': entidad_nit,
                'nombre': entidad.nombre
            },
            'periodo': {
                'año': año,
                'mes': mes,
                'fecha_calculo': fecha_calculo
            },
            'pensionados': [],
            'totales': {
                'capital': 0.0,
                'intereses': 0.0,
                'total': 0.0,
                'con_intereses': 0,
                'sin_intereses': 0,
                'ya_pagados': 0
            }
        }
        
        contador = 1
        for pensionado in pensionados:
            try:
                resultado = calcular_liquidacion_mensual(
                    session, pensionado.pensionado_id, año, mes, fecha_calculo
                )
                
                # Formatear para mostrar
                pensionado_data = {
                    'numero': contador,
                    'nombre': resultado['nombre'],
                    'documento': resultado['identificacion'],
                    'capital': f"$ {resultado['capital_mes']:,.2f}",
                    'intereses': f"$ {resultado['intereses']:,.2f}",
                    'total': f"$ {resultado['total']:,.2f}",
                    'tiene_intereses': resultado['tiene_intereses'],
                    'motivo_sin_intereses': resultado['motivo_sin_intereses'],
                    'ya_pagado': resultado['ya_pagado'],
                    # Valores numéricos para totales
                    'capital_num': resultado['capital_mes'],
                    'intereses_num': resultado['intereses'],
                    'total_num': resultado['total']
                }
                
                liquidacion_data['pensionados'].append(pensionado_data)
                
                # Actualizar totales
                liquidacion_data['totales']['capital'] += resultado['capital_mes']
                liquidacion_data['totales']['intereses'] += resultado['intereses']
                liquidacion_data['totales']['total'] += resultado['total']
                
                if resultado['tiene_intereses']:
                    liquidacion_data['totales']['con_intereses'] += 1
                else:
                    liquidacion_data['totales']['sin_intereses'] += 1
                
                if resultado['ya_pagado']:
                    liquidacion_data['totales']['ya_pagados'] += 1
                
                contador += 1
                
            except Exception as e:
                logger.warning(f"Error procesando pensionado {pensionado.identificacion}: {e}")
                continue
        
        # Formatear totales
        liquidacion_data['totales_formateados'] = {
            'capital': f"$ {liquidacion_data['totales']['capital']:,.2f}",
            'intereses': f"$ {liquidacion_data['totales']['intereses']:,.2f}",
            'total': f"$ {liquidacion_data['totales']['total']:,.2f}"
        }
        
        logger.info(f"Liquidación mensual {mes:02d}/{año} generada para entidad {entidad_nit}: "
                   f"{len(liquidacion_data['pensionados'])} pensionados, "
                   f"Total=${liquidacion_data['totales']['total']:,.2f}")
        
        return liquidacion_data
        
    except Exception as e:
        logger.error(f"Error generando liquidación mensual: {e}")
        raise