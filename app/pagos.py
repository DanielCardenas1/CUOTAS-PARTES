# Objetivo (Copilot): registrar y aplicar pagos a liquidaciones
# Objetivo (Copilot): Registrar pago y (opcional) prorratear sobre detalles por antigüedad.
# Si deseas orden capital->interés, aplícalo en tu lógica.

from datetime import date, datetime
from sqlalchemy import text
from decimal import Decimal, ROUND_DOWN
import logging

logger = logging.getLogger(__name__)

def registrar_pago(session, pensionado_id: int, fecha_pago: date, valor_pagado: float, 
                  observaciones: str = None) -> int:
    """
    Registra un pago de un pensionado y calcula la distribución entre capital e intereses.
    
    Args:
        session: Sesión de SQLAlchemy
        pensionado_id: ID del pensionado que realiza el pago
        fecha_pago: Fecha del pago
        valor_pagado: Valor total pagado
        observaciones: Observaciones del pago
        
    Returns:
        ID del pago creado
    """
    try:
        # Obtener información del pensionado
        pensionado = session.execute(
            text("""
                SELECT identificacion, nombre, capital_pendiente, intereses_pendientes
                FROM pensionado 
                WHERE pensionado_id = :pensionado_id
            """),
            {"pensionado_id": pensionado_id}
        ).fetchone()
        
        if not pensionado:
            raise ValueError(f"Pensionado con ID {pensionado_id} no encontrado")
        
        valor_decimal = Decimal(str(valor_pagado))
        capital_pendiente = Decimal(str(pensionado.capital_pendiente or 0))
        intereses_pendientes = Decimal(str(pensionado.intereses_pendientes or 0))
        
        # Calcular distribución del pago (primero intereses, luego capital)
        valor_interes, valor_capital = calcular_distribucion_pago(
            valor_decimal, capital_pendiente, intereses_pendientes
        )
        
        # Insertar el pago
        result = session.execute(
            text("""
                INSERT INTO pago (
                    pensionado_id, fecha_pago, valor, capital, interes, observaciones
                ) VALUES (
                    :pensionado_id, :fecha_pago, :valor, :capital, :interes, :observaciones
                )
            """),
            {
                "pensionado_id": pensionado_id,
                "fecha_pago": fecha_pago,
                "valor": valor_decimal,
                "capital": valor_capital,
                "interes": valor_interes,
                "observaciones": observaciones
            }
        )
        
        pago_id = result.lastrowid
        
        # Actualizar saldos del pensionado
        actualizar_saldos_pensionado(
            session, pensionado_id, valor_capital, valor_interes, fecha_pago
        )
        
        session.commit()
        
        logger.info(f"Pago registrado: ID={pago_id}, Pensionado={pensionado.identificacion}, "
                   f"Valor=${valor_decimal:.2f}, Capital=${valor_capital:.2f}, "
                   f"Interés=${valor_interes:.2f}")
        
        return pago_id
        
    except Exception as e:
        logger.error(f"Error registrando pago: {e}")
        session.rollback()
        raise

def calcular_distribucion_pago(valor_pago: Decimal, capital_pendiente: Decimal, 
                              intereses_pendientes: Decimal) -> tuple[Decimal, Decimal]:
    """
    Calcula cómo distribuir un pago entre capital e intereses.
    Prioridad: Primero intereses, luego capital.
    
    Returns:
        Tuple (valor_interes, valor_capital)
    """
    valor_interes = Decimal('0.00')
    valor_capital = Decimal('0.00')
    valor_restante = valor_pago
    
    # Aplicar primero a intereses
    if intereses_pendientes > 0 and valor_restante > 0:
        valor_interes = min(valor_restante, intereses_pendientes)
        valor_restante -= valor_interes
    
    # Aplicar el resto a capital
    if capital_pendiente > 0 and valor_restante > 0:
        valor_capital = min(valor_restante, capital_pendiente)
        valor_restante -= valor_capital
    
    # Si sobra dinero después de cubrir todo, se considera abono a capital
    if valor_restante > 0:
        valor_capital += valor_restante
    
    return valor_interes, valor_capital

def actualizar_saldos_pensionado(session, pensionado_id: int, abono_capital: Decimal, 
                                abono_interes: Decimal, fecha_pago: date):
    """
    Actualiza los saldos pendientes del pensionado después de un pago.
    """
    try:
        session.execute(
            text("""
                UPDATE pensionado 
                SET 
                    capital_pendiente = GREATEST(0, capital_pendiente - :abono_capital),
                    intereses_pendientes = GREATEST(0, intereses_pendientes - :abono_interes),
                    ultima_fecha_pago = :fecha_pago
                WHERE pensionado_id = :pensionado_id
            """),
            {
                "pensionado_id": pensionado_id,
                "abono_capital": abono_capital,
                "abono_interes": abono_interes,
                "fecha_pago": fecha_pago
            }
        )
        
        logger.debug(f"Saldos actualizados para pensionado {pensionado_id}: "
                    f"Abono capital=${abono_capital:.2f}, Abono interés=${abono_interes:.2f}")
        
    except Exception as e:
        logger.error(f"Error actualizando saldos del pensionado {pensionado_id}: {e}")
        raise

