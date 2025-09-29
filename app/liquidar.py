# Objetivo (Copilot):
# - Generar liquidación por entidad y rango (últimos 36 meses)
# - Crear encabezado (liquidacion), agregar detalle por pensionado/mes (liquidacion_detalle)
# - totalizar capital e interés
# - generar consecutivo: PREFIJO + AAAA + MM + secuencia

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import text
from decimal import Decimal
import logging
from .calcular import calcular_liquidacion_pensionado, obtener_tasas_dtf_periodo, calcular_meses_entre_fechas
from . import settings

logger = logging.getLogger(__name__)

def generar_liquidacion_completa(session, entidad_nit: str, periodo_inicio: date, periodo_fin: date) -> dict:
    """
    Genera una liquidación completa con todos los datos requeridos para vista previa y PDF.
    
    Args:
        session: Sesión de SQLAlchemy
        entidad_nit: NIT de la entidad
        periodo_inicio: Fecha de inicio del período
        periodo_fin: Fecha de fin del período
        
    Returns:
        Dict con datos completos de la liquidación
    """
    try:
        # Verificar que la entidad existe
        entidad = session.execute(
            text("SELECT entidad_id, nombre FROM entidad WHERE nit = :nit"),
            {"nit": entidad_nit}
        ).fetchone()
        
        if not entidad:
            raise ValueError(f"Entidad con NIT {entidad_nit} no encontrada")
        
        # Obtener pensionados de la entidad con todos los campos necesarios
        pensionados = session.execute(
            text("""
                SELECT p.pensionado_id, p.identificacion, p.nombre, 
                       p.base_calculo_cuota_parte, p.porcentaje_cuota_parte,
                       p.ultima_fecha_pago, p.fecha_ingreso_nomina,
                       p.capital_pendiente, p.intereses_pendientes,
                       p.cedula_sustituto, p.nombre_sustituto
                FROM pensionado p
                WHERE p.nit_entidad = :nit 
                  AND p.estado_cartera = 'ACTIVO'
                ORDER BY p.nombre
            """),
            {"nit": entidad_nit}
        ).fetchall()
        
        if not pensionados:
            raise ValueError(f"No se encontraron pensionados activos para la entidad {entidad_nit}")
        
        # Preparar datos de la liquidación
        liquidacion_data = {
            'encabezado': {
                'titulo': 'LIQUIDACION OFICIAL DE PENSIONADOS',
                'entidad': f"{entidad.nombre} - NIT:{entidad_nit}",
                'periodo': f'{periodo_inicio.strftime("%d/%m/%Y")} - {periodo_fin.strftime("%d/%m/%Y")}',
                'fecha_generacion': datetime.now().strftime("%d/%m/%Y")
            },
            'columnas': [
                'No.',
                'APELLIDOS Y NOMBRES DEL PENSIONADO',
                'No. DOCUMENTO',
                'SUSTITUTO',
                'No. DOCUMENTO',
                '% DE CONCURRENCIA',
                'VALOR MESADA',
                'PERIODO LIQUIDADO',
                'CAPITAL',
                'INTERESES',
                'TOTAL'
            ],
            'pensionados': [],
            'totales': {
                'capital': Decimal('0.00'),
                'intereses': Decimal('0.00'),
                'total': Decimal('0.00')
            }
        }
        
        # Procesar cada pensionado
        contador = 1
        for pensionado in pensionados:
            try:
                # Calcular liquidación del pensionado
                calculo = calcular_liquidacion_pensionado(
                    session, pensionado.pensionado_id, periodo_fin
                )
                
                if calculo['meses_calculados'] > 0:
                    capital = Decimal(str(calculo['capital_total_periodo']))
                    intereses = Decimal(str(calculo['interes_calculado']))
                    total = capital + intereses
                    
                    # Datos del pensionado para la liquidación
                    pensionado_data = {
                        'numero': contador,
                        'nombre': pensionado.nombre or '',
                        'documento': pensionado.identificacion or '',
                        'sustituto': pensionado.nombre_sustituto or '',
                        'documento_sustituto': pensionado.cedula_sustituto or '',
                        'porcentaje_concurrencia': f"{float(pensionado.porcentaje_cuota_parte or 0) * 100:.2f}%" if pensionado.porcentaje_cuota_parte else "0.00%",
                        'valor_mesada': f"$ {float(pensionado.base_calculo_cuota_parte or 0):,.2f}",
                        'periodo_liquidado': f"{periodo_inicio.strftime('%d%b-%Y')} - {periodo_fin.strftime('%d%b-%Y')}",
                        'capital': f"$ {float(capital):,.2f}",
                        'intereses': f"$ {float(intereses):,.2f}",
                        'total': f"$ {float(total):,.2f}",
                        # Valores numéricos para cálculos
                        'capital_num': capital,
                        'intereses_num': intereses,
                        'total_num': total
                    }
                    
                    liquidacion_data['pensionados'].append(pensionado_data)
                    
                    # Actualizar totales
                    liquidacion_data['totales']['capital'] += capital
                    liquidacion_data['totales']['intereses'] += intereses
                    liquidacion_data['totales']['total'] += total
                    
                    contador += 1
                    
                    logger.debug(f"Procesado pensionado {pensionado.identificacion}: "
                               f"Capital={capital:.2f}, Interés={intereses:.2f}")
                    
            except Exception as e:
                logger.warning(f"Error procesando pensionado {pensionado.identificacion}: {e}")
                continue
        
        # Formatear totales
        liquidacion_data['totales_formateados'] = {
            'capital': f"$ {float(liquidacion_data['totales']['capital']):,.2f}",
            'intereses': f"$ {float(liquidacion_data['totales']['intereses']):,.2f}",
            'total': f"$ {float(liquidacion_data['totales']['total']):,.2f}"
        }
        
        logger.info(f"Liquidación completa generada para entidad {entidad_nit}: "
                   f"{len(liquidacion_data['pensionados'])} pensionados, "
                   f"Total=${float(liquidacion_data['totales']['total']):,.2f}")
        
        return liquidacion_data
        
    except Exception as e:
        logger.error(f"Error generando liquidación completa para entidad {entidad_nit}: {e}")
        raise

