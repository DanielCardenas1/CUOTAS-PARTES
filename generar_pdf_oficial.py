#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generador de PDF formato oficial - Liquidación de Cuotas Partes
Crea un PDF profesional con formato exacto al documento oficial
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date, datetime
import argparse
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas

# Importar funciones del sistema funcionando
from mostrar_liquidacion_36 import generar_36_cuentas_pensionado, generar_36_cuentas_pensionado_oct, generar_36_cuentas_pensionado_custom
from app.db import get_session, engine
from sqlalchemy import text
from sqlalchemy import select, func
from app.models import Base, CuentaCobro

# --- Gestión de consecutivo en base de datos (tabla cuenta_cobro) ---
CONSEC_OVERRIDE = None  # --consecutivo
CONSEC_CORRECCION = False  # --correccion

_cuenta_table_ready = False

def _ensure_cuenta_table():
    global _cuenta_table_ready
    if _cuenta_table_ready:
        return
    try:
        # Crear solo la tabla de cuenta_cobro si no existe
        Base.metadata.create_all(engine, tables=[CuentaCobro.__table__])
    except Exception:
        # Si falla, lo ignoramos para no interrumpir (puede existir ya)
        pass
    _cuenta_table_ready = True

def _db_get_next_consecutivo(session):
    max_val = session.execute(select(func.max(CuentaCobro.consecutivo))).scalar()
    return (max_val or 0) + 1

def _db_find_existing(session, nit_entidad, identificacion, fecha_inicio, fecha_fin):
    return session.execute(
        select(CuentaCobro).where(
            CuentaCobro.nit_entidad == str(nit_entidad),
            CuentaCobro.pensionado_identificacion == str(identificacion),
            CuentaCobro.periodo_inicio == fecha_inicio,
            CuentaCobro.periodo_fin == fecha_fin
        ).order_by(CuentaCobro.fecha_creacion.desc())
    ).scalars().first()

def _ensure_unique_filename(base_name: str) -> str:
    """If base_name exists or is locked, return a variant with a numeric suffix or timestamp."""
    if not os.path.exists(base_name):
        return base_name
    # try adding _v3, _v4, ... up to reasonable limit
    base, ext = os.path.splitext(base_name)
    for i in range(3, 100):
        candidate = f"{base}_v{i}{ext}"
        if not os.path.exists(candidate):
            return candidate
    # fallback to timestamp
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{base}_{ts}{ext}"