def registrar_pago_masivo(session, entidad_nit: str, fecha_pago: date, 
                         archivo_pagos: list, observaciones: str = None) -> dict:
    """
    Registra múltiples pagos de una entidad desde un archivo o lista.
    
    Args:
        session: Sesión de SQLAlchemy
        entidad_nit: NIT de la entidad
        fecha_pago: Fecha común de los pagos
        archivo_pagos: Lista de diccionarios con identificacion y valor
        observaciones: Observaciones generales
        
    Returns:
        Diccionario con resumen del proceso
    """
    try:
        pagos_exitosos = 0
        pagos_fallidos = 0
        total_procesado = Decimal('0.00')
        errores = []
        
        for item in archivo_pagos:
            try:
                identificacion = item.get('identificacion')
                valor = Decimal(str(item.get('valor', 0)))
                
                if valor <= 0:
                    errores.append(f"Identificación {identificacion}: Valor inválido")
                    pagos_fallidos += 1
                    continue
                
                # Buscar pensionado
                pensionado = session.execute(
                    text("""
                        SELECT pensionado_id 
                        FROM pensionado 
                        WHERE identificacion = :identificacion 
                          AND nit_entidad = :nit_entidad
                    """),
                    {"identificacion": identificacion, "nit_entidad": entidad_nit}
                ).fetchone()
                
                if not pensionado:
                    errores.append(f"Identificación {identificacion}: Pensionado no encontrado")
                    pagos_fallidos += 1
                    continue
                
                # Registrar pago individual
                pago_id = registrar_pago(
                    session, 
                    pensionado.pensionado_id, 
                    fecha_pago, 
                    float(valor),
                    f"{observaciones} - Lote masivo" if observaciones else "Pago masivo"
                )
                
                pagos_exitosos += 1
                total_procesado += valor
                
            except Exception as e:
                errores.append(f"Identificación {identificacion}: {str(e)}")
                pagos_fallidos += 1
                continue
        
        resultado = {
            'pagos_exitosos': pagos_exitosos,
            'pagos_fallidos': pagos_fallidos,
            'total_procesado': float(total_procesado),
            'errores': errores
        }
        
        logger.info(f"Procesamiento masivo completado: {pagos_exitosos} exitosos, "
                   f"{pagos_fallidos} fallidos, Total=${total_procesado:.2f}")
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error en procesamiento masivo: {e}")
        session.rollback()
        raise

def obtener_historial_pagos(session, pensionado_id: int = None, entidad_nit: str = None, 
                           fecha_desde: date = None, fecha_hasta: date = None, 
                           limite: int = 50) -> list:
    """
    Obtiene el historial de pagos con filtros opcionales.
    """
    try:
        condiciones = []
        parametros = {}
        
        if pensionado_id:
            condiciones.append("p.pensionado_id = :pensionado_id")
            parametros["pensionado_id"] = pensionado_id
        
        if entidad_nit:
            condiciones.append("pen.nit_entidad = :entidad_nit")
            parametros["entidad_nit"] = entidad_nit
        
        if fecha_desde:
            condiciones.append("p.fecha_pago >= :fecha_desde")
            parametros["fecha_desde"] = fecha_desde
        
        if fecha_hasta:
            condiciones.append("p.fecha_pago <= :fecha_hasta")
            parametros["fecha_hasta"] = fecha_hasta
        
        where_clause = "WHERE " + " AND ".join(condiciones) if condiciones else ""
        
        query = f"""
            SELECT 
                p.pago_id,
                p.pensionado_id,
                pen.identificacion,
                pen.nombre,
                pen.nit_entidad,
                p.fecha_pago,
                p.valor,
                p.capital,
                p.interes,
                p.observaciones,
                p.fecha_creacion
            FROM pago p
            JOIN pensionado pen ON p.pensionado_id = pen.pensionado_id
            {where_clause}
            ORDER BY p.fecha_pago DESC, p.fecha_creacion DESC
            LIMIT :limite
        """
        
        parametros["limite"] = limite
        
        result = session.execute(text(query), parametros).fetchall()
        
        return [dict(row._mapping) for row in result]
        
    except Exception as e:
        logger.error(f"Error obteniendo historial de pagos: {e}")
        return []

def obtener_resumen_pagos_entidad(session, entidad_nit: str, 
                                 fecha_desde: date = None, fecha_hasta: date = None) -> dict:
    """
    Obtiene un resumen de pagos por entidad en un período.
    """
    try:
        condiciones = ["pen.nit_entidad = :entidad_nit"]
        parametros = {"entidad_nit": entidad_nit}
        
        if fecha_desde:
            condiciones.append("p.fecha_pago >= :fecha_desde")
            parametros["fecha_desde"] = fecha_desde
        
        if fecha_hasta:
            condiciones.append("p.fecha_pago <= :fecha_hasta")
            parametros["fecha_hasta"] = fecha_hasta
        
        where_clause = "WHERE " + " AND ".join(condiciones)
        
        query = f"""
            SELECT 
                COUNT(*) as total_pagos,
                SUM(p.valor) as total_valor,
                SUM(p.capital) as total_capital,
                SUM(p.interes) as total_interes,
                COUNT(DISTINCT p.pensionado_id) as pensionados_pagaron,
                MIN(p.fecha_pago) as fecha_primer_pago,
                MAX(p.fecha_pago) as fecha_ultimo_pago
            FROM pago p
            JOIN pensionado pen ON p.pensionado_id = pen.pensionado_id
            {where_clause}
        """
        
        result = session.execute(text(query), parametros).fetchone()
        
        if result:
            return dict(result._mapping)
        else:
            return {
                'total_pagos': 0,
                'total_valor': 0,
                'total_capital': 0,
                'total_interes': 0,
                'pensionados_pagaron': 0,
                'fecha_primer_pago': None,
                'fecha_ultimo_pago': None
            }
        
    except Exception as e:
        logger.error(f"Error obteniendo resumen de pagos: {e}")
        return {}