def generar_liquidacion(session, entidad_nit: str, periodo_inicio: date, periodo_fin: date) -> int:
    """
    Genera una liquidación completa para una entidad en un período específico.
    
    Args:
        session: Sesión de SQLAlchemy
        entidad_nit: NIT de la entidad
        periodo_inicio: Fecha de inicio del período
        periodo_fin: Fecha de fin del período
        
    Returns:
        ID de la liquidación creada
    """
    try:
        # Verificar que la entidad existe
        entidad = session.execute(
            text("SELECT entidad_id, nombre FROM entidad WHERE nit = :nit"),
            {"nit": entidad_nit}
        ).fetchone()
        
        if not entidad:
            raise ValueError(f"Entidad con NIT {entidad_nit} no encontrada")
        
        # Obtener pensionados de la entidad
        pensionados = session.execute(
            text("""
                SELECT pensionado_id, identificacion, nombre, 
                       base_calculo_cuota_parte, porcentaje_cuota_parte,
                       ultima_fecha_pago, fecha_ingreso_nomina,
                       capital_pendiente, intereses_pendientes
                FROM pensionado 
                WHERE nit_entidad = :nit 
                  AND estado_cartera = 'ACTIVO'
            """),
            {"nit": entidad_nit}
        ).fetchall()
        
        if not pensionados:
            raise ValueError(f"No se encontraron pensionados activos para la entidad {entidad_nit}")
        
        # Crear el encabezado de liquidación
        liquidacion_id = crear_encabezado_liquidacion(
            session, entidad.nombre, entidad_nit, periodo_inicio, periodo_fin
        )
        
        total_capital = Decimal('0.00')
        total_interes = Decimal('0.00')
        detalles_creados = 0
        
        # Procesar cada pensionado
        for pensionado in pensionados:
            try:
                # Calcular liquidación del pensionado
                calculo = calcular_liquidacion_pensionado(
                    session, pensionado.pensionado_id, periodo_fin
                )
                
                if calculo['meses_calculados'] > 0:
                    # Crear detalle de liquidación
                    detalle_id = crear_detalle_liquidacion(
                        session,
                        liquidacion_id,
                        pensionado.pensionado_id,
                        periodo_inicio,
                        periodo_fin,
                        Decimal(str(calculo['capital_total_periodo'])),
                        Decimal(str(calculo['interes_calculado']))
                    )
                    
                    total_capital += Decimal(str(calculo['capital_total_periodo']))
                    total_interes += Decimal(str(calculo['interes_calculado']))
                    detalles_creados += 1
                    
                    # ACTUALIZAR CAMPOS EN BASE DE DATOS
                    actualizar_saldos_pensionado(
                        session,
                        pensionado.pensionado_id,
                        Decimal(str(calculo['capital_total_periodo'])),
                        Decimal(str(calculo['interes_calculado']))
                    )
                    
                    logger.debug(f"Detalle creado para pensionado {pensionado.identificacion}: "
                               f"Capital={calculo['capital_total_periodo']:.2f}, "
                               f"Interés={calculo['interes_calculado']:.2f}")
                    
            except Exception as e:
                logger.warning(f"Error procesando pensionado {pensionado.identificacion}: {e}")
                continue
        
        # Actualizar totales en el encabezado
        actualizar_totales_liquidacion(session, liquidacion_id, total_capital, total_interes)
        
        logger.info(f"Liquidación {liquidacion_id} creada para entidad {entidad_nit}: "
                   f"{detalles_creados} pensionados, Capital={total_capital:.2f}, "
                   f"Interés={total_interes:.2f}, Total={total_capital + total_interes:.2f}")
        
        return liquidacion_id
        
    except Exception as e:
        logger.error(f"Error generando liquidación para entidad {entidad_nit}: {e}")
        session.rollback()
        raise

