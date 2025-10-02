import streamlit as st
from datetime import date
from decimal import Decimal, InvalidOperation
from sqlalchemy import text
import os

st.set_page_config(page_title="Cuotas Partes", page_icon="📑", layout="wide")

# --- Estilos institucionales ---
st.markdown("""
    <style>
    .main {background-color: #232a34; color: #e3e6ea;}
    .stButton > button {background-color: #1a2940; color: #fff; font-weight: bold; border-radius: 8px;}
    .stTable {background-color: #232a34;}
    .stTabs [data-baseweb=\"tab\"] {background-color: #1a2940; color: #fff;}
    </style>
""", unsafe_allow_html=True)

# --- Menú lateral principal ---
st.sidebar.title("Menú")
menu = st.sidebar.radio(
    "Navegación",
    (
        "🏠 Dashboard",
        "👤 Pensionados",
        "📑 Liquidaciones",
        "💰 Pagos",
        "📤 Cobro Persuasivo",
        "📊 Reportes y Seguimiento",
        "⚖️ Liquidaciones Masivas (30 Cuentas)",
        "🔒 Seguridad y Trazabilidad",
        "🗓️ Liquidar por Periodos Personalizados",
    ),
    index=0,
    key="menu_principal",
)


# --- Utilidades: número a letras (es-CO) ---
def numero_a_letras(n: int) -> str:
    """Convierte un número entero a texto en español (simplificado para valores grandes)."""
    unidades = (
        "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
        "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve",
        "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"
    )
    # Debe tener 10 entradas (índices 0..9) para evitar IndexError cuando d=9 (noventa)
    # Notar que 10-29 se manejan en el bloque num < 30, pero dejamos 'diez' y 'veinte' por completitud
    decenas = ("", "diez", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa")
    centenas = ("", "cien", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos")

    def _decenas(num):
        if num < 30:
            return unidades[num]
        d, u = divmod(num, 10)
        if u == 0:
            return decenas[d]
        return f"{decenas[d]} y {unidades[u]}"

    def _centenas(num):
        if num < 100:
            return _decenas(num)
        c, r = divmod(num, 100)
        if c == 1:
            if r == 0:
                return "cien"
            return f"ciento {_decenas(r)}"
        return f"{centenas[c]}" if r == 0 else f"{centenas[c]} {_decenas(r)}"

    def _seccion(num, divisor, singular, plural):
        c, r = divmod(num, divisor)
        if c == 0:
            return "", r
        if c == 1:
            return f"{singular}", r
        return f"{numero_a_letras(c)} {plural}", r

    if n == 0:
        return "cero"
    if n < 0:
        return "menos " + numero_a_letras(-n)

    resultado = []
    millones, resto = _seccion(n, 1_000_000, "un millón", "millones")
    if millones:
        resultado.append(millones)
    miles, resto = _seccion(resto, 1_000, "mil", "mil")
    if miles:
        resultado.append(miles)
    if resto:
        resultado.append(_centenas(resto))
    return " ".join([p for p in resultado if p])


def generar_pdf_consolidado_en_memoria(entidad_nit: str, entidad_nombre: str, todas_las_cuentas: list, fecha_corte: date):
    """
    Genera el PDF consolidado EXACTAMENTE con la misma lógica/formatos del botón "📄 PDF Consolidado".
    Devuelve una tupla (bytes_pdf, nombre_archivo).
    """
    # Imports locales para evitar dependencias globales
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    import io, calendar
    from dateutil.relativedelta import relativedelta

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=0.3*inch, leftMargin=0.3*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=8, alignment=TA_CENTER, fontName='Helvetica-Bold')
    normal_style = styles['Normal']
    normal_left_bold = ParagraphStyle('NormalLeftBold', parent=styles['Normal'], fontSize=10, alignment=TA_LEFT, fontName='Helvetica-Bold')

    story = []

    # Encabezado: ciudad y CUENTA DE COBRO + No.
    story.append(Spacer(1, 0.5*inch))
    header_line1 = Table([["BOGOTÁ, D.C.", "CUENTA DE COBRO"]], colWidths=[4*inch, 3*inch])
    header_line1.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(header_line1)

    # Número de cuenta (persistencia simple como en botón; usamos archivo en disco para mantenerse igual)
    try:
        with open('ultimo_consecutivo.txt', 'r') as f:
            ultimo_consecutivo = int(f.read().strip())
    except Exception:
        ultimo_consecutivo = 423
    nuevo_consecutivo = ultimo_consecutivo + 1
    with open('ultimo_consecutivo.txt', 'w') as f:
        f.write(str(nuevo_consecutivo))

    numero_table = Table([["", f"No.  {nuevo_consecutivo}"]], colWidths=[4*inch, 3*inch])
    numero_table.setStyle(TableStyle([
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (1, 0), (1, 0), 14),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
    ]))
    story.append(numero_table)

    story.append(Spacer(1, 0.3*inch))

    # Entidad acreedora (encabezado)
    entidad_nombre_pdf = entidad_nombre
    story.append(Paragraph(f"<b>{entidad_nombre_pdf.upper()}</b>", title_style))
    story.append(Paragraph(f"<b>NIT: {entidad_nit}</b>", title_style))

    story.append(Spacer(1, 0.4*inch))

    # DEBE A: (mismo nombre/nit)
    story.append(Paragraph("<b>DEBE A:</b>", title_style))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"<b>{entidad_nombre_pdf.upper()}</b>", title_style))
    story.append(Paragraph(f"<b>NIT: {entidad_nit}</b>", title_style))

    # Totales consolidados (usando la misma suma que el botón)
    total_consolidado_capital = 0.0
    total_consolidado_intereses = 0.0
    total_consolidado_total = 0.0
    for p in todas_las_cuentas:
        capital_pensionado = sum(float(cuenta['capital_total']) for cuenta in p['cuentas'])
        intereses_pensionado = sum(float(cuenta['intereses']) for cuenta in p['cuentas'])
        total_pensionado = capital_pensionado + intereses_pensionado
        total_consolidado_capital += capital_pensionado
        total_consolidado_intereses += intereses_pensionado
        total_consolidado_total += total_pensionado

    story.append(Spacer(1, 0.3*inch))

    # Valor en letras y numérico
    valor_letras = numero_a_letras(int(total_consolidado_total))
    story.append(Paragraph(f"<b>LA SUMA DE: {valor_letras.upper()} PESOS M/CTE</b>", normal_style))
    story.append(Paragraph(f"<b>$ {total_consolidado_total:,.0f}</b>", normal_left_bold))

    story.append(Spacer(1, 0.4*inch))

    # Concepto con periodo de 30 meses (inicio-fin), meses en español
    meses_es = {1:'enero',2:'febrero',3:'marzo',4:'abril',5:'mayo',6:'junio',7:'julio',8:'agosto',9:'septiembre',10:'octubre',11:'noviembre',12:'diciembre'}
    _fecha_fin = date(fecha_corte.year, fecha_corte.month, 1)
    _fecha_ini = _fecha_fin - relativedelta(months=29)
    inicio_txt = f"01 de {meses_es[_fecha_ini.month].capitalize()} de {_fecha_ini.year}"
    ultimo_dia = calendar.monthrange(_fecha_fin.year, _fecha_fin.month)[1]
    fin_txt = f"{ultimo_dia} de {meses_es[_fecha_fin.month].capitalize()} de {_fecha_fin.year}"
    concepto_text = (
        "Por concepto de Cuotas Partes Pensionales sobre pagos realizados en la nómina de Pensionados del SENA "
        f"a fecha de corte {inicio_txt} a corte de {fin_txt} por los pensionados que se relacionan a continuación:"
    )
    story.append(Paragraph(concepto_text, normal_style))
    story.append(Spacer(1, 0.3*inch))

    # Tabla principal
    tabla_data = [[
        'No. Cédula', 'Apellidos y Nombres', 'Ingreso\nNómina', 'RESOLUCIÓN\nNº', '% Cuota\nParte', 'Base\nCálculo\nCuota',
        'Saldo\nCapital\nCausado', 'Intereses\nAcumulados', 'TOTAL\nDEUDA'
    ]]

    for p in todas_las_cuentas:
        capital_pensionado = sum(float(cuenta['capital_total']) for cuenta in p['cuentas'])
        intereses_pensionado = sum(float(cuenta['intereses']) for cuenta in p['cuentas'])
        total_pensionado = capital_pensionado + intereses_pensionado
        base_calc = float(p['pensionado'].get('base_calculo_cuota', 0.0))
        nombre = p['pensionado']['nombre']
        nombre_corto = nombre[:25] + '...' if len(nombre) > 25 else nombre
        tabla_data.append([
            str(p['pensionado']['cedula']),
            nombre_corto,
            '1-may-08',
            '3089 de 2007',
            f"{float(p['pensionado']['porcentaje_cuota'])*100:.2f}%",
            f"{base_calc:,.0f}",
            f"{capital_pensionado:,.0f}",
            f"{intereses_pensionado:,.0f}",
            f"{total_pensionado:,.0f}"
        ])

    # Totales fila final
    tabla_data.append([
        '', '', '', 'TOTAL', '', '',
        f"{total_consolidado_capital:,.0f}",
        f"{total_consolidado_intereses:,.0f}",
        f"{total_consolidado_total:,.0f}"
    ])

    # Ajuste de anchos: tomar como referencia el bloque de "valor en letras" (área de texto)
    # Usamos un ancho objetivo ligeramente menor que el ancho util de la página para que no se vea desbordado.
    try:
        available_width = doc.width  # ancho útil (página - márgenes)
    except Exception:
        from reportlab.lib.pagesizes import letter as _letter
        available_width = _letter[0] - (0.3*inch + 0.3*inch)
    target_width = max(5.8*inch, available_width - 0.6*inch)  # ~0.3in de aire a cada lado respecto al texto

    # Pesos relativos por columna (proporciones estables)
    col_weights = [1.0, 2.2, 0.8, 0.9, 0.6, 0.8, 0.8, 0.8, 0.8]
    weights_sum = sum(col_weights)
    col_widths = [w/weights_sum * target_width for w in col_weights]

    tabla_pensionados = Table(tabla_data, colWidths=col_widths, hAlign='LEFT')
    light_header = colors.Color(0.94, 0.94, 0.94)
    light_row = colors.Color(0.985, 0.985, 0.985)
    tabla_pensionados.setStyle(TableStyle([
        # Encabezado gris claro, tipografía consistente y centrado
        ('BACKGROUND', (0, 0), (-1, 0), light_header),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

        # Filas: tamaño discreto, alineaciones refinadas como el ejemplo
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8),
        ('ALIGN', (0, 1), (0, -2), 'RIGHT'),   # Cédula
        ('ALIGN', (1, 1), (1, -2), 'LEFT'),    # Nombres
        ('ALIGN', (2, 1), (3, -2), 'CENTER'),  # Ingreso nómina y Resolución
        ('ALIGN', (4, 1), (-1, -2), 'RIGHT'),  # % y valores
        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
        # Alternancia muy sutil para elegancia (casi blanco)
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, light_row]),

        # Fila de totales (última): énfasis en negrita y línea superior separadora
        ('BACKGROUND', (0, -1), (-1, -1), colors.white),
        ('FONTNAME', (5, -1), (5, -1), 'Helvetica-Bold'),
        ('FONTNAME', (6, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (5, -1), (-1, -1), 9),
        ('ALIGN', (6, -1), (-1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),

        # Grid delgado y paddings ajustados
        ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(tabla_pensionados)

    # Anexo por pensionado con detalle de las 30 cuentas
    story.append(PageBreak())
    subtitle_pensionado = ParagraphStyle('SubPens', parent=styles['Heading2'], fontSize=12, spaceAfter=4, alignment=TA_LEFT, fontName='Helvetica-Bold')
    small_right = ParagraphStyle('SmallRight', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT)
    small_center = ParagraphStyle('SmallCenter', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)
    small_left = ParagraphStyle('SmallLeft', parent=styles['Normal'], fontSize=8, alignment=TA_LEFT)

    for idx_p, p in enumerate(todas_las_cuentas):
        if idx_p > 0:
            story.append(PageBreak())
        story.append(Paragraph(
            f"Detalle de cuentas de cobro - {p['pensionado']['nombre']} (CC {p['pensionado']['cedula']})",
            subtitle_pensionado
        ))

        detalle_headers = [
            Paragraph('#', small_center),
            Paragraph('Período', small_center),
            Paragraph('Capital Total', small_center),
            Paragraph('Intereses', small_center),
            Paragraph('Total Cuenta', small_center),
        ]
        detalle_data = [detalle_headers]

        cuentas_ord = sorted(p['cuentas'], key=lambda c: (c['año'], c['mes']))
        subtotal_capital = subtotal_intereses = subtotal_total = 0.0
        for idx, cta in enumerate(cuentas_ord, start=1):
            periodo_txt = f"{meses_es[cta['mes']].upper()} {cta['año']}"
            cap = float(cta.get('capital_total', 0))
            inte = float(cta.get('intereses', 0))
            tot = float(cta.get('total_cuenta', cap + inte))
            subtotal_capital += cap
            subtotal_intereses += inte
            subtotal_total += tot
            detalle_data.append([
                Paragraph(f"{idx}", small_center),
                Paragraph(periodo_txt, small_center),
                Paragraph(f"${cap:,.2f}", small_right),
                Paragraph(f"${inte:,.2f}", small_right),
                Paragraph(f"${tot:,.2f}", small_right),
            ])

        detalle_data.append([
            Paragraph('', small_center),
            Paragraph('TOTAL', ParagraphStyle('SmallBoldCenter', parent=small_center, fontName='Helvetica-Bold')),
            Paragraph(f"${subtotal_capital:,.2f}", ParagraphStyle('SmallBoldRight', parent=small_right, fontName='Helvetica-Bold')),
            Paragraph(f"${subtotal_intereses:,.2f}", ParagraphStyle('SmallBoldRight', parent=small_right, fontName='Helvetica-Bold')),
            Paragraph(f"${subtotal_total:,.2f}", ParagraphStyle('SmallBoldRight', parent=small_right, fontName='Helvetica-Bold')),
        ])

        detalle_table = Table(detalle_data, colWidths=[0.5*inch, 1.2*inch, 1.2*inch, 1.1*inch, 1.2*inch], repeatRows=1)
        detalle_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(detalle_table)
        story.append(Spacer(1, 0.25*inch))
        story.append(Spacer(1, 0.1*inch))

    # Construir PDF y retornar bytes + nombre
    doc.build(story)
    pdf_data = buffer.getvalue()
    buffer.close()
    pdf_name = f"LIQUIDACION_CONSOLIDADA_{entidad_nit}_{fecha_corte.strftime('%Y%m%d')}.pdf"
    return pdf_data, pdf_name


def generar_readme_texto(entidad_nit: str, total_pensionados: int, total_cuentas: int, entidad_nombre: str) -> str:
    """Crea un README descriptivo para el ZIP exportado."""
    hoy = date.today().strftime("%d/%m/%Y")
    contenido = f"""
    CUENTAS PARTES - PAQUETE DE LIQUIDACIÓN (30 MESES)
    ==================================================

    Entidad: {entidad_nombre} (NIT: {entidad_nit})
    Fecha de generación: {hoy}

    Contenido:
    - CONSOLIDADO_GLOBAL.pdf (resumen ejecutivo y totales)
    - PDFs individuales por pensionado (30 cuentas por persona)

    Alcance metodológico:
    - Sistema de 30 cuentas independientes (mes vencido)
    - Capital fijo por cuenta, sin capitalización entre meses
    - Intereses por DTF mensual específica
    - Primas en junio y diciembre según número de mesadas

    Resumen del paquete:
    - Pensionados incluidos: {total_pensionados}
    - Total de cuentas independientes: {total_cuentas}

    Observaciones:
    - Septiembre no se factura en este corte; ventana: últimos 30 meses hasta agosto de 2025.
    - Este paquete es de uso interno y soporte de cobro persuasivo.
    """
    return "\n".join(line.rstrip() for line in contenido.splitlines()).strip() + "\n"

def generar_consolidado_global_texto(entidad_nit, entidad_nombre, todas_las_cuentas, total_capital, total_intereses, fecha_corte):
    """Genera el contenido del consolidado global en formato texto"""
    content = f"""
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    CONSOLIDADO GLOBAL - LIQUIDACIÓN 30 CUENTAS INDEPENDIENTES                    ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                                  ║
║  🏛️  ENTIDAD: {entidad_nombre:<70}                                        ║
║  🆔  NIT: {entidad_nit:<77}                                        ║
║  📅  FECHA LIQUIDACIÓN: {fecha_corte.strftime('%d/%m/%Y'):<65}                                        ║
║  📊  PERÍODO: SEPTIEMBRE 2022 - FEBRERO 2025 (30 MESES EXACTOS)                                               ║
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
║  📋  SISTEMA: 30 Cuentas de Cobro Independientes por Pensionado                                                ║
║  💰  CAPITAL: Fijo por cuenta (sin capitalización entre cuentas)                                               ║
║  📈  INTERESES: DTF mensual específica aplicada sobre capital fijo                                             ║
║  🏛️  CONCEPTO: Mes vencido - Cuentas históricas desde su propio mes                                            ║
║  🎁  PRIMAS: Incluidas en diciembre y junio según número de mesadas                                            ║
║  ⚖️  MARCO LEGAL: Sistema Anti-Prescripción según Ley 1066 de 2006                                             ║
║                                                                                                                  ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝

NOTA IMPORTANTE: Este consolidado representa la suma de {sum(len(p['cuentas']) for p in todas_las_cuentas)} cuentas de cobro independientes.
Cada pensionado tiene exactamente 30 cuentas mensuales según prescripción vigente.

Generado el {fecha_corte.strftime('%d/%m/%Y')} - Sistema Cuotas Partes v2.0
"""
    
    return content

def generar_resumen_pensionado_texto(pensionado_data):
    """Genera el resumen individual de un pensionado"""
    p = pensionado_data['pensionado']
    
    content = f"""
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                     RESUMEN INDIVIDUAL - 30 CUENTAS INDEPENDIENTES                              ║
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

DETALLE DE LAS 30 CUENTAS:
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

# (secciones duplicadas eliminadas)
• Los intereses se calculan con la DTF del mes de la cuenta (mes vencido)
• Este sistema evita la prescripción de cuotas partes (Ley 1066/2006)

🔧 SOPORTE TÉCNICO:
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Sistema: Cuotas Partes v2.0
Metodología: 30 Cuentas Independientes
Fecha generación: {date.today().strftime('%d/%m/%Y')}

Para consultas técnicas sobre la liquidación, contactar al administrador del sistema.
"""
    
    return content


def generar_zip_masivo_completo(entidad_nit: str, entidad_nombre: str, todas_las_cuentas: list, fecha_corte: date) -> bytes:
    """
    Crea un ZIP en memoria con la estructura completa:
    - README.txt
    - CONSOLIDADO_GLOBAL.pdf
    - Carpeta por pensionado:
        - Carpeta por año:
            - PDF de cuenta de cobro individual.
    """
    import io
    import zipfile
    import os
    from datetime import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    
    # Importar la función de generación de PDF individual
    from generar_pdf_oficial import generar_pdf_para_pensionado

    def _sanitize(name: str) -> str:
        import re
        name = name.strip().replace(' ', '_')
        name = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9_-]", '', name)
        return name

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        top_dir = f"{_sanitize(entidad_nombre)}_{entidad_nit}"
        # 1. README
        readme_content = generar_readme_texto(
            entidad_nit,
            len(todas_las_cuentas),
            sum(len(p.get('cuentas', [])) for p in todas_las_cuentas),
            entidad_nombre,
        )
        zf.writestr(f"{top_dir}/README.txt", readme_content)

        # 2. PDF Consolidado: usar la MISMA función del botón "PDF Consolidado"
        #    Preferimos reutilizar el PDF ya generado en la sesión; si no existe, lo generamos aquí.
        temp_dir = "temp_pdf_generation"
        os.makedirs(temp_dir, exist_ok=True)
        error_log_path = os.path.join(temp_dir, "error_log.txt")

        try:
            try:
                import streamlit as st  # puede no estar disponible en algunos contextos
                pdf_bytes = st.session_state.get('pdf_consolidado_data')
                pdf_name = st.session_state.get('pdf_consolidado_name')
            except Exception:
                pdf_bytes = None
                pdf_name = None

            if not pdf_bytes or not pdf_name:
                # Generar con la misma lógica empleada por el botón
                pdf_bytes, pdf_name = generar_pdf_consolidado_en_memoria(
                    entidad_nit=entidad_nit,
                    entidad_nombre=entidad_nombre,
                    todas_las_cuentas=todas_las_cuentas,
                    fecha_corte=fecha_corte,
                )

            if pdf_bytes and pdf_name:
                zf.writestr(os.path.join(top_dir, pdf_name), pdf_bytes)
        except Exception as e:
            with open(error_log_path, "a", encoding="utf-8") as f:
                f.write(f"Error generando/anexando PDF consolidado de la entidad {entidad_nombre} (NIT: {entidad_nit}): {e}\n")

        # 3. Generar PDFs individuales y organizarlos en carpetas

        for pensionado_data in todas_las_cuentas:
            pensionado_info = pensionado_data['pensionado']
            
            # Reconstruir la tupla de pensionado que espera `generar_pdf_para_pensionado`
            # (identificacion, nombre, numero_mesadas, fecha_ingreso_nomina, empresa, base_calculo, porcentaje, nit)
            # Los índices pueden variar, es crucial ajustarlos al `pensionado_data` real.
            base_calc = pensionado_info.get('base_calculo_cuota', 0.0)
            try:
                base_calc = float(base_calc)
            except Exception:
                base_calc = 0.0
            porcentaje = pensionado_info.get('porcentaje_cuota', 0.0)
            try:
                porcentaje = float(porcentaje)
            except Exception:
                pass
            pensionado_tuple = (
                str(pensionado_info['cedula']),
                pensionado_info['nombre'],
                int(pensionado_info.get('mesadas', 12)),
                None,  # fecha_ingreso_nomina (no requerida por el cálculo)
                entidad_nombre,
                base_calc,
                porcentaje,
                str(entidad_nit),
            )

            for cuenta in pensionado_data['cuentas']:
                año = cuenta['año']
                mes = cuenta['mes']
                
                # Generar el PDF para una sola cuenta (un mes)
                # La función `generar_pdf_para_pensionado` crea el archivo en disco.
                try:
                    pdf_path = generar_pdf_para_pensionado(
                        pensionado=pensionado_tuple,
                        periodo='custom',
                        año_inicio=año,
                        mes_inicio=mes,
                        solo_mes=True, # ¡Importante para generar solo 1 cuenta!
                        output_dir=temp_dir # Guardar en una carpeta temporal
                    )
                    
                    if pdf_path and os.path.exists(pdf_path):
                        # Construir la ruta deseada dentro del ZIP
                        # Ej: Suarez_Mootoo_15240013/2023/15240013_Enero_2023.pdf
                        base_name = os.path.basename(pdf_path)
                        
                        # Extraer nombre de carpeta del pensionado desde la ruta generada
                        # La ruta es como temp_pdf_generation/Pensionado_ID/archivo.pdf
                        pensioner_folder_name = os.path.basename(os.path.dirname(pdf_path))
                        zip_path = os.path.join(top_dir, pensioner_folder_name, str(año), base_name)
                        
                        # Añadir el archivo al ZIP
                        zf.write(pdf_path, arcname=zip_path)
                        
                        # Opcional: eliminar el archivo temporal para no ocupar espacio
                        os.remove(pdf_path)

                except Exception as e:
                    # Registrar el error para no detener todo el proceso y continuar
                    error_log_path = os.path.join(temp_dir, "error_log.txt")
                    with open(error_log_path, "a", encoding="utf-8") as f:
                        f.write(f"Error generando PDF para {pensionado_info['cedula']} (Mes: {mes}/{año}): {e}\n")

        # Incluir el log de errores (si existe) dentro del ZIP para diagnóstico
        error_log_path = os.path.join(temp_dir, "error_log.txt")
        if os.path.exists(error_log_path):
            with open(error_log_path, "rb") as f:
                zf.writestr(f"{top_dir}/error_log.txt", f.read())

    # Limpiar la carpeta temporal
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    return zip_buffer.getvalue()

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

        entidad_sel = st.selectbox(
            "Selecciona entidad",
            entidades,
            format_func=lambda e: f"{e.nombre} ({e.nit})" if e else "",
            key="liq_entidad_sel"
        )
        pensionado_sel = st.selectbox(
            "Selecciona pensionado",
            pensionados,
            format_func=lambda p: f"{p.nombre} ({p.identificacion})" if p else "",
            key="liq_pensionado_sel"
        )
        periodo = st.date_input("Período a liquidar", value=date.today(), key="liq_periodo")
        valor_base = st.number_input("Valor base de cálculo", min_value=0.0, step=1000.0, key="liq_valor_base")
        tasa_dtf = st.number_input("Interés DTF (%)", min_value=0.0, step=0.01, key="liq_tasa_dtf")
        calcular = st.button("Liquidar cuenta", key="liq_btn_liquidar")

        st.markdown("---")

        if calcular and pensionado_sel and entidad_sel:
            # Simulación de cálculo real
            capital = valor_base
            interes = capital * (tasa_dtf / 100)
            total = capital + interes

            df = pd.DataFrame([
                {
                    "Pensionado": pensionado_sel.nombre,
                    "Identificación": pensionado_sel.identificacion,
                    "Entidad": entidad_sel.nombre,
                    "Periodo": periodo.strftime('%Y-%m'),
                    "Capital": f"{capital:,.2f}",
                    "Interés": f"{interes:,.2f}",
                    "Total": f"{total:,.2f}"
                }
            ])

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

# --- Módulo Liquidaciones Masivas (30 Cuentas) ---
elif menu == "⚖️ Liquidaciones Masivas (30 Cuentas)":
    st.title("⚖️ Liquidaciones Masivas (30 Cuentas Independientes)")
    
    st.markdown("""
    ### 📋 Sistema Corregido de 30 Cuentas Independientes
    **🎯 Objetivo:** Generar 30 cuentas de cobro independientes por pensionado (mes vencido).
    
    **💡 Metodología Corregida:**
    - **📅 Período:** Últimos 30 meses hasta agosto de 2025 (septiembre no se toma por facturar)
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
        import os
        
        # Importar las funciones del sistema corregido (desde el paquete scripts)
        from scripts.liquidacion_36_cuentas_corregida import (
            obtener_pensionados_entidad, 
            calcular_cuenta_mensual, 
            obtener_dtf_mes,
            tiene_prima_mes,
            calcular_interes_mensual,
            calcular_dias_mes
        )
        from mostrar_liquidacion_36 import ajustar_base_por_ipc
        # Usar la misma fórmula de intereses que el PDF de "solo mes" para alinear valores
        from mostrar_liquidacion_36 import calcular_interes_mensual_unico
        
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
                    format_func=lambda x: x[1],
                    key="masivas_entidad"
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
                value=date(2025, 8, 31),
                help="Usado para calcular los últimos 30 meses (mes vencido).",
                key="masivas_fecha_corte"
            )
            
            st.info(f"""
            **📆 Período (dinámico):**
            - Últimos 30 meses hasta la fecha de corte seleccionada
            - Con corte agosto 2025: 01/03/2023 → 31/08/2025 (30 meses)
            - 💰 **Metodología:** Mes vencido
            """)
        
        st.markdown("---")
        
        # Botón de generación
        if st.button("🚀 Generar 30 Cuentas de Cobro", type="primary"):
            if entidad_nit:
                with st.spinner("⏳ Generando las 30 cuentas independientes..."):
                    try:
                        from decimal import Decimal, InvalidOperation
                        from datetime import date
                        from dateutil.relativedelta import relativedelta
                        
                        # Obtener pensionados de la entidad
                        pensionados = obtener_pensionados_entidad(session, entidad_nit)
                        
                        if not pensionados:
                            st.error(f"No se encontraron pensionados para la entidad {entidad_nit}")
                        else:
                            # Período dinámico: últimos 30 meses hasta fecha_corte
                            from dateutil.relativedelta import relativedelta
                            fecha_final = date(fecha_corte.year, fecha_corte.month, 1)
                            fecha_inicial = fecha_final - relativedelta(months=29)
                            
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
                                
                                # Generar 30 cuentas para este pensionado
                                fecha_cuenta = fecha_inicial
                                consecutivo = 1
                                total_pensionado = Decimal('0')
                                
                                cuentas_pensionado = []

                                # Base cálculo cuota original del pensionado (para mostrar en consolidado)
                                try:
                                    base_calculo_cuota_parte_origen = float(pensionado[8]) if pensionado[8] else 383628.0
                                except (ValueError, IndexError, TypeError):
                                    base_calculo_cuota_parte_origen = 383628.0
                                
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
                                    
                                    # Ajustar base por IPC (base 2025 → año de la cuenta) usando la misma función que el cálculo individual
                                    base_ajustada_año = ajustar_base_por_ipc(float(base_calculo_cuota_parte), fecha_cuenta.year)
                                    
                                    # Calcular capital fijo de la cuenta usando la base ajustada por IPC
                                    capital_base = Decimal(str(base_ajustada_año)) * porcentaje_cuota
                                    
                                    # Determinar si tiene prima
                                    tiene_prima = tiene_prima_mes(numero_mesadas, fecha_cuenta.month)
                                    prima = capital_base if tiene_prima else Decimal('0')
                                    capital_total = capital_base + prima
                                    
                                    # Calcular intereses acumulativos para ESTA cuenta específica
                                    fecha_actual = fecha_cuenta
                                    # Limitar intereses hasta el primer día del mes de corte
                                    fecha_limite = date(fecha_corte.year, fecha_corte.month, 1)
                                    interes_acumulado = Decimal('0')
                                    
                                    # Iterar mes a mes DESDE el mes de la cuenta hasta el mes de corte
                                    while fecha_actual <= fecha_limite:
                                        # Interés del mes usando la misma fórmula que el PDF individual (capital fijo)
                                        interes_mes = calcular_interes_mensual_unico(float(capital_total), fecha_actual, fecha_corte)
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
                                        'pensionado_id': pensionado[0],  # pensionado_id está en índice 0
                                        'base_calculo_cuota': base_calculo_cuota_parte_origen
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
                        st.error(f"❌ Error generando las 30 cuentas de cobro: {str(e)}")
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
                    'Base Cálculo': f"${float(p['pensionado'].get('base_calculo_cuota', 0.0)):,.2f}",
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
                "Selecciona un pensionado para ver sus 30 cuentas:",
                options=[i for i, _ in pensionado_names],
                format_func=lambda x: pensionado_names[x][1],
                key="masivas_selector_pensionado"
            )
            
            if selected_pensionado_idx is not None:
                pensionado_detalle = todas_las_cuentas[selected_pensionado_idx]
                
                st.write(f"**👤 {pensionado_detalle['pensionado']['nombre']}** - Total: ${float(pensionado_detalle['total_pensionado']):,.2f}")
                
                # Mostrar las 30 cuentas
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

            # Placeholders para evitar botones duplicados tras múltiples clics
            if 'pdf_consolidado_data' not in st.session_state:
                st.session_state['pdf_consolidado_data'] = None
            if 'pdf_consolidado_name' not in st.session_state:
                st.session_state['pdf_consolidado_name'] = None
            if 'zip_masivo_data' not in st.session_state:
                st.session_state['zip_masivo_data'] = None
            if 'zip_masivo_name' not in st.session_state:
                st.session_state['zip_masivo_name'] = None

            col1, col2 = st.columns(2)

            with col1:
                pdf_dl_placeholder = st.empty()
                zip_dl_placeholder = st.empty()

                if st.button("📄 PDF Consolidado", type="primary", use_container_width=True):
                    try:
                        pdf_data, pdf_name = generar_pdf_consolidado_en_memoria(
                            entidad_nit=entidad_nit,
                            entidad_nombre=next((e.nombre for e in entidades if e.nit == entidad_nit), str(entidad_nit)),
                            todas_las_cuentas=todas_las_cuentas,
                            fecha_corte=fecha_corte,
                        )
                        st.session_state['pdf_consolidado_data'] = pdf_data
                        st.session_state['pdf_consolidado_name'] = pdf_name

                        pdf_dl_placeholder.download_button(
                            label="⬇️ Descargar PDF Consolidado",
                            data=st.session_state['pdf_consolidado_data'],
                            file_name=st.session_state['pdf_consolidado_name'],
                            mime="application/pdf",
                            key="download_pdf_consolidado"
                        )
                        st.success(f"✅ PDF consolidado generado para {len(todas_las_cuentas)} pensionados")
                    except Exception as e:
                        st.error(f"Error generando PDF consolidado: {str(e)}")
                        import traceback
                        st.error(traceback.format_exc())
                
                # Botón para generar ZIP con la nueva estructura de carpetas por año
                if st.button("📁 Generar ZIP (carpetas por año)", key="zip_masivo_completo"):
                    try:
                        with st.spinner("⏳ Generando ZIP con estructura de carpetas por año..."):
                            # Obtener el nombre de la entidad para el nombre del archivo
                            entidad_nombre = next((e.nombre for e in entidades if e.nit == entidad_nit), "ENTIDAD")
                            
                            # Llamar a la nueva función que genera el ZIP con subcarpetas de año
                            zip_data = generar_zip_masivo_completo(
                                entidad_nit=entidad_nit,
                                entidad_nombre=entidad_nombre,
                                todas_las_cuentas=todas_las_cuentas,
                                fecha_corte=fecha_corte
                            )

                            # Guardar en session_state y renderizar/actualizar botón único
                            st.session_state['zip_masivo_data'] = zip_data
                            st.session_state['zip_masivo_name'] = f"LIQUIDACION_MASIVA_{entidad_nit}_{fecha_corte.strftime('%Y%m%d')}.zip"

                            zip_dl_placeholder.download_button(
                                label="⬇️ Descargar ZIP (carpetas por año)",
                                data=st.session_state['zip_masivo_data'],
                                file_name=st.session_state['zip_masivo_name'],
                                mime="application/zip",
                                key="download_zip_masivo"
                            )

                            st.success(f"✅ ZIP generado con {len(todas_las_cuentas)} pensionados y estructura de carpetas por año.")
                            
                    except Exception as e:
                        st.error(f"❌ Error generando el ZIP masivo: {str(e)}")
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

            # Renderización persistente de botones de descarga (si ya hay datos en session_state)
            with col1:
                if st.session_state.get('pdf_consolidado_data'):
                    st.download_button(
                        label="⬇️ Descargar PDF Consolidado",
                        data=st.session_state['pdf_consolidado_data'],
                        file_name=st.session_state['pdf_consolidado_name'],
                        mime="application/pdf",
                        key="download_pdf_consolidado_persist"
                    )
                if st.session_state.get('zip_masivo_data'):
                    st.download_button(
                        label="⬇️ Descargar ZIP (carpetas por año)",
                        data=st.session_state['zip_masivo_data'],
                        file_name=st.session_state['zip_masivo_name'],
                        mime="application/zip",
                        key="download_zip_masivo_persist"
                    )
        
        session.close()
        
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        import traceback
        st.error(traceback.format_exc())

# (secciones duplicadas eliminadas: mantener solo las versiones actualizadas más abajo)

    

# --- Módulo Seguridad y Trazabilidad ---
elif menu == "🔒 Seguridad y Trazabilidad":
    st.title("Seguridad y Trazabilidad")
    st.subheader("Registro de acciones y accesos por usuario")
    
    st.write("(Aquí se mostraría la bitácora de acciones y roles de usuario)")
    st.selectbox("Rol de usuario", ["Administrador", "Analista", "Auditor"])
    st.button("Ver historial de acciones")
    st.button("Configurar accesos y roles")

# --- Módulo Liquidar por Periodos Personalizados ---
elif menu == "🗓️ Liquidar por Periodos Personalizados":
    st.title("Liquidar por Periodos Personalizados")
    st.write("Selecciona la entidad, el rango de fechas y los meses que deseas excluir. Se generará un PDF individual por cada periodo seleccionado.")

    from datetime import date
    from app.db import get_session
    session = get_session()
    entidades = session.execute(text("SELECT nit, nombre FROM entidad ORDER BY nombre")).fetchall()
    entidad_nit = st.selectbox("Entidad", options=[e[0] for e in entidades], format_func=lambda x: next(e[1] for e in entidades if e[0]==x))

    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    modo = st.radio("Modo de selección", ["Rango de fechas", "Un solo mes"], horizontal=True)

    fecha_inicio = None
    fecha_fin = None
    excluir_meses = []
    solo_un_mes = True
    excluir_meses_por_año = {}

    if modo == "Rango de fechas":
        col1, col2 = st.columns(2)
        with col1:
            # Inicio no puede ser antes de Mar 2023 por la ventana de 30 meses definida
            fecha_inicio = st.date_input("Fecha inicio", value=date(2023,3,1), min_value=date(2023,3,1), max_value=date(2025,8,31))
        with col2:
            fecha_fin = st.date_input("Fecha fin", value=date(2025,8,31), min_value=fecha_inicio or date(2023,3,1), max_value=date(2025,8,31))
    # Excluir meses por año dentro del rango seleccionado
        st.markdown("**Excluir meses por año**")
        # Botón para limpiar exclusiones rápidamente (estabiliza estado al cambiar de ventana/rango)
        if st.button("Limpiar exclusiones", key="btn_limpiar_exclusiones"):
            for a in range(2022, 2026):
                k = f"excluir_{a}"
                if k in st.session_state:
                    del st.session_state[k]
        global_inicio = date(2022, 9, 1)
        global_fin = date(2025, 8, 31)
        # Iterar por cada año del rango seleccionado
        # Renderizar SIEMPRE los años de 2022 a 2025 para evitar cambios dinámicos en el DOM
        for año in range(2022, 2026):
            # Mantener opciones constantes (12 meses) para estabilidad del DOM
            keyname = f"excluir_{año}"
            # Sanear posibles valores previos fuera de las opciones válidas
            if keyname in st.session_state:
                prev = st.session_state[keyname]
                if isinstance(prev, (list, tuple)):
                    filtrado = [v for v in prev if v in meses]
                    if filtrado != prev:
                        st.session_state[keyname] = filtrado
            seleccion = st.multiselect(
                f"Excluir meses {año}",
                options=meses,
                help="Los meses fuera del rango seleccionado se ignoran automáticamente",
                key=keyname
            )
            # Mapear nombres seleccionados a números de mes
            excluir_meses_por_año[año] = set(meses.index(nombre) + 1 for nombre in seleccion)
        solo_un_mes = st.checkbox("Generar solo ese mes por PDF (no acumulado)", value=True)
    else:
        # Un solo mes: permitir elegir año y mes dentro de [Sep 2022, Ago 2025]
        col1, col2 = st.columns(2)
        with col1:
            año_sel = st.selectbox("Año", options=[2022, 2023, 2024, 2025], index=0)
        with col2:
            # Limitar meses según año seleccionado
            if año_sel == 2022:
                meses_idx = list(range(9, 13))  # Sep-Dic
            elif año_sel == 2025:
                meses_idx = list(range(1, 9))   # Ene-Ago
            else:
                meses_idx = list(range(1, 13))  # Todo el año
            nombres_filtrados = [meses[i-1] for i in meses_idx]
            mes_nombre = st.selectbox("Mes", options=nombres_filtrados)
            mes_sel = meses.index(mes_nombre) + 1

        # Construir fechas de inicio y fin del mes seleccionado
        from calendar import monthrange
        fecha_inicio = date(año_sel, mes_sel, 1)
        dia_fin = monthrange(año_sel, mes_sel)[1]
        fecha_fin = date(año_sel, mes_sel, dia_fin)
        solo_un_mes = True  # Forzar modo de un solo mes

    # PREVISUALIZACIÓN: construir lista de periodos resultantes antes de generar
    periodos_preview = []
    if modo == "Un solo mes" and fecha_inicio is not None:
        periodos_preview.append((fecha_inicio.year, fecha_inicio.month))
    elif modo == "Rango de fechas" and fecha_inicio is not None and fecha_fin is not None:
        actual = fecha_inicio
        while actual <= fecha_fin:
            excl_for_year = excluir_meses_por_año.get(actual.year, set())
            if actual.month not in excl_for_year:
                periodos_preview.append((actual.year, actual.month))
            if actual.month == 12:
                actual = date(actual.year+1, 1, 1)
            else:
                actual = date(actual.year, actual.month+1, 1)

    # Guardar en session_state para que métricas y generación usen exactamente la misma lista
    st.session_state['periodos_preview'] = periodos_preview

    # Contar pensionados de la entidad para estimar PDFs
    try:
        total_pensionados = session.execute(
            text("SELECT COUNT(*) FROM pensionado WHERE nit_entidad = :nit"), {"nit": entidad_nit}
        ).scalar() or 0
    except Exception:
        total_pensionados = 0

    colp1, colp2, colp3 = st.columns(3)
    with colp1:
        st.metric("Periodos seleccionados", len(st.session_state.get('periodos_preview', [])))
    with colp2:
        st.metric("Pensionados", total_pensionados)
    with colp3:
        st.metric("PDFs estimados", len(st.session_state.get('periodos_preview', [])) * total_pensionados)

    # Lista legible de periodos
    if st.session_state.get('periodos_preview'):
        etiquetas = [f"{meses[m-1]} {a}" for a, m in st.session_state['periodos_preview']]
        with st.expander("Ver periodos seleccionados"):
            st.write(", ".join(etiquetas))

    if st.button("Generar PDFs por periodo"):
        from generar_pdf_oficial import generar_pdf_para_pensionado
        pensionados = session.execute(
            text("SELECT identificacion, nombre, numero_mesadas, fecha_ingreso_nomina, empresa, base_calculo_cuota_parte, porcentaje_cuota_parte, nit_entidad FROM pensionado WHERE nit_entidad = :nit"),
            {"nit": entidad_nit}
        ).fetchall()
        # Construir carpeta base por entidad: <3 primeras letras>_<NIT>
        # Obtener nombre de entidad
        entidad_row = session.execute(text("SELECT nombre FROM entidad WHERE nit = :nit"), {"nit": entidad_nit}).fetchone()
        entidad_nombre = (entidad_row[0] if entidad_row else str(entidad_nit))
        prefijo = entidad_nombre.strip().upper()[:3].replace(' ', '')
        carpeta_entidad = f"{prefijo}_{entidad_nit}"
        base_dir = os.path.join(os.path.dirname(__file__), 'reportes_liquidacion', carpeta_entidad)
        os.makedirs(base_dir, exist_ok=True)
        # Reusar la lista de periodos ya calculada en la previsualización
        for pensionado in pensionados:
            for año, mes in st.session_state.get('periodos_preview', []):
                generar_pdf_para_pensionado(pensionado, 'custom', año, mes, solo_mes=solo_un_mes, output_dir=base_dir)
        st.success(f"PDFs generados para {len(pensionados)} pensionados y {len(st.session_state.get('periodos_preview', []))} periodos seleccionados.")