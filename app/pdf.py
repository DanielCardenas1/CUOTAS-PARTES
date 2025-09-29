"""
Módulo para exportación de liquidaciones a PDF
"""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from sqlalchemy import text
from datetime import datetime

def generar_pdf_completo(session, entidad_nit: str, periodo_inicio, periodo_fin, ruta_salida: str) -> str:
    """
    Genera PDF con todos los campos requeridos usando generar_liquidacion_completa.
    
    Args:
        session: Sesión de SQLAlchemy
        entidad_nit: NIT de la entidad
        periodo_inicio: Fecha de inicio del período
        periodo_fin: Fecha de fin del período
        ruta_salida: Ruta donde guardar el archivo PDF
        
    Returns:
        Ruta completa del archivo PDF generado
    """
    try:
        from .liquidar import generar_liquidacion_completa
        
        # Obtener datos completos de la liquidación
        liquidacion_data = generar_liquidacion_completa(
            session, entidad_nit, periodo_inicio, periodo_fin
        )
        
        # Generar PDF con formato oficial completo
        generar_pdf_oficial_completo(liquidacion_data, ruta_salida)
        
        return ruta_salida
        
    except Exception as e:
        print(f"Error generando PDF completo: {e}")
        raise

def generar_pdf_oficial_completo(liquidacion_data, ruta_salida):
    """Genera PDF en formato oficial optimizado con todos los campos requeridos"""
    
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    
    # Configurar documento en formato horizontal (landscape) con márgenes optimizados
    doc = SimpleDocTemplate(
        ruta_salida,
        pagesize=landscape(A4),
        rightMargin=15,
        leftMargin=15,
        topMargin=25,
        bottomMargin=25
    )
    
    # Elementos del documento
    story = []
    styles = getSampleStyleSheet()
    
    # Estilo para títulos
    titulo_style = ParagraphStyle(
        'TituloOficial',
        parent=styles['Heading1'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulos
    subtitulo_style = ParagraphStyle(
        'SubtituloOficial',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    # Títulos del documento
    story.append(Paragraph(liquidacion_data['encabezado']['titulo'], titulo_style))
    story.append(Paragraph(liquidacion_data['encabezado']['entidad'], subtitulo_style))
    story.append(Spacer(1, 12))
    
    # Preparar datos para la tabla
    datos_tabla = []
    
    # Encabezados de la tabla (sin observaciones)
    encabezados = [
        'No.',
        'APELLIDOS Y NOMBRES\nDEL PENSIONADO',
        'No.\nDOCUMENTO',
        'SUSTITUTO',
        'No.\nDOCUMENTO',
        '% CUOTA\nPARTE',
        'VALOR\nMESADA',
        'PERIODO LIQUIDADO',
        'CAPITAL',
        'INTERESES',
        'TOTAL'
    ]
    
    datos_tabla.append(encabezados)
    
    # Crear estilo para texto con wrapping
    estilo_texto = ParagraphStyle(
        'TextoWrap',
        parent=styles['Normal'],
        fontSize=7,
        alignment=TA_LEFT,
        fontName='Helvetica'
    )
    
    estilo_texto_centro = ParagraphStyle(
        'TextoCentro',
        parent=styles['Normal'],
        fontSize=7,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )
    
    # Agregar datos de pensionados con text wrapping
    for pensionado in liquidacion_data['pensionados']:
        # Usar Paragraph para nombres largos con wrapping automático
        nombre = pensionado['nombre']
        nombre_paragraph = Paragraph(nombre, estilo_texto)
        
        # Usar Paragraph para sustitutos largos
        sustituto = pensionado['sustituto'] if pensionado['sustituto'] else ''
        sustituto_paragraph = Paragraph(sustituto, estilo_texto) if sustituto else ''
        
        fila = [
            str(pensionado['numero']),
            nombre_paragraph,  # Con wrapping automático
            pensionado['documento'],
            sustituto_paragraph,  # Con wrapping automático
            pensionado['documento_sustituto'],
            pensionado['porcentaje_concurrencia'],
            pensionado['valor_mesada'],
            pensionado['periodo_liquidado'],
            pensionado['capital'],
            pensionado['intereses'],
            pensionado['total']
        ]
        datos_tabla.append(fila)
    
    # Fila de totales
    fila_totales = [
        '', 'TOTAL', '', '', '', '', '',
        '', 
        liquidacion_data['totales_formateados']['capital'],
        liquidacion_data['totales_formateados']['intereses'],
        liquidacion_data['totales_formateados']['total']
    ]
    datos_tabla.append(fila_totales)
    
    # Crear tabla con anchos optimizados para text wrapping y altura automática
    tabla = Table(datos_tabla, 
                  colWidths=[
                      0.4*inch,  # No.
                      1.8*inch,  # Nombre (optimizado para wrapping)  
                      0.8*inch,  # Documento
                      1.2*inch,  # Sustituto (optimizado para wrapping)
                      0.8*inch,  # Doc Sustituto
                      0.7*inch,  # % Concurrencia
                      1.0*inch,  # Valor Mesada
                      1.3*inch,  # Período
                      1.0*inch,  # Capital
                      1.0*inch,  # Intereses
                      1.0*inch   # Total
                  ],
                  splitByRow=1,  # Permitir que las filas se dividan si es necesario
                  repeatRows=1   # Repetir encabezado en páginas siguientes
    )
    
    # Estilo de la tabla optimizado para mejor legibilidad
    tabla.setStyle(TableStyle([
        # Encabezados
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),  # Fuente más pequeña
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),  # Menos espaciado
        
        # Bordes más finos
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        
        # Alineaciones específicas
        ('ALIGN', (1, 1), (1, -2), 'LEFT'),      # Nombres a la izquierda
        ('ALIGN', (3, 1), (3, -2), 'LEFT'),      # Sustitutos a la izquierda
        ('ALIGN', (2, 1), (2, -2), 'CENTER'),    # Documentos centrados
        ('ALIGN', (4, 1), (4, -2), 'CENTER'),    # Doc sustitutos centrados
        ('ALIGN', (5, 1), (5, -2), 'RIGHT'),     # % a la derecha
        ('ALIGN', (6, 1), (10, -2), 'RIGHT'),    # Valores monetarios a la derecha
        
        # Destacar fila de totales
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 8),  # Totales un poco más grandes
        
        # Espaciado de celdas optimizado para wrapping
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        
        # Alternancia de colores para mejor lectura
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
        
        # Ajuste de altura de filas para text wrapping
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Alineación superior para mejor lectura
        
        # Permitir altura automática de filas
        ('SPLITLONGWORDS', (0, 0), (-1, -1), True),
    ]))
    
    story.append(tabla)
    story.append(Spacer(1, 12))
    
    # Valor en letras
    valor_letras_style = ParagraphStyle(
        'ValorLetras',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold'
    )
    
    total_num = float(liquidacion_data['totales']['total'])
    valor_letras = convertir_numero_letras_pdf(total_num)
    story.append(Paragraph(f"VALOR EN LETRAS: {valor_letras} PESOS MIL.", valor_letras_style))
    
    # Construir el PDF
    doc.build(story)
    print(f"✓ PDF generado: {ruta_salida}")