def crear_encabezado_liquidacion(session, nombre_entidad: str, nit_entidad: str, 
                                periodo_inicio: date, periodo_fin: date) -> int:
    """
    Crea el encabezado de una liquidación.
    """
    try:
        # Insertar encabezado
        result = session.execute(
            text("""
                INSERT INTO liquidacion (
                    nombre, identificacion, periodo_inicio, periodo_fin, 
                    capital, interes, total, estado
                ) VALUES (
                    :nombre, :nit, :periodo_inicio, :periodo_fin,
                    0.00, 0.00, 0.00, 'DRAFT'
                )
            """),
            {
                "nombre": nombre_entidad,
                "nit": nit_entidad,
                "periodo_inicio": periodo_inicio,
                "periodo_fin": periodo_fin
            }
        )
        
        liquidacion_id = result.lastrowid
        session.commit()
        
        logger.info(f"Encabezado de liquidación creado: ID={liquidacion_id}, "
                   f"Entidad={nombre_entidad}, Período={periodo_inicio} a {periodo_fin}")
        
        return liquidacion_id
        
    except Exception as e:
        logger.error(f"Error creando encabezado de liquidación: {e}")
        session.rollback()
        raise

def crear_detalle_liquidacion(session, liquidacion_id: int, pensionado_id: int,
                             periodo_inicio: date, periodo_fin: date,
                             capital: Decimal, interes: Decimal) -> int:
    """
    Crea un detalle de liquidación para un pensionado.
    """
    try:
        total = capital + interes
        
        result = session.execute(
            text("""
                INSERT INTO liquidacion_detalle (
                    liquidacion_id, pensionado_id, periodo,
                    capital, interes, total
                ) VALUES (
                    :liquidacion_id, :pensionado_id, :periodo,
                    :capital, :interes, :total
                )
            """),
            {
                "liquidacion_id": liquidacion_id,
                "pensionado_id": pensionado_id,
                "periodo": periodo_inicio,  # Usar fecha de inicio como referencia
                "capital": capital,
                "interes": interes,
                "total": total
            }
        )
        
        detalle_id = result.lastrowid
        session.commit()
        
        return detalle_id
        
    except Exception as e:
        logger.error(f"Error creando detalle de liquidación: {e}")
        session.rollback()
        raise

def actualizar_saldos_pensionado(session, pensionado_id: int, 
                                capital_pendiente: Decimal, intereses_pendientes: Decimal):
    """
    Actualiza los saldos de capital e intereses pendientes en la tabla pensionados.
    """
    try:
        session.execute(
            text("""
                UPDATE pensionado 
                SET capital_pendiente = :capital_pendiente,
                    intereses_pendientes = :intereses_pendientes
                WHERE pensionado_id = :pensionado_id
            """),
            {
                "pensionado_id": pensionado_id,
                "capital_pendiente": capital_pendiente,
                "intereses_pendientes": intereses_pendientes
            }
        )
        
        logger.debug(f"Saldos actualizados para pensionado {pensionado_id}: "
                   f"Capital={capital_pendiente:.2f}, Intereses={intereses_pendientes:.2f}")
        
    except Exception as e:
        logger.error(f"Error actualizando saldos del pensionado {pensionado_id}: {e}")
        raise

