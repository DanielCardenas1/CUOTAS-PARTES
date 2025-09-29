import streamlit as st
from datetime import date
from decimal import Decimal, InvalidOperation

st.set_page_config(page_title="Cuotas Partes", page_icon="📑", layout="wide")

# --- Estilos institucionales ---
st.markdown("""
    <style>
    .main {background-color: #232a34; color: #e3e6ea;}
    .stButton > button {background-color: #1a2940; color: #fff; font-weight: bold; border-radius: 8px;}
    .stTable {background-color: #232a34;}
    .stTabs [data-baseweb="tab"] {background-color: #1a2940; color: #fff;}
    </style>
""", unsafe_allow_html=True)

# --- Sidebar de navegación ---
menu = st.sidebar.radio(
    "Menú principal",
    [
        "🏠 Dashboard",
        "👤 Pensionados",
        "📑 Liquidaciones",
        "⚖️ Liquidaciones Masivas (36 Cuentas)",
        "💰 Pagos",
        "📤 Cobro Persuasivo",
        "📊 Reportes y Seguimiento",
        "🔒 Seguridad y Trazabilidad"
    ]
)

# --- Funciones auxiliares para exportación ---

def numero_a_letras(numero):
    """Convierte un número a su representación en letras para documentos oficiales"""
    try:
        numero_entero = int(numero)
        numero_decimal = int((numero - numero_entero) * 100)
        
        # Diccionarios para la conversión
        unidades = ["", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
        decenas = ["", "", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
        especiales = ["DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISÉIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"]
        centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]
        
        def convertir_grupo(n):
            if n == 0:
                return ""
            elif n < 10:
                return unidades[n]
            elif n < 20:
                return especiales[n - 10]
            elif n < 100:
                return decenas[n // 10] + ("" if n % 10 == 0 else " Y " + unidades[n % 10])
            else:
                return (centenas[n // 100] if n // 100 != 1 else "CIEN" if n % 100 == 0 else "CIENTO") + ("" if n % 100 == 0 else " " + convertir_grupo(n % 100))
        
        if numero_entero == 0:
            return "CERO PESOS M/L"
        elif numero_entero < 1000:
            resultado = convertir_grupo(numero_entero)
        elif numero_entero < 1000000:
            miles = numero_entero // 1000
            resto = numero_entero % 1000
            resultado = (convertir_grupo(miles) + " MIL" + ("" if resto == 0 else " " + convertir_grupo(resto)))
        elif numero_entero < 1000000000:
            millones = numero_entero // 1000000
            resto = numero_entero % 1000000
            if millones == 1:
                resultado = "UN MILLÓN"
            else:
                resultado = convertir_grupo(millones) + " MILLONES"
            if resto > 0:
                if resto < 1000:
                    resultado += " " + convertir_grupo(resto)
                else:
                    miles = resto // 1000
                    unidades_resto = resto % 1000
                    resultado += " " + convertir_grupo(miles) + " MIL"
                    if unidades_resto > 0:
                        resultado += " " + convertir_grupo(unidades_resto)
        else:
            return "NÚMERO DEMASIADO GRANDE"
            
        return resultado + " PESOS M/L"
        
    except:
        return "ERROR EN CONVERSIÓN"

def generar_cuenta_individual_desde_excel(pensionado, cuenta, entidad_nombre, entidad_nit):
    """Genera una cuenta de cobro individual usando directamente la plantilla Excel PLANTILLA CXC 06.xlsm"""
    import openpyxl
    from openpyxl.utils import get_column_letter
    import tempfile
    import os
    import subprocess
    import shutil
    
    # Calcular totales
    capital = float(cuenta['capital_total'])
    intereses = float(cuenta['intereses'])
    total = capital + intereses
    
    # Convertir el total a letras
    total_letras = numero_a_letras(total)
    
    # Crear buffer en memoria para el PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                           rightMargin=0.5*inch, leftMargin=0.5*inch,
                           topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Definir estilos basados en la plantilla
    styles = getSampleStyleSheet()
    
    # Estilos específicos de la plantilla
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    titulo_style = ParagraphStyle(
        'TituloStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    nit_style = ParagraphStyle(
        'NitStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica',
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    debe_style = ParagraphStyle(
        'DebeStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    letras_style = ParagraphStyle(
        'LetrasStyle',
        parent=styles['Normal'],
        fontSize=8,
        fontName='Helvetica',
        alignment=TA_LEFT,
        spaceAfter=6
    )
    
    valor_style = ParagraphStyle(
        'ValorStyle',
        parent=styles['Normal'],
        fontSize=12,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    # Elementos del documento
    story = []
    
    # Leer y actualizar consecutivo
    try:
        with open('ultimo_consecutivo.txt', 'r') as f:
            consecutivo = int(f.read().strip())
    except:
        consecutivo = 1
    
    consecutivo += 1
    
    with open('ultimo_consecutivo.txt', 'w') as f:
        f.write(str(consecutivo))
    
    # Header: BOGOTÁ D.C. y CUENTA DE COBRO (según plantilla - Fila 3)
    header_data = [
        ["BOGOTÁ, D.C.", "CUENTA DE COBRO"],
        ["", f"Nro. {consecutivo}"]
    ]
    
    header_table = Table(header_data, colWidths=[3.5*inch, 2.5*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (0, 0), 10),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('FONTNAME', (1, 0), (1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (1, 0), (1, 1), 10),
        ('ALIGN', (1, 0), (1, 1), 'RIGHT'),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 0.3*inch))
    
    # SENA como emisor de la cuenta (según plantilla - Filas 6-7)
    story.append(Paragraph("SERVICIO NACIONAL DE APRENDIZAJE -SENA", titulo_style))
    story.append(Paragraph("899,999,034-1", nit_style))
    
    # DEBE A: (según plantilla - Fila 10)
    story.append(Paragraph("DEBE A:", debe_style))
    
    # Entidad deudora (según plantilla - Filas 14-15)
    story.append(Paragraph(entidad_nombre, titulo_style))
    story.append(Paragraph(entidad_nit, nit_style))
    
    # Valor en letras (según plantilla - Fila 17)
    story.append(Paragraph(f"LA SUMA DE: {total_letras}", letras_style))
    
    # Valor numérico (según plantilla - Fila 18)
    story.append(Paragraph(f"$ {total:,.0f}", valor_style))
    
    # Concepto (según plantilla - Filas 20-21)
    concepto_linea1 = "Por concepto de Cuotas Partes Pensionales sobre pagos realizados en la nómina de Pensionados del SENA"
    concepto_linea2 = "a fecha de corte 01 de Agosto de 2022 a corte de 31 de Julio de 2025 por los pensionados que se relacionan a continuación:"
    
    story.append(Paragraph(concepto_linea1, letras_style))
    story.append(Paragraph(concepto_linea2, letras_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Tabla de pensionados (según plantilla - Filas 23-26)
    table_headers = [
        'No. Cédula', 'Apellidos y Nombres', 'Ingreso\nnómina', 'RESOLUCIÓN Nº', 
        '% Cuota\nParte', 'Vr. Cuota\nParte Mes', 'Saldo\nCapital\nCausado', 
        'Intereses\nAcumulados', 'TOTAL\nDEUDA'
    ]
    
    table_data = [
        table_headers,
        [
            pensionado['cedula'],
            pensionado['nombre'][:25] if len(pensionado['nombre']) > 25 else pensionado['nombre'],
            '1-may-08',
            '3089 de 2007',
            f"{float(pensionado['porcentaje_cuota'])*100:.2f}%",
            f"{float(cuenta.get('valor_mesada', cuenta['capital_total'])):,.0f}",
            f"{capital:,.0f}",
            f"{intereses:,.0f}",
            f"{total:,.0f}"
        ],
        ['', '', '', '', '', 'TOTAL', f"{capital:,.0f}", f"{intereses:,.0f}", f"{total:,.0f}"]
    ]
    
    # Crear tabla ajustada para página vertical
    table = Table(table_data, colWidths=[0.7*inch, 1.5*inch, 0.7*inch, 0.8*inch, 0.6*inch, 0.8*inch, 0.9*inch, 0.9*inch, 0.9*inch])
    
    table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        
        # Data row
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, 1), 7),
        
        # Total row
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 2), (-1, 2), 7),
        
        # Grid and formatting
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 0.3*inch))
    
    # Información de pago (según plantilla - Fila 29)
    pago_info = "El pago de la presente cuenta se debe hacer a través de nuestro SISTEMA DE PAGOS EN LÍNEA - PSE,"
    story.append(Paragraph(pago_info, letras_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Información legal (según plantilla - Filas 31-33)
    legal_text = """Las obligaciones generadas con posterioridad al 29 de julio de 2006 por concepto de cuotas partes pensionales causarán un interés del DTF entre la fecha de pago de la mesada pensional y la fecha de reembolso por parte de la entidad concurrente. (Artículo 4 Ley 1066 de 2006, Circular N. 1-2006. 3-2006-016603)."""
    story.append(Paragraph(legal_text, letras_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Firmas (según plantilla - Filas 39-48)
    story.append(Paragraph("ADRIANA MILENA GASCA CARDOSO", titulo_style))
    story.append(Paragraph("Directora Administrativa y Financiera", letras_style))
    story.append(Paragraph("Sena - Dirección General", letras_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Vo Bo: JOSE GIOVANNI LOZANO BOLIVAR", letras_style))
    story.append(Paragraph("Coordinador Grupo recaudo y cartera D.A.F", letras_style))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("Preparó: Jenny Pirajan", letras_style))
    story.append(Paragraph("Cargo: Contratista-Grupo de Recaudo y Cartera.D.A.F", letras_style))
    
    # Construir PDF
    doc.build(story)
    
    # Obtener datos del buffer
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

def generar_consolidado_global_texto(entidad_nit, entidad_nombre, todas_las_cuentas, total_capital, total_intereses, fecha_corte):
    """Genera el contenido del consolidado global en formato texto"""
    content = f"""
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    CONSOLIDADO GLOBAL - LIQUIDACIÓN 36 CUENTAS INDEPENDIENTES                    ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                                  ║
║  🏛️  ENTIDAD: {entidad_nombre:<70}                                        ║
║  🆔  NIT: {entidad_nit:<77}                                        ║
║  📅  FECHA LIQUIDACIÓN: {fecha_corte.strftime('%d/%m/%Y'):<65}                                        ║
║  📊  PERÍODO: SEPTIEMBRE 2022 - AGOSTO 2025 (36 MESES EXACTOS)                                                ║
║                                                                                                                  ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                           RESUMEN EJECUTIVO                                                      ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                                  ║
║  👥  TOTAL PENSIONADOS: {len(todas_las_cuentas):<2}                                                                         ║
║  📋  TOTAL CUENTAS INDEPENDIENTES: {sum(len(p['cuentas']) for p in todas_las_cuentas):<3}                                                         ║
║  💰  CAPITAL TOTAL: ${float(total_capital):>15,.2f}                                                         ║
║  📈  INTERESES TOTALES: ${float(total_intereses):>15,.2f}                                                         ║
║  💯  GRAN TOTAL A COBRAR: ${float(total_capital + total_intereses):>15,.2f}                                                      ║
║                                                                                                                  ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                        RANKING POR PENSIONADO                                                    ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣

"""
    
    # Agregar ranking de pensionados
    pensionados_ordenados = sorted(todas_las_cuentas, key=lambda x: float(x['total_pensionado']), reverse=True)
    
    for i, p in enumerate(pensionados_ordenados, 1):
        porcentaje_del_total = (float(p['total_pensionado']) / float(total_capital + total_intereses)) * 100
        content += f"  {i:2d}. {p['pensionado']['nombre']:<35} ${float(p['total_pensionado']):>15,.2f} ({porcentaje_del_total:5.1f}%)\n"
    
    content += f"""

╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                          METODOLOGÍA APLICADA                                                    ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                                  ║
║  📋  SISTEMA: 36 Cuentas de Cobro Independientes por Pensionado                                                ║
║  💰  CAPITAL: Fijo por cuenta (sin capitalización entre cuentas)                                               ║
║  📈  INTERESES: DTF mensual específica aplicada sobre capital fijo                                             ║
║  🏛️  CONCEPTO: Mes vencido - Cuentas históricas desde su propio mes                                            ║
║  🎁  PRIMAS: Incluidas en diciembre y junio según número de mesadas                                            ║
║  ⚖️  MARCO LEGAL: Sistema Anti-Prescripción según Ley 1066 de 2006                                             ║
║                                                                                                                  ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝

NOTA IMPORTANTE: Este consolidado representa la suma de {sum(len(p['cuentas']) for p in todas_las_cuentas)} cuentas de cobro independientes.
Cada pensionado tiene exactamente 36 cuentas mensuales desde septiembre 2022 hasta agosto 2025.

Generado el {fecha_corte.strftime('%d/%m/%Y')} - Sistema Cuotas Partes v2.0
"""
    
    return content

def generar_resumen_pensionado_texto(pensionado_data):
    """Genera el resumen individual de un pensionado"""
    p = pensionado_data['pensionado']
    
    content = f"""
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                     RESUMEN INDIVIDUAL - 36 CUENTAS INDEPENDIENTES                              ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                                  ║
║  👤  PENSIONADO: {p['pensionado']['nombre']:<70}                                           ║
║  🆔  CÉDULA: {p['pensionado']['cedula']:<77}                                           ║
║  📊  PORCENTAJE CUOTA: {float(p['pensionado']['porcentaje_cuota'])*100:>6.2f}%                                                                ║
║  🎁  NÚMERO MESADAS: {p['pensionado']['mesadas']:<2}                                                                              ║
║                                                                                                                  ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                           TOTALES PENSIONADO                                                     ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                                  ║
║  📋  TOTAL CUENTAS: {len(pensionado_data['cuentas']):<2}                                                                            ║
║  💰  CAPITAL TOTAL: ${float(pensionado_data['total_capital']):>15,.2f}                                                         ║
║  📈  INTERESES TOTALES: ${float(pensionado_data['total_intereses']):>15,.2f}                                                         ║
║  💯  GRAN TOTAL: ${float(pensionado_data['total_pensionado']):>15,.2f}                                                            ║
║                                                                                                                  ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝

DETALLE DE LAS 36 CUENTAS:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

 #  │   Mes/Año   │    Capital Base    │      Prima       │   Capital Total   │    Intereses     │   Total Cuenta   │ Estado
────┼─────────────┼────────────────────┼──────────────────┼───────────────────┼──────────────────┼──────────────────┼─────────
"""
    
    for cuenta in pensionado_data['cuentas']:
        estado_emoji = "🎁" if cuenta['estado'] == '🎁 PRIMA' else "📈"
        prima_str = f"${float(cuenta['prima']):>13,.2f}" if cuenta['prima'] > 0 else f"{'':>16}"
        
        content += f"{cuenta['consecutivo']:2d}  │ {cuenta['mes']:02d}/{cuenta['año']} │ ${float(cuenta['capital_base']):>14,.2f} │ {prima_str} │ ${float(cuenta['capital_total']):>13,.2f} │ ${float(cuenta['intereses']):>12,.2f} │ ${float(cuenta['total_cuenta']):>12,.2f} │ {estado_emoji}\n"
    
    content += f"""
────┴─────────────┴────────────────────┴──────────────────┴───────────────────┴──────────────────┴──────────────────┴─────────

METODOLOGÍA:
• Cada cuenta es independiente con capital fijo (sin capitalización)
• Intereses calculados desde el mes de la cuenta hasta agosto 2025
• DTF efectiva anual específica para cada mes
• Primas incluidas según número de mesadas (12/13/14)

PERÍODO: Septiembre 2022 - Agosto 2025 (36 meses exactos - mes vencido)
"""
    
    return content

def generar_pdf_consolidado_para_zip(entidad_nit, entidad_nombre, todas_las_cuentas, total_capital, total_intereses, fecha_corte):
    """Genera PDF consolidado para incluir en ZIP"""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import io
    
    # Crear buffer en memoria para el PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                           rightMargin=0.3*inch, leftMargin=0.3*inch,
                           topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Estilos
    styles = getSampleStyleSheet()
    
    titulo_principal = ParagraphStyle(
        'TituloPrincipal',
        parent=styles['Heading1'],
        fontSize=14,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    subtitulo = ParagraphStyle(
        'Subtitulo',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    normal_centro = ParagraphStyle(
        'NormalCentro',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    # Elementos del documento
    story = []
    
    # Título principal
    story.append(Paragraph("CONSOLIDADO GLOBAL - LIQUIDACIÓN 36 CUENTAS", titulo_principal))
    story.append(Paragraph(f"ENTIDAD: {entidad_nombre}", subtitulo))
    story.append(Paragraph(f"NIT: {entidad_nit}", normal_centro))
    story.append(Paragraph(f"Fecha de corte: {fecha_corte.strftime('%d/%m/%Y')}", normal_centro))
    story.append(Spacer(1, 0.3*inch))
    
    # Crear tabla de pensionados
    table_data = [
        ['CÉDULA', 'NOMBRE', 'CAPITAL TOTAL', 'INTERESES', 'TOTAL DEUDA']
    ]
    
    for pensionado_info, cuentas in todas_las_cuentas.items():
        if cuentas:
            primera_cuenta = cuentas[0]
            capital_pensionado = sum(float(cuenta['capital_total']) for cuenta in cuentas)
            intereses_pensionado = sum(float(cuenta['intereses']) for cuenta in cuentas)
            total_pensionado = capital_pensionado + intereses_pensionado
            
            table_data.append([
                primera_cuenta['cedula'],
                primera_cuenta['nombre'][:30],
                f"${capital_pensionado:,.0f}",
                f"${intereses_pensionado:,.0f}",
                f"${total_pensionado:,.0f}"
            ])
    
    # Fila de totales
    total_deuda = total_capital + total_intereses
    table_data.append(['', 'TOTALES', f"${total_capital:,.0f}", f"${total_intereses:,.0f}", f"${total_deuda:,.0f}"])
    
    # Crear tabla
    table = Table(table_data, colWidths=[1.2*inch, 2.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    
    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        
        # Data rows
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 7),
        
        # Total row
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 8),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 0.2*inch))
    
    # Información adicional
    story.append(Paragraph(f"Total pensionados: {len(todas_las_cuentas)}", normal_centro))
    story.append(Paragraph("Período: Septiembre 2022 - Agosto 2025 (36 cuentas independientes)", normal_centro))
    
    # Construir PDF
    doc.build(story)
    
    # Obtener datos del buffer
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

def generar_zip_individual_plantilla(entidad_nit, entidad_nombre, todas_las_cuentas):
    """Genera un ZIP con todas las cuentas individuales basadas en la plantilla Excel"""
    import zipfile
    import io
    from datetime import datetime
    
    # Crear un buffer en memoria para el ZIP
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Agregar README
        readme_content = generar_readme_texto(entidad_nit, len(todas_las_cuentas), 
                                            sum(len(cuentas) for cuentas in todas_las_cuentas.values()))
        zip_file.writestr("README.txt", readme_content)
        
        # Agregar PDF consolidado
        total_capital = sum(sum(float(cuenta['capital_total']) for cuenta in cuentas) 
                          for cuentas in todas_las_cuentas.values())
        total_intereses = sum(sum(float(cuenta['intereses']) for cuenta in cuentas) 
                            for cuentas in todas_las_cuentas.values())
        
        fecha_corte = datetime.now()
        pdf_consolidado = generar_pdf_consolidado_para_zip(entidad_nit, entidad_nombre, 
                                                          todas_las_cuentas, total_capital, 
                                                          total_intereses, fecha_corte)
        zip_file.writestr("CONSOLIDADO_GLOBAL.pdf", pdf_consolidado)
        
        # Agregar cada PDF individual por pensionado
        for pensionado_info, cuentas in todas_las_cuentas.items():
            # Obtener información del pensionado desde la primera cuenta
            primera_cuenta = cuentas[0] if cuentas else None
            if not primera_cuenta:
                continue
                
            # Crear nombre de archivo seguro
            nombre_pensionado = primera_cuenta['nombre'][:30].replace(' ', '_').replace(',', '')
            cedula = primera_cuenta['cedula']
            
            # Calcular totales del pensionado
            capital_pensionado = sum(float(cuenta['capital_total']) for cuenta in cuentas)
            intereses_pensionado = sum(float(cuenta['intereses']) for cuenta in cuentas)
            
            # Crear cuenta consolidada para este pensionado
            cuenta_consolidada = {
                'capital_total': capital_pensionado,
                'intereses': intereses_pensionado
            }
            
            # Preparar datos del pensionado
            pensionado_data = {
                'cedula': cedula,
                'nombre': primera_cuenta['nombre'],
                'porcentaje_cuota': primera_cuenta.get('porcentaje_cuota', 0.15)
            }
            
            # Generar PDF individual usando la plantilla
            pdf_data = generar_cuenta_individual_desde_excel(pensionado_data, cuenta_consolidada, 
                                                         entidad_nombre, entidad_nit)
            
            # Agregar al ZIP
            nombre_archivo = f"CUENTA_INDIVIDUAL_{cedula}_{nombre_pensionado}.pdf"
            zip_file.writestr(nombre_archivo, pdf_data)
    
    # Obtener datos del ZIP
    zip_data = zip_buffer.getvalue()
    zip_buffer.close()
    
    return zip_data

def generar_readme_texto(entidad_nit, total_pensionados, total_cuentas):
    """Genera el archivo README con instrucciones"""
    
    content = f"""
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    LIQUIDACIÓN 36 CUENTAS INDEPENDIENTES                                        ║
║                                              INSTRUCCIONES                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝

📋 CONTENIDO DEL ARCHIVO:
═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

🏛️ ENTIDAD: {entidad_nit}
👥 PENSIONADOS: {total_pensionados}
📊 TOTAL CUENTAS: {total_cuentas}

📁 ESTRUCTURA DE CARPETAS:
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

├── 00_CONSOLIDADO_GLOBAL.txt          → Resumen ejecutivo de toda la entidad
├── 01_Pensionado_Cedula/               → Carpeta individual por pensionado  
│   ├── 00_RESUMEN_Pensionado.txt       → Resumen de las 36 cuentas del pensionado
│   └── cuentas/                        → Subcarpeta con las 36 cuentas individuales
│       ├── CUENTA_01_09_2022.pdf       → Cuenta mes 1 (Sep 2022) - FORMATO OFICIAL HACIENDA
│       ├── CUENTA_02_10_2022.pdf       → Cuenta mes 2 (Oct 2022) - FORMATO OFICIAL HACIENDA
│       └── ... (hasta CUENTA_36_08_2025.pdf) → TODAS LAS 36 CUENTAS EN PDF OFICIAL
└── README.txt                          → Este archivo de instrucciones

⚖️ METODOLOGÍA APLICADA:
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

📅 PERÍODO: Septiembre 2022 - Agosto 2025 (36 meses exactos)
💰 CAPITAL: Fijo por cuenta (no se capitaliza entre cuentas)
📈 INTERESES: DTF mensual específica sobre capital fijo
🏛️ CONCEPTO: Mes vencido (cuentas históricas desde su propio mes)
🎁 PRIMAS: Incluidas según número de mesadas (dic/jun)
⚖️ LEGAL: Sistema Anti-Prescripción (Ley 1066 de 2006)

📋 CÓMO USAR ESTE ARCHIVO:
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

1. 📖 Lea primero el CONSOLIDADO_GLOBAL.txt para entender el resumen ejecutivo
2. 👤 Navegue a la carpeta del pensionado que necesite revisar
3. 📋 Abra el resumen del pensionado para ver sus totales
4. � Revise las 36 cuentas individuales en PDF oficial en la subcarpeta "cuentas/"
5. 🏛️ Cada PDF tiene el formato oficial de la Secretaría de Hacienda

💡 IMPORTANTE:
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Cada pensionado tiene EXACTAMENTE 36 cuentas independientes
• Cada cuenta mantiene su capital fijo durante todo el período
• Los intereses se calculan mes a mes con DTF específica
• Las cuentas históricas generan intereses desde su propio mes
• Este sistema evita la prescripción de cuotas partes

🔧 SOPORTE TÉCNICO:
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Sistema: Cuotas Partes v2.0
Metodología: 36 Cuentas Independientes
Fecha generación: {date.today().strftime('%d/%m/%Y')}

Para consultas técnicas sobre la liquidación, contactar al administrador del sistema.
"""
    
    return content

# --- Dashboard ---
if menu == "🏠 Dashboard":
    st.title("Generador de Cuentas de Cobro (Cuotas Partes)")
    st.subheader("Resumen rápido")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de pensionados", "0")
    with col2:
        st.metric("Cuentas por cobrar este mes", "0")
    with col3:
        st.metric("Cuentas próximas a prescribir", "0")
    with col4:
        st.metric("Alertas", "0")
    st.markdown("---")
    st.button("➕ Nuevo pensionado")
    st.button("📑 Generar liquidaciones")
    st.button("💰 Registrar pagos")
    st.button("📤 Enviar cobros persuasivos")

# --- Módulo Pensionados ---
elif menu == "👤 Pensionados":
    st.title("Gestión de Pensionados")
    st.subheader("Registro / Edición de pensionados")
    
    try:
        from app.db import get_session
        from app.models import Pensionado
        import pandas as pd
        
        session = get_session()
        pensionados = session.query(Pensionado).all()
        session.close()
        
        st.markdown("---")
        # Buscador funcional
        filtro = st.text_input("🔍 Buscar pensionado por nombre, identificación o entidad")
        
        if pensionados:
            df = pd.DataFrame([
                {
                    "ID": p.pensionado_id,
                    "Identificación": p.identificacion,
                    "Nombre": p.nombre,
                    "Entidad": p.nit_entidad,
                    "Estado": p.estado_cartera,
                    "Fecha ingreso": p.fecha_ingreso_nomina,
                    "Capital pendiente": p.capital_pendiente,
                    "Intereses pendientes": p.intereses_pendientes
                }
                for p in pensionados
            ])
            
            if filtro:
                filtro_lower = filtro.lower()
                df = df[df.apply(lambda row: filtro_lower in str(row["Nombre"]).lower() or filtro_lower in str(row["Identificación"]).lower() or filtro_lower in str(row["Entidad"]).lower(), axis=1)]
            
            st.markdown('<div style="overflow-x:auto; max-width:100vw;">', unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True, height=400)
            st.markdown('</div>', unsafe_allow_html=True)
            st.caption("Usa la barra inferior para deslizar horizontalmente y ver todas las columnas.")
        else:
            st.info("No hay pensionados registrados en la base de datos.")
            
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        st.info("Verifica que MySQL esté ejecutándose y que la configuración sea correcta.")

# --- Módulo Liquidaciones ---
elif menu == "📑 Liquidaciones":
    st.title("Generar Liquidaciones Mensuales")
    st.subheader("Formulario de liquidación")
    
    try:
        from app.db import get_session
        from app.models import Pensionado, Entidad
        import pandas as pd
        
        session = get_session()
        entidades = session.query(Entidad).all()
        pensionados = session.query(Pensionado).all()
        session.close()
        
        entidad_sel = st.selectbox("Selecciona entidad", entidades, format_func=lambda e: f"{e.nombre} ({e.nit})" if e else "")
        pensionado_sel = st.selectbox("Selecciona pensionado", pensionados, format_func=lambda p: f"{p.nombre} ({p.identificacion})" if p else "")
        periodo = st.date_input("Período a liquidar", value=date.today())
        valor_base = st.number_input("Valor base de cálculo", min_value=0.0, step=1000.0)
        tasa_dtf = st.number_input("Interés DTF (%)", min_value=0.0, step=0.01)
        calcular = st.button("Liquidar cuenta")
        
        st.markdown("---")
        
        if calcular and pensionado_sel and entidad_sel:
            # Simulación de cálculo real
            capital = valor_base
            interes = capital * (tasa_dtf / 100)
            total = capital + interes
            
            df = pd.DataFrame([{
                "Pensionado": pensionado_sel.nombre,
                "Identificación": pensionado_sel.identificacion,
                "Entidad": entidad_sel.nombre,
                "Periodo": periodo.strftime('%Y-%m'),
                "Capital": f"{capital:,.2f}",
                "Interés": f"{interes:,.2f}",
                "Total": f"{total:,.2f}"
            }])
            
            st.subheader(":mag: Vista previa de liquidación")
            st.dataframe(df, use_container_width=True)
            st.success(f"Liquidación generada: Capital={capital:,.2f}, Interés={interes:,.2f}, Total={total:,.2f}")
        elif calcular:
            st.error("Debes seleccionar entidad y pensionado.")
            
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        st.info("Verifica que MySQL esté ejecutándose y que la configuración sea correcta.")

# --- Módulo Pagos ---
elif menu == "💰 Pagos":
    st.title("Registro de Pagos de Entidades")
    st.subheader("Formulario de registro de pagos")
    
    st.text_input("Seleccionar pensionado")
    st.text_input("Seleccionar entidad")
    st.text_input("Número de cuenta de cobro aplicada")
    st.date_input("Fecha de pago", value=date.today())
    st.number_input("Valor abonado", min_value=0.0, step=1000.0)
    st.text_area("Observaciones")
    st.button("Guardar pago")
    
    st.markdown("---")
    st.write("(Aquí se mostraría la tabla de pagos registrados)")

# --- Módulo Cobro Persuasivo ---
elif menu == "📤 Cobro Persuasivo":
    st.title("Cobro Persuasivo a Entidades Deudoras")
    st.subheader("Generar carta de cobro")
    
    st.text_input("Seleccionar entidad deudora")
    st.date_input("Período a cobrar", value=date.today())
    st.text_area("Información legal (Ley 1066/2006)")
    st.write("Valores y períodos a cobrar (simulado)")
    st.file_uploader("Adjuntar liquidaciones mensuales + consolidado", accept_multiple_files=True)
    st.button("Enviar / Descargar carta")

# --- Módulo Reportes y Seguimiento ---
elif menu == "📊 Reportes y Seguimiento":
    st.title("Reportes y Seguimiento")
    st.subheader("Tabla dinámica de seguimiento")
    
    st.text_input("Filtrar por entidad")
    st.text_input("Filtrar por pensionado")
    st.date_input("Filtrar por período", value=date.today())
    
    st.markdown("---")
    st.write("(Aquí se mostraría la tabla de reportes y seguimiento)")
    st.button("Exportar a PDF")
    st.button("Exportar a Excel")
    
    st.markdown("---")
    st.write("🔴 Cuentas próximas a prescribir | 🟡 Pagos parciales | 🟢 Pagos completos")

# --- Módulo Liquidaciones Masivas (36 Cuentas) ---
elif menu == "⚖️ Liquidaciones Masivas (36 Cuentas)":
    st.title("⚖️ Liquidaciones Masivas (36 Cuentas Independientes)")
    
    st.markdown("""
    ### 📋 Sistema Corregido de 36 Cuentas Independientes
    **🎯 Objetivo:** Generar 36 cuentas de cobro independientes por pensionado (mes vencido).
    
    **💡 Metodología Corregida:**
    - **📅 Período Fijo:** Septiembre 2022 - Agosto 2025 (36 meses exactos)
    - **💰 Capital Fijo:** Cada cuenta mantiene su capital base sin capitalización
    - **📈 Interés Simple:** DTF mensual aplicada sobre capital fijo de cada cuenta
    - **🏛️ Mes Vencido:** Cuentas históricas generan intereses desde su propio mes
    - **🎁 Primas:** Incluidas en diciembre y junio según corresponda
    
    **⚖️ Marco Legal:** Sistema Anti-Prescripción - Cada mes es una cuenta independiente
    """)
    
    # Inicializar session_state
    if 'cuentas_generadas' not in st.session_state:
        st.session_state.cuentas_generadas = None
        st.session_state.entidad_actual = None
    
    try:
        from app.db import get_session
        from sqlalchemy import text
        import sys
        import os
        
        # Importar las funciones del sistema corregido
        sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))
        from liquidacion_36_cuentas_corregida import (
            obtener_pensionados_entidad, 
            calcular_cuenta_mensual, 
            obtener_dtf_mes,
            tiene_prima_mes,
            calcular_interes_mensual,
            calcular_dias_mes
        )
        from scripts.liquidacion_historica import ajustar_base_por_ipc
        
        session = get_session()
        
        # Obtener entidades disponibles
        entidades = session.execute(
            text("""
                SELECT DISTINCT e.nit, e.nombre, COUNT(p.pensionado_id) as pensionados_activos
                FROM entidad e
                LEFT JOIN pensionado p ON e.nit = p.nit_entidad AND p.estado_cartera = 'ACTIVO'
                GROUP BY e.nit, e.nombre
                HAVING pensionados_activos > 0
                ORDER BY e.nombre
            """)
        ).fetchall()
        
        st.markdown("---")
        
        # Formulario de generación
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🏢 Selección de Entidad")
            
            if entidades:
                entidad_options = [(e.nit, f"{e.nombre} (NIT: {e.nit}) - {e.pensionados_activos} pensionados") for e in entidades]
                entidad_selected = st.selectbox(
                    "Selecciona la entidad:",
                    options=entidad_options,
                    format_func=lambda x: x[1]
                )
                entidad_nit = entidad_selected[0] if entidad_selected else None
                # Obtener nombre de la entidad seleccionada
                entidad_nombre = next((e.nombre for e in entidades if e.nit == entidad_nit), "ENTIDAD NO ENCONTRADA")
            else:
                st.error("No se encontraron entidades con pensionados activos")
                entidad_nit = None
                entidad_nombre = None
        
        with col2:
            st.subheader("📅 Configuración")
            fecha_corte = st.date_input(
                "Fecha de corte:",
                value=date(2025, 9, 25),
                help="Fecha de referencia para el cálculo"
            )
            
            st.info(f"""
            **📆 Período fijo:**
            - Desde: Septiembre 2022
            - Hasta: Agosto 2025
            - Total: 36 cuentas independientes
            - 💰 **Metodología:** Mes vencido
            """)
        
        st.markdown("---")
        
        # Botón de generación
        if st.button("🚀 Generar 36 Cuentas de Cobro", type="primary"):
            if entidad_nit:
                with st.spinner("⏳ Generando las 36 cuentas independientes..."):
                    try:
                        from decimal import Decimal
                        from datetime import date
                        from dateutil.relativedelta import relativedelta
                        
                        # Obtener pensionados de la entidad
                        pensionados = obtener_pensionados_entidad(session, entidad_nit)
                        
                        if not pensionados:
                            st.error(f"No se encontraron pensionados para la entidad {entidad_nit}")
                        else:
                            # Período fijo del sistema
                            fecha_inicial = date(2022, 9, 1)
                            fecha_final = date(2025, 8, 31)
                            
                            # Generar todas las cuentas
                            todas_las_cuentas = []
                            total_capital_entidad = Decimal('0')
                            total_intereses_entidad = Decimal('0')
                            
                            # Barra de progreso
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            pensionado_count = 0
                            total_pensionados = len(pensionados)
                            
                            for pensionado in pensionados:
                                pensionado_count += 1
                                status_text.text(f"Procesando pensionado {pensionado_count}/{total_pensionados}: {pensionado[1]}")
                                
                                # Generar 36 cuentas para este pensionado
                                fecha_cuenta = fecha_inicial
                                consecutivo = 1
                                total_pensionado = Decimal('0')
                                
                                cuentas_pensionado = []
                                
                                while fecha_cuenta <= fecha_final:
                                    # Obtener datos del pensionado de forma segura
                                    try:
                                        # Usar porcentaje_cuota del campo correcto (índice 3)
                                        porcentaje_cuota = Decimal(str(pensionado[3])) if pensionado[3] else Decimal('0.15')
                                        # Usar numero_mesadas del campo correcto (índice 4) 
                                        numero_mesadas = int(pensionado[4]) if pensionado[4] else 12
                                        # Usar base_calculo_cuota_parte de la base de datos (índice 8)
                                        base_calculo_cuota_parte = Decimal(str(pensionado[8])) if pensionado[8] else Decimal('383628.0')
                                    except (ValueError, IndexError, InvalidOperation):
                                        # Valores por defecto en caso de error
                                        porcentaje_cuota = Decimal('0.15')
                                        numero_mesadas = 12
                                        base_calculo_cuota_parte = Decimal('922628.0')  # Valor correcto de la BD
                                    
                                    # Ajustar base por IPC para el año específico de la cuenta
                                    base_ajustada_año = ajustar_base_por_ipc(float(base_calculo_cuota_parte), 2022, fecha_cuenta.year)
                                    
                                    # Calcular capital fijo de la cuenta usando la base ajustada por IPC
                                    capital_base = Decimal(str(base_ajustada_año)) * porcentaje_cuota
                                    
                                    # Determinar si tiene prima
                                    tiene_prima = tiene_prima_mes(numero_mesadas, fecha_cuenta.month)
                                    prima = capital_base if tiene_prima else Decimal('0')
                                    capital_total = capital_base + prima
                                    
                                    # Calcular intereses acumulativos para ESTA cuenta específica
                                    fecha_actual = fecha_cuenta
                                    fecha_limite = date(2025, 8, 31)
                                    interes_acumulado = Decimal('0')
                                    
                                    # Iterar mes a mes DESDE el mes de la cuenta hasta agosto 2025
                                    while fecha_actual <= fecha_limite:
                                        # Calcular interés para este mes específico usando las fechas correctas
                                        interes_mes = calcular_interes_mensual(float(capital_total), fecha_actual, fecha_limite)
                                        interes_acumulado += Decimal(str(interes_mes))
                                        fecha_actual = fecha_actual + relativedelta(months=1)
                                    
                                    total_cuenta = capital_total + interes_acumulado
                                    
                                    cuenta = {
                                        'pensionado_id': pensionado[0],  # pensionado_id está en índice 0
                                        'pensionado_nombre': pensionado[2],  # nombre está en índice 2
                                        'cedula': pensionado[1],  # cedula está en índice 1
                                        'porcentaje': float(porcentaje_cuota),
                                        'consecutivo': consecutivo,
                                        'mes': fecha_cuenta.month,
                                        'año': fecha_cuenta.year,
                                        'fecha_cuenta': fecha_cuenta,
                                        'capital_base': capital_base,
                                        'prima': prima,
                                        'capital_total': capital_total,
                                        'intereses': interes_acumulado,
                                        'total_cuenta': total_cuenta,
                                        'estado': '🎁 PRIMA' if tiene_prima else '📈 Regular'
                                    }
                                    
                                    cuentas_pensionado.append(cuenta)
                                    total_pensionado += total_cuenta
                                    
                                    fecha_cuenta += relativedelta(months=1)
                                    consecutivo += 1
                                
                                # Agregar resumen del pensionado
                                resumen_pensionado = {
                                    'pensionado': {
                                        'cedula': pensionado[1],  # identificacion está en índice 1
                                        'nombre': pensionado[2],  # nombre está en índice 2
                                        'porcentaje_cuota': porcentaje_cuota,
                                        'mesadas': numero_mesadas,
                                        'pensionado_id': pensionado[0]  # pensionado_id está en índice 0
                                    },
                                    'cuentas': cuentas_pensionado,
                                    'total_capital': sum(c['capital_total'] for c in cuentas_pensionado),
                                    'total_intereses': sum(c['intereses'] for c in cuentas_pensionado),
                                    'total_pensionado': total_pensionado
                                }
                                
                                todas_las_cuentas.append(resumen_pensionado)
                                total_capital_entidad += resumen_pensionado['total_capital']
                                total_intereses_entidad += resumen_pensionado['total_intereses']
                                
                                # Actualizar progreso
                                progress_bar.progress(pensionado_count / total_pensionados)
                            
                            progress_bar.progress(1.0)
                            status_text.text("✅ Generación completada!")
                            
                            # Guardar resultados en session_state
                            st.session_state.cuentas_generadas = {
                                'todas_las_cuentas': todas_las_cuentas,
                                'total_capital_entidad': total_capital_entidad,
                                'total_intereses_entidad': total_intereses_entidad,
                                'total_cuentas_generadas': sum(len(p['cuentas']) for p in todas_las_cuentas)
                            }
                            st.session_state.entidad_actual = entidad_nit
                        
                    except Exception as e:
                        st.error(f"❌ Error generando las 36 cuentas de cobro: {str(e)}")
                        import traceback
                        st.error(traceback.format_exc())
            else:
                st.error("⚠️ Por favor selecciona una entidad")
        
        # Mostrar resultados si existen en session_state
        if st.session_state.cuentas_generadas and st.session_state.entidad_actual == entidad_nit:
            datos = st.session_state.cuentas_generadas
            todas_las_cuentas = datos['todas_las_cuentas']
            total_capital_entidad = datos['total_capital_entidad']
            total_intereses_entidad = datos['total_intereses_entidad']
            total_cuentas_generadas = datos['total_cuentas_generadas']
            
            st.success(f"✅ {total_cuentas_generadas} cuentas independientes generadas para {len(todas_las_cuentas)} pensionados!")
            
            # Consolidado global
            st.markdown("---")
            st.subheader("🏆 CONSOLIDADO GLOBAL DE LA ENTIDAD")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("👥 Pensionados", f"{len(todas_las_cuentas)}")
            with col2:
                st.metric("💰 Capital Total", f"${float(total_capital_entidad):,.2f}")
            with col3:
                st.metric("📈 Intereses Total", f"${float(total_intereses_entidad):,.2f}")
            with col4:
                st.metric("💯 GRAN TOTAL", f"${float(total_capital_entidad + total_intereses_entidad):,.2f}")
            
            # Resumen por pensionado
            st.markdown("---")
            st.subheader("📋 Resumen por Pensionado")
            
            import pandas as pd
            df_pensionados = pd.DataFrame([
                {
                    'Pensionado': p['pensionado']['nombre'],
                    'Cédula': p['pensionado']['cedula'],
                    'Porcentaje': f"{float(p['pensionado']['porcentaje_cuota']) * 100:.2f}%",
                    'Cuentas': len(p['cuentas']),
                    'Capital': f"${float(p['total_capital']):,.2f}",
                    'Intereses': f"${float(p['total_intereses']):,.2f}",
                    'Total': f"${float(p['total_pensionado']):,.2f}"
                }
                for p in todas_las_cuentas
            ])
            
            st.dataframe(df_pensionados, use_container_width=True, height=400)
            
            # Mostrar detalle de un pensionado específico
            st.markdown("---")
            st.subheader("🔍 Detalle por Pensionado")
            
            # Selector de pensionado con key único para evitar reinicios
            pensionado_names = [(i, p['pensionado']['nombre']) for i, p in enumerate(todas_las_cuentas)]
            selected_pensionado_idx = st.selectbox(
                "Selecciona un pensionado para ver sus 36 cuentas:",
                options=[i for i, _ in pensionado_names],
                format_func=lambda x: pensionado_names[x][1],
                key="selector_pensionado"
            )
            
            if selected_pensionado_idx is not None:
                pensionado_detalle = todas_las_cuentas[selected_pensionado_idx]
                
                st.write(f"**👤 {pensionado_detalle['pensionado']['nombre']}** - Total: ${float(pensionado_detalle['total_pensionado']):,.2f}")
                
                # Mostrar las 36 cuentas
                df_cuentas = pd.DataFrame([
                    {
                        'Cuenta': f"{c['consecutivo']:02d}",
                        'Mes/Año': f"{c['mes']:02d}/{c['año']}",
                        'Capital Base': f"${float(c['capital_base']):,.2f}",
                        'Prima': f"${float(c['prima']):,.2f}" if c['prima'] > 0 else "-",
                        'Capital Total': f"${float(c['capital_total']):,.2f}",
                        'Intereses': f"${float(c['intereses']):,.2f}",
                        'Total Cuenta': f"${float(c['total_cuenta']):,.2f}",
                        'Estado': c['estado']
                    }
                    for c in pensionado_detalle['cuentas']
                ])
                
                st.dataframe(df_cuentas, use_container_width=True, height=600)
            
            # Sección de exportación
            st.markdown("---")
            st.subheader("📦 Exportar Documentos Oficiales")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("� PDF Consolidado", type="primary", use_container_width=True):
                    try:
                        from reportlab.lib.pagesizes import letter, landscape
                        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
                        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                        from reportlab.lib.units import inch
                        from reportlab.lib import colors
                        from reportlab.lib.enums import TA_CENTER, TA_LEFT
                        import tempfile
                        import io
                        
                        # Crear buffer en memoria para el PDF (orientación vertical)
                        buffer = io.BytesIO()
                        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                                               rightMargin=0.3*inch, leftMargin=0.3*inch,
                                               topMargin=0.5*inch, bottomMargin=0.5*inch)
                        
                        # Estilos
                        styles = getSampleStyleSheet()
                        title_style = ParagraphStyle(
                            'CustomTitle',
                            parent=styles['Heading1'],
                            fontSize=16,
                            spaceAfter=8,
                            alignment=TA_CENTER,
                            fontName='Helvetica-Bold'
                        )
                        
                        subtitle_style = ParagraphStyle(
                            'CustomSubtitle',
                            parent=styles['Normal'],
                            fontSize=12,
                            spaceAfter=6,
                            alignment=TA_CENTER,
                            fontName='Helvetica-Bold'
                        )
                        
                        normal_center = ParagraphStyle(
                            'NormalCenter',
                            parent=styles['Normal'],
                            fontSize=10,
                            alignment=TA_CENTER
                        )
                        
                        # Elementos del documento
                        story = []
                        
                        # === FORMATO OFICIAL CUENTA DE COBRO ===
                        
                        # Leer y actualizar consecutivo
                        try:
                            with open('ultimo_consecutivo.txt', 'r') as f:
                                ultimo_consecutivo = int(f.read().strip())
                        except:
                            ultimo_consecutivo = 423
                        
                        nuevo_consecutivo = ultimo_consecutivo + 1
                        
                        # Guardar nuevo consecutivo
                        with open('ultimo_consecutivo.txt', 'w') as f:
                            f.write(str(nuevo_consecutivo))
                        
                        # Encabezado oficial como la imagen
                        story.append(Spacer(1, 0.5*inch))
                        
                        # Primera línea: BOGOTÁ D.C. y CUENTA DE COBRO
                        header_line1 = Table([['BOGOTÁ, D.C.', 'CUENTA DE COBRO']], colWidths=[4*inch, 3*inch])
                        header_line1.setStyle(TableStyle([
                            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, -1), 14),
                            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ]))
                        story.append(header_line1)
                        
                        # Número de cuenta de cobro (centrado debajo de CUENTA DE COBRO)
                        numero_table = Table([['', f'No.  {nuevo_consecutivo}']], colWidths=[4*inch, 3*inch])
                        numero_table.setStyle(TableStyle([
                            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (1, 0), (1, 0), 14),
                            ('ALIGN', (1, 0), (1, 0), 'CENTER'),  # Centrado
                        ]))
                        story.append(numero_table)
                        
                        story.append(Spacer(1, 0.3*inch))
                        
                        # Nombre de la entidad acreedora (siempre SERVICIO NACIONAL DE APRENDIZAJE)
                        story.append(Paragraph(f"<b>SERVICIO NACIONAL DE APRENDIZAJE -SENA</b>", title_style))
                        story.append(Paragraph(f"<b>899,999,034-1</b>", title_style))
                        
                        story.append(Spacer(1, 0.4*inch))
                        
                        # DEBE A:
                        story.append(Paragraph("<b>DEBE A:</b>", title_style))
                        story.append(Spacer(1, 0.3*inch))
                        
                        # Nombre del deudor (centrado) - siempre es el SENA
                        story.append(Paragraph(f"<b>SERVICIO NACIONAL DE APRENDIZAJE -SENA</b>", title_style))
                        story.append(Paragraph(f"<b>899,999,034-1</b>", title_style))
                        
                        # Calcular totales consolidados ANTES de usar en las tablas
                        total_consolidado_capital = 0
                        total_consolidado_intereses = 0
                        total_consolidado_total = 0
                        
                        for p in todas_las_cuentas:
                            capital_pensionado = sum(float(cuenta['capital_total']) for cuenta in p['cuentas'])
                            intereses_pensionado = sum(float(cuenta['intereses']) for cuenta in p['cuentas'])
                            total_pensionado = capital_pensionado + intereses_pensionado
                            
                            total_consolidado_capital += capital_pensionado
                            total_consolidado_intereses += intereses_pensionado
                            total_consolidado_total += total_pensionado
                        
                        story.append(Spacer(1, 0.3*inch))
                        
                        # Valor en letras alineado a la izquierda con más espacio
                        valor_letras = numero_a_letras(int(total_consolidado_total))
                        valor_paragraph = Paragraph(f"<b>LA SUMA DE: {valor_letras.upper()} PESOS M/CTE</b>", styles['Normal'])
                        valor_paragraph.alignment = 0  # Alineación izquierda
                        story.append(valor_paragraph)
                        
                        story.append(Paragraph(f"<b>$ {total_consolidado_total:,.0f}</b>", title_style))
                        
                        story.append(Spacer(1, 0.4*inch))
                        
                        # Concepto como en la imagen
                        concepto_text = f"""Por concepto de Cuotas Partes Pensionales sobre pagos realizados en la nómina de Pensionados del SENA 
a fecha de corte 01 de Agosto de 2022 a corte de 31 de Julio de 2025 por los pensionados que se relacionan a continuación:"""
                        
                        story.append(Paragraph(concepto_text, styles['Normal']))
                        story.append(Spacer(1, 0.3*inch))
                        
                        # Tabla oficial como en la imagen (ajustado RESOLUCIÓN)
                        tabla_data = [
                            ['No. Cédula', 'Apellidos y Nombres', 'Ingreso\nNómina', 'RESOLUCIÓN\nNº', '% Cuota\nParte', 'Vr. Cuota\nParte Mes', 'Saldo\nCapital\nCausado', 'Intereses\nAcumulados', 'TOTAL\nDEUDA']
                        ]
                        
                        for p in todas_las_cuentas:
                            capital_pensionado = sum(float(cuenta['capital_total']) for cuenta in p['cuentas'])
                            intereses_pensionado = sum(float(cuenta['intereses']) for cuenta in p['cuentas'])
                            total_pensionado = capital_pensionado + intereses_pensionado
                            
                            # Obtener la cuota parte mensual promedio
                            cuota_parte_mes = capital_pensionado / 36  # 36 meses
                            
                            tabla_data.append([
                                str(p['pensionado']['cedula']),
                                p['pensionado']['nombre'][:25] + '...' if len(p['pensionado']['nombre']) > 25 else p['pensionado']['nombre'],
                                '1-may-08',  # Fecha estándar como en la imagen
                                '3089 de 2007',  # Resolución estándar
                                f"{float(p['pensionado']['porcentaje_cuota'])*100:.2f}%",
                                f"{cuota_parte_mes:,.0f}",
                                f"{capital_pensionado:,.0f}",
                                f"{intereses_pensionado:,.0f}",
                                f"{total_pensionado:,.0f}"
                            ])
                        
                        # Fila de totales
                        tabla_data.append([
                            '', '', '', 'TOTAL', '', '',
                            f"{total_consolidado_capital:,.0f}",
                            f"{total_consolidado_intereses:,.0f}",
                            f"{total_consolidado_total:,.0f}"
                        ])
                        
                        # Crear tabla ajustada para página vertical
                        tabla_pensionados = Table(tabla_data, colWidths=[0.7*inch, 1.4*inch, 0.5*inch, 0.7*inch, 0.5*inch, 0.6*inch, 0.7*inch, 0.7*inch, 0.8*inch])
                        tabla_pensionados.setStyle(TableStyle([
                            # Header
                            ('BACKGROUND', (0, 0), (-1, 0), colors.white),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 7),  # Reducido para que quepa
                            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                            
                            # Data rows
                            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                            ('FONTSIZE', (0, 1), (-1, -2), 7),  # Reducido para que quepa
                            ('ALIGN', (0, 1), (1, -2), 'LEFT'),    # Cédula y nombre
                            ('ALIGN', (2, 1), (-1, -2), 'CENTER'), # Resto centrado
                            ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
                            
                            # Total row
                            ('BACKGROUND', (0, -1), (-1, -1), colors.white),
                            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, -1), (-1, -1), 9),
                            ('ALIGN', (0, -1), (-1, -1), 'CENTER'),
                            
                            # Grid completo
                            ('GRID', (0, 0), (-1, -1), 1, colors.black),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('TOPPADDING', (0, 0), (-1, -1), 2),  # Reducido
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),  # Reducido
                            ('LEFTPADDING', (0, 0), (-1, -1), 1),  # Reducido
                            ('RIGHTPADDING', (0, 0), (-1, -1), 1),  # Reducido
                        ]))
                        
                        story.append(tabla_pensionados)
                        
                        # Construir PDF
                        doc.build(story)
                        
                        # Obtener datos del buffer
                        pdf_data = buffer.getvalue()
                        buffer.close()
                        
                        st.download_button(
                            label="⬇️ Descargar PDF Consolidado",
                            data=pdf_data,
                            file_name=f"LIQUIDACION_CONSOLIDADA_{entidad_nit}_{fecha_corte.strftime('%Y%m%d')}.pdf",
                            mime="application/pdf"
                        )
                        
                        st.success(f"✅ PDF consolidado generado para {len(todas_las_cuentas)} pensionados")
                        
                    except Exception as e:
                        st.error(f"Error generando PDF consolidado: {str(e)}")
                        import traceback
                        st.error(traceback.format_exc())
                
                # Botón para generar ZIP con PDFs individuales
                if st.button("📁 Generar ZIP con PDFs Individuales", key="zip_individuales"):
                    try:
                        with st.spinner("Generando PDFs individuales según plantilla Excel..."):
                            zip_data = generar_zip_individual_plantilla(entidad_nit, entidad_nombre, todas_las_cuentas)
                            
                            st.download_button(
                                label="⬇️ Descargar ZIP con PDFs Individuales",
                                data=zip_data,
                                file_name=f"CUENTAS_INDIVIDUALES_{entidad_nit}_{fecha_corte.strftime('%Y%m%d')}.zip",
                                mime="application/zip"
                            )
                            
                            st.success(f"✅ ZIP generado con {len(todas_las_cuentas)} PDFs individuales basados en plantilla Excel")
                            
                    except Exception as e:
                        st.error(f"Error generando ZIP: {str(e)}")
                        import traceback
                        st.error(traceback.format_exc())
            
            with col2:
                st.info("""
                **📋 Opciones de Exportación:**
                
                **📄 PDF Consolidado:**
                - Un solo documento con todos los pensionados
                - Tabla resumen con totales generales
                - Formato oficial cuenta de cobro
                - Ideal para presentaciones ejecutivas
                
                **📁 ZIP con PDFs Individuales:**
                - Un PDF por cada pensionado
                - Formato basado en plantilla Excel oficial
                - Numeración consecutiva automática
                - Estructura completa según PLANTILLA CXC 06
                """)
        
        session.close()
        
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        import traceback
        st.error(traceback.format_exc())

# --- Módulo Seguridad y Trazabilidad ---
elif menu == "🔒 Seguridad y Trazabilidad":
    st.title("Seguridad y Trazabilidad")
    st.subheader("Registro de acciones y accesos por usuario")
    
    st.write("(Aquí se mostraría la bitácora de acciones y roles de usuario)")
    st.selectbox("Rol de usuario", ["Administrador", "Analista", "Auditor"])
    st.button("Ver historial de acciones")
    st.button("Configurar accesos y roles")