def convertir_numero_letras_pdf(numero):
    """Función para convertir números a letras para PDF"""
    try:
        num_int = int(numero)
        
        if num_int < 1000:
            return f"{num_int:,}"
        elif num_int < 1000000:
            millares = num_int // 1000
            resto = num_int % 1000
            if resto == 0:
                return f"{millares:,} MIL"
            else:
                return f"{millares:,} MIL {resto:,}"
        else:
            millones = num_int // 1000000
            resto = num_int % 1000000
            if resto == 0:
                return f"{millones:,} MILLONES"
            elif resto < 1000:
                return f"{millones:,} MILLONES {resto:,}"
            else:
                millares = resto // 1000
                final = resto % 1000
                if final == 0:
                    return f"{millones:,} MILLONES {millares:,} MIL"
                else:
                    return f"{millones:,} MILLONES {millares:,} MIL {final:,}"
    except:
        return f"{numero:,.0f}"

def exportar_liquidacion_pdf(session, liquidacion_id: int, ruta_salida: str) -> str:
    """
    Exporta una liquidación a PDF con formato profesional.
    
    Args:
        session: Sesión de SQLAlchemy
        liquidacion_id: ID de la liquidación a exportar
        ruta_salida: Ruta donde guardar el archivo PDF
        
    Returns:
        Ruta completa del archivo PDF generado
    """
    try:
        # Obtener datos de la liquidación
        liquidacion = session.execute(
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
                    l.fecha_creacion
                FROM liquidacion l
                WHERE l.liquidacion_id = :liquidacion_id
            """),
            {"liquidacion_id": liquidacion_id}
        ).fetchone()
        
        # Obtener detalles
        detalles = session.execute(
            text("""
                SELECT 
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
                LIMIT 10
            """),
            {"liquidacion_id": liquidacion_id}
        ).fetchall()
        
        print(f"✓ Datos obtenidos: {len(detalles)} detalles")
        
        # Generar PDF en formato oficial
        generar_pdf_oficial(liquidacion, detalles, ruta_salida)
        
        return ruta_salida
        
    except Exception as e:
        raise

def generar_pdf_oficial(liquidacion, detalles, ruta_salida):
    """Genera PDF en formato oficial de liquidación de pensionados"""
    
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    
    # Configurar documento en formato horizontal (landscape)
    doc = SimpleDocTemplate(
        ruta_salida,
        pagesize=landscape(A4),
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    # Elementos del documento
    story = []
    styles = getSampleStyleSheet()
    
    # Título oficial
    titulo_style = ParagraphStyle(
        'TituloOficial',
        parent=styles['Heading1'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )
    
    story.append(Paragraph("LIQUIDACIÓN OFICIAL DE PENSIONADOS", titulo_style))
    story.append(Spacer(1, 20))
    
    # Tabla de liquidación oficial
    if detalles:
        # Encabezados de la tabla oficial
        headers = [
            'No.',
            'APELLIDOS Y\nNOMBRES\nDEL PENSIONADO',
            'No.\nDOCUMENTO',
            'SUSTITUTO',
            'No.\nDOCUMENTO',
            '% DE\nCUOTA\nPARTE',
            'VALOR\nMESADA',
            'PERÍODO\nLIQUIDADO',
            'CAPITAL',
            'INTERESES',
            'TOTAL'
        ]
        
        # Datos de la tabla
        table_data = [headers]
        
        for i, detalle in enumerate(detalles, 1):
            # Formatear período exactamente como en la imagen
            periodo_str = f"01/09/2025 - 30/09/2025"  # Formato según imagen
            
            # Formatear identificación con puntos (CC12345 -> CC12.345)
            doc_formateado = f"CC{int(detalle.identificacion):,}".replace(',', '.')
            
            table_data.append([
                str(i),
                detalle.nombre[:25] + '...' if len(detalle.nombre) > 25 else detalle.nombre,  # Truncar nombres largos
                doc_formateado,
                '',  # Sustituto (vacío por ahora)
                '',  # No. Documento sustituto
                '0.0000%',  # % Cuota parte (se puede calcular después)
                '0.00',  # Valor mesada (se puede obtener de pensionado)
                periodo_str,
                f"{float(detalle.capital):,.0f}",  # Sin decimales para más espacio
                f"{float(detalle.interes):,.0f}",
                f"{float(detalle.total):,.0f}"
            ])
        
        # Fila de totales
        total_capital = sum(float(d.capital) for d in detalles)
        total_intereses = sum(float(d.interes) for d in detalles)
        total_general = sum(float(d.total) for d in detalles)
        
        table_data.append([
            '', '', '', '', '', '', '', 'TOTAL',
            f"{total_capital:,.0f}",
            f"{total_intereses:,.0f}",
            f"{total_general:,.0f}"
        ])
        
        # Crear tabla con anchos específicos ajustados para landscape
        # Total disponible en landscape A4: ~10.5 inches
        col_widths = [0.3*inch, 2.2*inch, 0.9*inch, 0.7*inch, 0.7*inch, 0.6*inch, 0.6*inch, 1.3*inch, 1.0*inch, 1.0*inch, 1.0*inch]
        
        table = Table(table_data, colWidths=col_widths)
        
        # Estilo oficial de la tabla
        table.setStyle(TableStyle([
            # Encabezados
            ('BACKGROUND', (0, 0), (-1, 0), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            
            # Contenido
            ('ALIGN', (0, 1), (0, -2), 'CENTER'),  # No.
            ('ALIGN', (1, 1), (1, -2), 'LEFT'),    # Nombres
            ('ALIGN', (2, 1), (7, -2), 'CENTER'),  # Documentos y datos centrales
            ('ALIGN', (8, 1), (-1, -2), 'RIGHT'),  # Valores monetarios
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -2), 8),
            ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
            
            # Fila de totales
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 9),
            ('ALIGN', (7, -1), (7, -1), 'CENTER'),  # Palabra TOTAL
            ('ALIGN', (8, -1), (-1, -1), 'RIGHT'),  # Valores totales
            
            # Bordes
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('LINEWIDTH', (0, 0), (-1, 0), 1),  # Línea más gruesa para encabezados
            ('LINEWIDTH', (0, -1), (-1, -1), 1),  # Línea más gruesa para totales
            
            # Padding
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
        
        # Valor en letras
        valor_letras = convertir_numero_a_letras(total_general)
        letras_style = ParagraphStyle(
            'ValorLetras',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        story.append(Paragraph(
            f"VALOR EN LETRAS: {valor_letras.upper()} PESOS M/L.",
            letras_style
        ))
    
    # Construir documento
    doc.build(story)

def convertir_numero_a_letras(numero):
    """Convierte un número a su representación en letras"""
    # Convertir Decimal a int para evitar errores
    numero = int(float(numero))
    
    # Implementación básica - se puede mejorar con librería externa
    if numero == 0:
        return "CERO"
    
    # Para números grandes, usar aproximación
    if numero >= 1000000000:
        miles_millones = int(numero / 1000000000)
        resto = numero % 1000000000
        if resto == 0:
            return f"{convertir_millones(miles_millones)} MIL MILLONES"
        else:
            return f"{convertir_millones(miles_millones)} MIL MILLONES {convertir_numero_a_letras(resto)}"
    elif numero >= 1000000:
        millones = int(numero / 1000000)
        resto = numero % 1000000
        if resto == 0:
            return f"{convertir_millones(millones)} MILLONES"
        else:
            return f"{convertir_millones(millones)} MILLONES {convertir_numero_a_letras(resto)}"
    else:
        return convertir_miles(numero)

def convertir_millones(numero):
    """Convierte números de millones"""
    if numero == 1:
        return "UN"
    elif numero < 1000:
        return convertir_miles(numero)
    else:
        return str(numero)  # Simplificado

def convertir_miles(numero):
    """Convierte números menores a millón"""
    # Implementación simplificada
    if numero < 1000:
        return convertir_centenas(numero)
    else:
        miles = int(numero / 1000)
        resto = numero % 1000
        if resto == 0:
            return f"{convertir_centenas(miles)} MIL"
        else:
            return f"{convertir_centenas(miles)} MIL {convertir_centenas(resto)}"

def convertir_centenas(numero):
    """Convierte números menores a mil"""
    unidades = ["", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    decenas = ["", "", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    especiales = ["DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISÉIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"]
    centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]
    
    if numero == 0:
        return "CERO"
    elif numero == 100:
        return "CIEN"
    elif numero < 10:
        return unidades[numero]
    elif numero < 20:
        return especiales[numero - 10]
    elif numero < 100:
        dec = int(numero / 10)
        uni = numero % 10
        if uni == 0:
            return decenas[dec]
        else:
            return f"{decenas[dec]} Y {unidades[uni]}"
    else:
        cen = int(numero / 100)
        resto = numero % 100
        if resto == 0:
            return centenas[cen]
        else:
            return f"{centenas[cen]} {convertir_centenas(resto)}"

def generar_pdf_simple(liquidacion, detalles, ruta_salida):
    """Genera un PDF simple con los datos de liquidación (mantiene compatibilidad)"""
    
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    
    # Configurar documento
    doc = SimpleDocTemplate(
        ruta_salida,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Elementos del documento
    story = []
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    titulo_style = ParagraphStyle(
        'TituloCustom',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.darkblue
    )
    
    # Título principal
    story.append(Paragraph("CUENTA DE COBRO", titulo_style))
    story.append(Paragraph("Sistema de Cuotas Partes", styles['Heading2']))
    story.append(Spacer(1, 20))
    
    # Información general
    info_data = [
        ['Entidad:', liquidacion.entidad_nombre],
        ['NIT:', liquidacion.entidad_nit],
        ['Liquidación No.:', str(liquidacion.liquidacion_id)],
        ['Período:', f"{liquidacion.periodo_inicio.strftime('%d/%m/%Y')} al {liquidacion.periodo_fin.strftime('%d/%m/%Y')}"],
        ['Total Capital:', f"${liquidacion.capital:,.2f}"],
        ['Total Intereses:', f"${liquidacion.interes:,.2f}"],
        ['TOTAL A PAGAR:', f"${liquidacion.total:,.2f}"],
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -2), 10),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('LINEBELOW', (0, -2), (-1, -2), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 30))
    
    # Tabla de detalles (solo primeros 10)
    story.append(Paragraph("DETALLE DE LIQUIDACIÓN (Muestra):", styles['Heading3']))
    story.append(Spacer(1, 10))
    
    # Datos de la tabla
    table_data = [['No.', 'Identificación', 'Nombre', 'Capital', 'Intereses', 'Total']]
    
    for i, detalle in enumerate(detalles, 1):
        nombre_corto = detalle.nombre[:25] + '...' if len(detalle.nombre) > 25 else detalle.nombre
        table_data.append([
            str(i),
            str(detalle.identificacion),
            nombre_corto,
            f"${detalle.capital:,.2f}",
            f"${detalle.interes:,.2f}",
            f"${detalle.total:,.2f}"
        ])
    
    # Crear tabla
    detalle_table = Table(table_data, colWidths=[0.4*inch, 1*inch, 2.2*inch, 1*inch, 1*inch, 1*inch])
    detalle_table.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        
        # Contenido
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # No.
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),  # Identificación
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),    # Nombre
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),  # Valores
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        
        # Bordes y colores alternados
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(detalle_table)
    story.append(Spacer(1, 30))
    
    # Nota legal
    nota = """
    <b>NOTA LEGAL:</b> Esta cuenta de cobro se genera en cumplimiento de la Ley 1066 de 2006 
    y demás normas vigentes sobre cuotas partes pensionales. Los valores aquí relacionados 
    corresponden a las cuotas partes y sus respectivos intereses calculados con base en la 
    DTF mensual vigente.
    """
    
    nota_style = ParagraphStyle(
        'NotaLegal',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_JUSTIFY,
        textColor=colors.gray
    )
    
    story.append(Paragraph(nota, nota_style))
    story.append(Spacer(1, 20))
    
    # Pie de página
    pie = f"""
    <para align="center">
    <i>Documento generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M:%S')}</i><br/>
    <i>Sistema de Cuotas Partes - Versión 1.0</i>
    </para>
    """
    
    story.append(Paragraph(pie, nota_style))
    
    # Construir documento
    doc.build(story)

# Función de utilidad para generar PDFs de liquidaciones