def actualizar_totales_liquidacion(session, liquidacion_id: int, 
                                  total_capital: Decimal, total_interes: Decimal):
    """
    Actualiza los totales en el encabezado de liquidación.
    """
    try:
        total_general = total_capital + total_interes
        
        session.execute(
            text("""
                UPDATE liquidacion 
                SET capital = :capital, 
                    interes = :interes, 
                    total = :total,
                    estado = 'GENERATED',
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE liquidacion_id = :liquidacion_id
            """),
            {
                "liquidacion_id": liquidacion_id,
                "capital": total_capital,
                "interes": total_interes,
                "total": total_general
            }
        )
        
        session.commit()
        
        logger.info(f"Totales actualizados para liquidación {liquidacion_id}: "
                   f"Capital={total_capital:.2f}, Interés={total_interes:.2f}, "
                   f"Total={total_general:.2f}")
        
    except Exception as e:
        logger.error(f"Error actualizando totales de liquidación {liquidacion_id}: {e}")
        session.rollback()
        raise

def generar_consecutivo_liquidacion(session, fecha_referencia: date) -> str:
    """
    Genera un consecutivo único para la liquidación.
    Formato: PREFIJO + AAAA + MM + secuencia
    """
    try:
        prefijo = getattr(settings, 'CONSECUTIVO_PREFIJO', 'LIQ-')
        anio = fecha_referencia.year
        mes = fecha_referencia.month
        
        # Obtener siguiente secuencia para el mes
        result = session.execute(
            text("""
                SELECT COUNT(*) + 1 as siguiente
                FROM liquidacion 
                WHERE YEAR(fecha_creacion) = :anio 
                  AND MONTH(fecha_creacion) = :mes
            """),
            {"anio": anio, "mes": mes}
        ).scalar()
        
        secuencia = result or 1
        consecutivo = f"{prefijo}{anio}{mes:02d}{secuencia:04d}"
        
        return consecutivo
        
    except Exception as e:
        logger.error(f"Error generando consecutivo: {e}")
        # Usar consecutivo por defecto si hay error
        return f"LIQ-{datetime.now().strftime('%Y%m%d%H%M%S')}"

def obtener_liquidaciones_entidad(session, entidad_nit: str, limite: int = 10) -> list:
    """
    Obtiene las liquidaciones más recientes de una entidad.
    """
    try:
        result = session.execute(
            text("""
                SELECT 
                    l.liquidacion_id,
                    l.nombre as entidad_nombre,
                    l.identificacion as entidad_nit,
                    l.periodo_inicio,
                    l.periodo_fin,
                    l.capital,
                    l.interes,
                    l.total,
                    l.estado,
                    l.fecha_creacion,
                    l.fecha_actualizacion,
                    COUNT(ld.detalle_id) as total_pensionados
                FROM liquidacion l
                LEFT JOIN liquidacion_detalle ld ON l.liquidacion_id = ld.liquidacion_id
                WHERE l.identificacion = :nit
                GROUP BY l.liquidacion_id
                ORDER BY l.fecha_creacion DESC
                LIMIT :limite
            """),
            {"nit": entidad_nit, "limite": limite}
        ).fetchall()
        
        return [dict(row._mapping) for row in result]
        
    except Exception as e:
        logger.error(f"Error obteniendo liquidaciones de entidad {entidad_nit}: {e}")
        return []

def obtener_detalle_liquidacion(session, liquidacion_id: int) -> list:
    """
    Obtiene el detalle completo de una liquidación.
    """
    try:
        result = session.execute(
            text("""
                SELECT 
                    ld.detalle_id,
                    ld.pensionado_id,
                    p.identificacion,
                    p.nombre,
                    ld.periodo,
                    ld.capital,
                    ld.interes,
                    ld.total
                FROM liquidacion_detalle ld
                JOIN pensionado p ON ld.pensionado_id = p.pensionado_id
                WHERE ld.liquidacion_id = :liquidacion_id
                ORDER BY p.nombre
            """),
            {"liquidacion_id": liquidacion_id}
        ).fetchall()
        
        return [dict(row._mapping) for row in result]
        
    except Exception as e:
        logger.error(f"Error obteniendo detalle de liquidación {liquidacion_id}: {e}")
        return []