def generar_pdf_para_pensionado(pensionado, periodo='sep', año_inicio=None, mes_inicio=None):
    """Genera un PDF para un pensionado ya consultado.

    Espera una tupla en el siguiente orden (para compatibilidad con mostrar_liquidacion_36):
    (0) identificacion, (1) nombre, (2) numero_mesadas, (3) fecha_ingreso_nomina,
    (4) empresa, (5) base_calculo_cuota_parte, (6) porcentaje_cuota_parte, (7) nit_entidad (opcional)
    
    Args:
        pensionado: Tupla con datos del pensionado
        periodo: 'sep' para Sep 2022-Ago 2025, 'oct' para Oct 2022-Ago 2025, 'custom' para personalizado
        año_inicio: Año de inicio para período custom
        mes_inicio: Mes de inicio para período custom
    """
    # Generar datos usando el sistema funcionando según el período
    fecha_corte = date(2025, 8, 31)  # Última fecha válida (agosto 2025)
    
    if periodo == 'oct':
        cuentas = generar_36_cuentas_pensionado_oct(pensionado, fecha_corte)
    elif periodo == 'custom':
        if año_inicio is None or mes_inicio is None:
            raise ValueError("Para período 'custom' se requieren --año-inicio y --mes-inicio")
        
        # Para período custom, calcular hasta la fecha de corte válida (no 36 meses fijos)
        fecha_inicio = date(año_inicio, mes_inicio, 1)
        # Si la fecha de inicio es posterior al corte, error
        if fecha_inicio > fecha_corte:
            raise ValueError(f"La fecha de inicio ({fecha_inicio}) no puede ser posterior a agosto 2025")
        
        # Calcular número de meses desde inicio hasta fecha_corte
        from dateutil.relativedelta import relativedelta
        meses_disponibles = (fecha_corte.year - fecha_inicio.year) * 12 + (fecha_corte.month - fecha_inicio.month) + 1
        
        cuentas = generar_36_cuentas_pensionado_custom(pensionado, año_inicio, mes_inicio, fecha_corte, meses_disponibles)
    else:
        cuentas = generar_36_cuentas_pensionado(pensionado, fecha_corte)
    
    # Calcular totales: para presentación masiva queremos mostrar el capital
    # adeudado como el capital base (único), no la suma de los 36 meses.
    # El interés sí se acumula (suma de intereses mensuales).
    if cuentas:
        capital_unico = cuentas[0].get('capital_base', cuentas[0].get('capital', 0))
    else:
        capital_unico = 0.0
    total_capital = capital_unico
    total_intereses = sum(c['interes'] for c in cuentas)
    total_final = total_capital + total_intereses
    
    # Obtener período real de las cuentas
    if cuentas:
        fecha_inicio = cuentas[0]['fecha_cuenta']  # Primera fecha
        fecha_fin = cuentas[-1]['fecha_cuenta']   # Última fecha
        
        # Convertir fechas a formato de texto en español
        meses_es = {
            1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
            5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO',
            9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
        }
        
        mes_inicio = meses_es[fecha_inicio.month]
        año_inicio = fecha_inicio.year
        mes_fin = meses_es[fecha_fin.month]
        año_fin = fecha_fin.year
        
        periodo_texto = f'{mes_inicio} DEL {año_inicio} A {mes_fin} DEL {año_fin}'
    else:
        periodo_texto = 'PERÍODO NO DISPONIBLE'
    
    # Crear archivo PDF con nombre único para evitar PermissionError
    base_name = f"LIQUIDACION_CUOTAS_PARTES_{pensionado[0]}_{date.today().strftime('%Y%m%d')}_v2.pdf"
    nombre_archivo = _ensure_unique_filename(base_name)
    
    # Configurar documento con márgenes más estrechos
    doc = SimpleDocTemplate(
        nombre_archivo,
        pagesize=A4,
        rightMargin=0.5*cm,
        leftMargin=0.5*cm,
        topMargin=1*cm,
        bottomMargin=1*cm
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilo para título principal
    titulo_style = ParagraphStyle(
        'TituloCustom',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=12,
        alignment=TA_CENTER,
        textColor=colors.black,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulo
    subtitulo_style = ParagraphStyle(
        'SubtituloCustom',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=16,
        alignment=TA_CENTER,
        textColor=colors.black,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para información
    info_style = ParagraphStyle(
        'InfoCustom',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        alignment=TA_LEFT,
        textColor=colors.black,
        fontName='Helvetica'
    )
    
    # Estilo para totales
    total_style = ParagraphStyle(
        'TotalCustom',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        alignment=TA_LEFT,
        textColor=colors.black,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para encabezado
    encabezado_style = ParagraphStyle(
        'EncabezadoCustom',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=8,
        alignment=TA_LEFT,
        textColor=colors.black,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para cuenta de cobro (alineado a la derecha)
    cuenta_cobro_style = ParagraphStyle(
        'CuentaCobroCustom',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=8,
        alignment=TA_RIGHT,
        textColor=colors.black,
        fontName='Helvetica-Bold'
    )
    
    # Construir contenido del PDF según formato de la imagen
    story = []
    
    # ENCABEZADO CON CIUDAD Y CONSECUTIVO (gestión en BD)
    _ensure_cuenta_table()
    # Fechas de periodo para registro
    periodo_inicio_fecha = cuentas[0]['fecha_cuenta'] if cuentas else date(2022, 9, 1)
    periodo_fin_fecha = cuentas[-1]['fecha_cuenta'] if cuentas else date(2025, 8, 31)
    nit_text = str(pensionado[7]) if len(pensionado) > 7 and pensionado[7] else 'N/D'
    # Calcular/obtener consecutivo
    with get_session() as s:
        existente = _db_find_existing(s, nit_text, pensionado[0], periodo_inicio_fecha, periodo_fin_fecha)
        consecutivo_cc = None
        if CONSEC_OVERRIDE is not None:
            consecutivo_cc = int(CONSEC_OVERRIDE)
        elif CONSEC_CORRECCION and existente is not None:
            consecutivo_cc = existente.consecutivo
        else:
            # Nuevo consecutivo global
            consecutivo_cc = _db_get_next_consecutivo(s)
        
        # Crear o actualizar registro de trazabilidad
        ahora = datetime.now()
        pdf_name_preview = f"LIQUIDACION_CUOTAS_PARTES_{pensionado[0]}_{date.today().strftime('%Y%m%d')}_v2.pdf"
        if existente is None:
            reg = CuentaCobro(
                consecutivo=consecutivo_cc,
                nit_entidad=nit_text,
                empresa=pensionado[4],
                pensionado_identificacion=str(pensionado[0]),
                pensionado_nombre=pensionado[1],
                periodo_inicio=periodo_inicio_fecha,
                periodo_fin=periodo_fin_fecha,
                total_capital=total_capital,
                total_intereses=total_intereses,
                total_liquidacion=total_final,
                archivo_pdf=pdf_name_preview,
                estado='EMITIDA' if CONSEC_OVERRIDE is None else 'EMITIDA_MANUAL',
                version=1,
                fecha_creacion=ahora,
                fecha_actualizacion=ahora,
            )
            s.add(reg)
            s.commit()
        else:
            # Existe mismo periodo; si corrección, solo actualizamos totales;
            # si no es corrección y no se forzó, incrementamos versión y creamos nueva entrada con nuevo consecutivo
            if CONSEC_CORRECCION and CONSEC_OVERRIDE is None:
                existente.total_capital = total_capital
                existente.total_intereses = total_intereses
                existente.total_liquidacion = total_final
                existente.archivo_pdf = pdf_name_preview
                existente.estado = 'CORREGIDA'
                existente.fecha_actualizacion = ahora
                s.commit()
                consecutivo_cc = existente.consecutivo
            else:
                reg = CuentaCobro(
                    consecutivo=consecutivo_cc,
                    nit_entidad=nit_text,
                    empresa=pensionado[4],
                    pensionado_identificacion=str(pensionado[0]),
                    pensionado_nombre=pensionado[1],
                    periodo_inicio=periodo_inicio_fecha,
                    periodo_fin=periodo_fin_fecha,
                    total_capital=total_capital,
                    total_intereses=total_intereses,
                    total_liquidacion=total_final,
                    archivo_pdf=pdf_name_preview,
                    estado='EMITIDA',
                    version=(existente.version or 1) + 1,
                    fecha_creacion=ahora,
                    fecha_actualizacion=ahora,
                )
                s.add(reg)
                s.commit()
    encabezado_data = [
        [Paragraph('BOGOTA, D.C.', encabezado_style), 
        Paragraph(f'CUENTA DE COBRO<br/>Nro. {consecutivo_cc}', cuenta_cobro_style)]
    ]
    
    tabla_encabezado = Table(encabezado_data, colWidths=[7*cm, 7*cm])
    tabla_encabezado.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(tabla_encabezado)
    story.append(Spacer(1, 0.5*cm))
    
    # INFORMACIÓN COMPLETA (ENTIDAD + PENSIONADO)
    # Calcular el ancho total de las otras tablas para que coincidan
    ancho_total_otras_tablas = 2.5*cm + 2.5*cm + 2*cm + 2.5*cm + 2*cm + 2.5*cm  # Total: 14cm

    nit_text = str(pensionado[7]) if len(pensionado) > 7 and pensionado[7] else 'N/D'
    info_superior = [
        ['Entidad', f'{pensionado[4]} - NIT. {nit_text}'],
        ['Período', f'CUOTAS PARTES POR COBRAR {periodo_texto}'],
        ['Nombre', f'{pensionado[1]}'],
        ['Identificación', f'{pensionado[0]}']
    ]
    
    # Solo agregar filas de sustituto si tienen datos
    sustituto_nombre = ''  # Aquí puedes obtener el dato del sustituto si existe
    sustituto_identificacion = ''  # Aquí puedes obtener la identificación del sustituto si existe
    
    if sustituto_nombre and sustituto_nombre.strip():
        info_superior.append(['Sustituto', sustituto_nombre])
    
    if sustituto_identificacion and sustituto_identificacion.strip():
        info_superior.append(['Identificación', sustituto_identificacion])
    
    tabla_superior = Table(info_superior, colWidths=[3*cm, ancho_total_otras_tablas - 3*cm])
    tabla_superior.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    
    story.append(tabla_superior)
    story.append(Spacer(1, 0.3*cm))
    
    # TABLA DE RESUMEN INTERMEDIA
    resumen_data = [
        ['Ingreso a Nómina', '% Cuota Parte', 'Estado', 'Capital pendiente', 'Interes acumulado', 'Total'],
        ['01/05/2008', '36.10%', 'ACTIVO', f'${total_capital:,.2f}', f'${total_intereses:,.2f}', f'${total_final:,.2f}']
    ]
    
    tabla_resumen = Table(resumen_data, colWidths=[2.3*cm, 2.3*cm, 2.3*cm, 2.3*cm, 2.4*cm, 2.4*cm])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('BACKGROUND', (2, 1), (2, 1), colors.green),  # Estado en posición 2
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    
    story.append(tabla_resumen)
    story.append(Spacer(1, 0.3*cm))
    
    # TÍTULO DE LA SECCIÓN DE INTERESES
    titulo_intereses = f"""
    <b>JULIO 29/2006 - Art. 4 Ley 1066/2006 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; CON INTERESES DTF</b>
    """
    
    story.append(Paragraph(titulo_intereses, ParagraphStyle('TituloIntereses', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold')))
    story.append(Spacer(1, 0.2*cm))
    
    # Estilo para cabeceras con texto ajustado
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=7,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        leading=8,
        spaceAfter=0,
        spaceBefore=0
    )
    
    # Cabeceras de la tabla usando Paragraph para ajuste automático de texto
    headers = [
        Paragraph('PERÍODO', header_style),
        Paragraph('Vr. Cuota parte periodo', header_style),
        Paragraph('Días', header_style),
        Paragraph('DTF EA', header_style),
        Paragraph('Valor Intereses', header_style),
        Paragraph('Capital', header_style)
    ]
    
    # Datos de la tabla
    table_data = [headers]
    
    # Estilos para celdas de datos
    data_style_left = ParagraphStyle('DataLeft', parent=styles['Normal'], fontSize=6, fontName='Helvetica', alignment=TA_LEFT, leading=7)
    data_style_center = ParagraphStyle('DataCenter', parent=styles['Normal'], fontSize=6, fontName='Helvetica', alignment=TA_CENTER, leading=7)
    data_style_right = ParagraphStyle('DataRight', parent=styles['Normal'], fontSize=6, fontName='Helvetica', alignment=TA_RIGHT, leading=7)
    
    meses_nombres = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                     "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    
    for cuenta in cuentas:
        mes_nombre = meses_nombres[cuenta['mes'] - 1]
        año = cuenta['año']
        
        # Mostrar en la tabla el capital base (no duplicado). El interés se
        # calcula sobre el capital que incluye la prima cuando corresponde, pero
        # para la presentación individual queremos siempre mostrar el capital base.
        valor_cuota_periodo = cuenta.get('capital_base', cuenta.get('capital', 0))
        
        fila = [
            Paragraph(f"{mes_nombre.capitalize()}-{año}", data_style_left),
            Paragraph(f"${valor_cuota_periodo:,.2f}", data_style_right),
            Paragraph(f"{cuenta['dias_interes']:d}", data_style_center),
            Paragraph(f"{cuenta['dtf_interes']:.2f}%", data_style_center),
            Paragraph(f"${cuenta['interes']:,.2f}", data_style_right),
            # Mostrar capital base en la columna final (no duplicado)
            Paragraph(f"${cuenta.get('capital_base', cuenta.get('capital', 0)):,.2f}", data_style_right)
        ]
        table_data.append(fila)
    
    # Estilo para fila de totales
    total_style_center = ParagraphStyle('TotalCenter', parent=styles['Normal'], fontSize=7, fontName='Helvetica-Bold', alignment=TA_CENTER, leading=8)
    total_style_right = ParagraphStyle('TotalRight', parent=styles['Normal'], fontSize=7, fontName='Helvetica-Bold', alignment=TA_RIGHT, leading=8)
    
    # Calcular total de cuota parte periodo usando siempre el capital base
    total_cuota_parte_periodo = sum(c.get('capital_base', c.get('capital', 0)) for c in cuentas)
    
    # Fila de totales (mostrar intereses sumados; mostrar capital como capital único)
    fila_totales = [
        Paragraph("TOTAL", total_style_center),
        Paragraph(f"${total_cuota_parte_periodo:,.2f}", total_style_right),
        Paragraph("", total_style_center),
        Paragraph("", total_style_center),
        Paragraph(f"${total_intereses:,.2f}", total_style_right),
        Paragraph(f"${total_capital:,.2f}", total_style_right)
    ]
    table_data.append(fila_totales)
    
    # Crear tabla con 6 columnas (eliminada la redundante)
    col_widths = [2.5*cm, 2.5*cm, 1.2*cm, 1.8*cm, 2.3*cm, 2.7*cm]
    tabla = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    # Estilo de la tabla
    tabla.setStyle(TableStyle([
        # Cabecera
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        
        # Datos
        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'), # Alineación vertical centrada
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.lightgrey]),
        
        # Fila de totales
        ('BACKGROUND', (0, -1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
        ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, -1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 4),
        
        # Bordes
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        
        # Padding general reducido
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 1), (-1, -2), 2),
        ('BOTTOMPADDING', (0, 1), (-1, -2), 2),
    ]))
    
    story.append(tabla)
    
    # Generar PDF
    doc.build(story)
    
    print(f"✅ PDF creado exitosamente: {nombre_archivo}")
    print(f"🧾 Cuenta de cobro Nro.: {consecutivo_cc}")
    print(f"📊 Total capital: ${total_capital:,.2f}")
    print(f"💰 Total intereses: ${total_intereses:,.2f}")
    print(f"🎯 Total liquidación: ${total_final:,.2f}")
    print(f"\n📋 Características del PDF:")
    print(f"   - Formato: A4 profesional")
    print(f"   - Pensionado: {pensionado[1]}")
    print(f"   - Identificación: {pensionado[0]}")
    print(f"   - Período: {periodo_texto} ({len(cuentas)} meses)")
    print(f"   - Tabla completa con DTF y días por mes")
    print(f"   - Resumen ejecutivo y notas técnicas")
    
    return nombre_archivo


def crear_pdf_formato_oficial():
    """Crea PDFs en modo individual (por defecto) o en lote por NIT/ID."""
    parser = argparse.ArgumentParser(description='Generar PDF(s) de liquidación de cuotas partes')
    parser.add_argument('--id', dest='identificacion', help='Identificación del pensionado (solo uno)')
    parser.add_argument('--nit', dest='nit_entidad', help='NIT de la entidad para procesar todos sus pensionados')
    parser.add_argument('--consecutivo', dest='consecutivo', type=int, help='Forzar Nro. de cuenta de cobro (no incrementa archivo)')
    parser.add_argument('--correccion', dest='correccion', action='store_true', help='Usar el último consecutivo sin incrementar')
    parser.add_argument('--periodo', dest='periodo', choices=['sep', 'oct', 'custom'], default='sep', help='Período inicial: sep (Sep 2022-Ago 2025), oct (Oct 2022-Ago 2025), o custom (usar --año-inicio y --mes-inicio)')
    parser.add_argument('--año-inicio', dest='año_inicio', type=int, help='Año de inicio para período custom (ej: 2023)')
    parser.add_argument('--mes-inicio', dest='mes_inicio', type=int, choices=range(1,13), help='Mes de inicio para período custom (1-12)')
    args, unknown = parser.parse_known_args()

    # Configurar flags globales de consecutivo
    global CONSEC_OVERRIDE, CONSEC_CORRECCION
    CONSEC_OVERRIDE = args.consecutivo
    CONSEC_CORRECCION = args.correccion

    # Caso 1: Procesar por NIT (lote)
    if args.nit_entidad:
        session = get_session()
        try:
            query = text('''SELECT identificacion, nombre, numero_mesadas,
                            fecha_ingreso_nomina, empresa, base_calculo_cuota_parte,
                            porcentaje_cuota_parte, nit_entidad
                            FROM pensionado WHERE nit_entidad = :nit
                            ORDER BY nombre''')
            results = session.execute(query, {'nit': args.nit_entidad}).fetchall()
            if not results:
                print(f"❌ No se encontraron pensionados para la entidad NIT {args.nit_entidad}")
                return
            print(f"🔎 Procesando {len(results)} pensionados de la entidad NIT {args.nit_entidad}...")
            for idx, pensionado in enumerate(results, 1):
                print(f"\n[{idx}/{len(results)}] Generando PDF para: {pensionado[1]} (ID: {pensionado[0]})")
                try:
                    generar_pdf_para_pensionado(pensionado, args.periodo, args.año_inicio, args.mes_inicio)
                except Exception as e:
                    print(f"   ⚠️ Error generando PDF para {pensionado[1]} ({pensionado[0]}): {e}")
            print("\n✅ Proceso por entidad finalizado")
            return
        finally:
            session.close()

    # Caso 2: Procesar por identificación (individual)
    if args.identificacion:
        session = get_session()
        try:
            query = text('''SELECT identificacion, nombre, numero_mesadas, 
                            fecha_ingreso_nomina, empresa, base_calculo_cuota_parte,
                            porcentaje_cuota_parte, nit_entidad
                            FROM pensionado WHERE identificacion = :id LIMIT 1''')
            result = session.execute(query, {'id': args.identificacion}).fetchone()
            if not result:
                print(f"❌ No se encontró pensionado con ID {args.identificacion}")
                return
            print(f"✅ Pensionado encontrado: {result[1]} ({result[0]})")
            generar_pdf_para_pensionado(result, args.periodo, args.año_inicio, args.mes_inicio)
            return
        finally:
            session.close()

    # Caso 3: Sin argumentos -> comportamiento anterior (ejemplo por defecto)
    session = get_session()
    try:
        query = text('''SELECT identificacion, nombre, numero_mesadas, 
                        fecha_ingreso_nomina, empresa, base_calculo_cuota_parte,
                        porcentaje_cuota_parte, nit_entidad
                        FROM pensionado WHERE identificacion = '26489799' ''')
        result = session.execute(query).fetchone()
        if not result:
            print("❌ No se encontró pensionado con ID 26489799")
            return
        print(f"✅ Pensionado encontrado: {result[1]} ({result[0]})")
        generar_pdf_para_pensionado(result, args.periodo, args.año_inicio, args.mes_inicio)
    finally:
        session.close()

if __name__ == "__main__":
    crear_pdf_formato_oficial()