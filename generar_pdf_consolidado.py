#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Genera la Cuenta de Cobro consolidada por entidad (NIT):
- Encabezado: ciudad y "CUENTA DE COBRO Nro. <consecutivo>"
- Bloque central: Nombre entidad y NIT; "DEBE A:" y nombre del deudor
- Línea "LA SUMA DE:" con el total en letras y el valor numérico
- Párrafo de concepto con período (desde primera cuenta hasta última)
- Tabla detallada por pensionado: No. Cédula, Nombre, Ingreso nómina, Resolución No, % Cuota Parte,
  Vr. Cuota Parte Mes, Saldo Capital Causado, Intereses Acumulados, TOTAL DEUDA

El consecutivo se toma como el siguiente número global de la tabla cuenta_cobro.
Se registra una fila de trazabilidad con identificacion = f"ENTIDAD-{nit}" para control básico.
"""

import os
import sys
from datetime import date, datetime
from typing import List, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from sqlalchemy import text, select, func

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.db import get_session, engine
from app.models import Base, CuentaCobro
from mostrar_liquidacion_36 import generar_36_cuentas_pensionado


# ---------------- Consecutivo y trazabilidad (reutilizado) -----------------
_cuenta_table_ready = False

def _ensure_cuenta_table():
    global _cuenta_table_ready
    if _cuenta_table_ready:
        return
    try:
        Base.metadata.create_all(engine, tables=[CuentaCobro.__table__])
    except Exception:
        pass
    _cuenta_table_ready = True

def _db_get_next_consecutivo(session):
    max_val = session.execute(select(func.max(CuentaCobro.consecutivo))).scalar()
    return (max_val or 0) + 1


def _ensure_unique_filename(base_name: str) -> str:
    """If base_name exists or is locked, return a variant with a numeric suffix or timestamp."""
    if not os.path.exists(base_name):
        return base_name
    # try adding _v2, _v3, ... up to reasonable limit
    base, ext = os.path.splitext(base_name)
    for i in range(2, 100):
        candidate = f"{base}_v{i}{ext}"
        if not os.path.exists(candidate):
            return candidate
    # fallback to timestamp
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{base}_{ts}{ext}"


# ---------------- Utilidades de formato -----------------
def _fmt_money(n: float) -> str:
    return f"$ {n:,.0f}" if abs(n) >= 1 else f"$ {n:,.2f}"

def _fmt_pct(decimal_val: float) -> str:
    return f"{decimal_val*100:.2f}%"

MESES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

def _ultimo_dia_mes(ano: int, mes: int) -> int:
    # Simple: meses de 30/31; Febrero 28 (suficiente para presentación)
    if mes in (1,3,5,7,8,10,12):
        return 31
    if mes == 2:
        return 29 if (ano % 400 == 0 or (ano % 100 != 0 and ano % 4 == 0)) else 28
    return 30

def _numero_en_letras_es(n: int) -> str:
    """Convierte un entero en letras (español), mayúsculas, con MILLÓN/MILLONES, MIL, etc."""
    n = int(round(n))
    if n == 0:
        return "CERO"

    unidades = (
        "", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
        "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve",
        "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"
    )
    decenas_txt = ("", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa")
    centenas_txt = ("", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos")

    def a_99(x: int) -> str:
        if x < 30:
            return unidades[x]
        d = x // 10
        u = x % 10
        if u == 0:
            return decenas_txt[d-2]
        return f"{decenas_txt[d-2]} y {unidades[u]}"

    def a_999(x: int) -> str:
        if x == 0:
            return ""
        if x == 100:
            return "cien"
        c = x // 100
        r = x % 100
        if c == 0:
            return a_99(r)
        if r == 0:
            return centenas_txt[c]
        return f"{centenas_txt[c]} {a_99(r)}"

    millones = n // 1_000_000
    resto_millones = n % 1_000_000
    miles = resto_millones // 1000
    resto = resto_millones % 1000

    partes = []
    if millones:
        if millones == 1:
            partes.append("un millón")
        else:
            partes.append(f"{a_999(millones)} millones")
    if miles:
        if miles == 1:
            partes.append("mil")
        else:
            partes.append(f"{a_999(miles)} mil")
    if resto:
        partes.append(a_999(resto))

    texto = " ".join([p for p in partes if p]).strip()
    # Ajustes: UNO -> UN antes de MILLÓN/MIL cuando corresponde ya resuelto; convertir a mayúsculas con tildes.
    return texto.upper().replace(" VEINTIUNO ", " VEINTIÚN ").replace(" VEINTIUNO", " VEINTIÚN")


# ---------------- Cálculo y armado datos -----------------
def _consultar_entidad_y_pensionados(nit: str):
    with get_session() as s:
        entidad = s.execute(text("SELECT nombre, nit FROM entidad WHERE nit = :nit"), {"nit": nit}).fetchone()
        pensionados = s.execute(text(
            """
            SELECT identificacion, nombre, numero_mesadas,
                   fecha_ingreso_nomina, empresa, base_calculo_cuota_parte,
                   porcentaje_cuota_parte, nit_entidad, res_no
            FROM pensionado
            WHERE nit_entidad = :nit AND estado_cartera = 'ACTIVO'
            ORDER BY nombre
            """
        ), {"nit": nit}).fetchall()
        return entidad, pensionados

def _agrupar_consolidadopor_pensionado(pensionado_row) -> dict:
    """Calcula totales para un pensionado usando generar_36_cuentas_pensionado."""
    cuentas = generar_36_cuentas_pensionado(pensionado_row, date(2025, 8, 31))
    total_capital = sum(c['capital'] for c in cuentas)
    total_intereses = sum(c['interes'] for c in cuentas)
    periodo_inicio = cuentas[0]['fecha_cuenta'] if cuentas else date(2022, 9, 1)
    periodo_fin = cuentas[-1]['fecha_cuenta'] if cuentas else date(2025, 8, 31)
    return {
        'id': pensionado_row[0],
        'nombre': pensionado_row[1],
        'num_mesadas': pensionado_row[2],
        'ingreso_nomina': pensionado_row[3],
        'empresa': pensionado_row[4],
        'base_calculo': float(pensionado_row[5] or 0),
        'porcentaje': float(pensionado_row[6] or 0),
        'nit': pensionado_row[7],
        'resolucion': pensionado_row[8] or '',
        'total_capital': float(total_capital),
        'total_interes': float(total_intereses),
        'total_deuda': float(total_capital + total_intereses),
        'periodo_inicio': periodo_inicio,
        'periodo_fin': periodo_fin,
        'vr_cuota_mes': float((pensionado_row[5] or 0) * (pensionado_row[6] or 0)),
    }


# ---------------- Render PDF -----------------
def generar_pdf_consolidado(nit: str, deudor: str = "SERVICIO NACIONAL DE APRENDIZAJE - SENA", ciudad: str = "BOGOTA, D.C.", deudor_nit: str = "899,999,034-1") -> str:
    entidad, pensionados = _consultar_entidad_y_pensionados(nit)
    if not entidad:
        raise ValueError(f"Entidad NIT {nit} no encontrada")
    if not pensionados:
        raise ValueError(f"No hay pensionados activos para NIT {nit}")

    # Calcular filas
    filas = [_agrupar_consolidadopor_pensionado(p) for p in pensionados]

    # Totales generales y período
    total_capital = sum(f['total_capital'] for f in filas)
    total_interes = sum(f['total_interes'] for f in filas)
    total_deuda = total_capital + total_interes

    # No generar un resumen consolidado por mes aquí: el consolidado debe presentarse
    # por pensionado (tabla detallada por pensionado). Se calculan únicamente las
    # fechas de inicio y fin para el encabezado y registro de trazabilidad.
    inicio = min(f['periodo_inicio'] for f in filas)
    fin = max(f['periodo_fin'] for f in filas)

    # Consecutivo global y registro de trazabilidad (modo simple)
    _ensure_cuenta_table()
    with get_session() as s:
        consecutivo = _db_get_next_consecutivo(s)
        ahora = datetime.now()
        base_name = f"CUENTA_COBRO_CONSOLIDADA_{nit}_{date.today().strftime('%Y%m%d')}.pdf"
        nombre_pdf = _ensure_unique_filename(base_name)
        reg = CuentaCobro(
            consecutivo=consecutivo,
            nit_entidad=str(nit),
            empresa=entidad[0],
            pensionado_identificacion=f"ENTIDAD-{nit}",
            pensionado_nombre="CONSOLIDADO",
            periodo_inicio=inicio,
            periodo_fin=fin,
            total_capital=total_capital,
            total_intereses=total_interes,
            total_liquidacion=total_deuda,
            archivo_pdf=nombre_pdf,
            estado='EMITIDA',
            version=1,
            fecha_creacion=ahora,
            fecha_actualizacion=ahora,
        )
        try:
            s.add(reg)
            s.commit()
        except Exception:
            s.rollback()
            # Si falla el registro, seguimos de todos modos

    # Documento
    doc = SimpleDocTemplate(
        nombre_pdf,
        pagesize=A4,
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1.2*cm,
        bottomMargin=1*cm,
    )

    story = []
    styles = getSampleStyleSheet()

    style_left_bold = ParagraphStyle('leftBold', parent=styles['Normal'], fontName='Helvetica-Bold', alignment=TA_LEFT, fontSize=11)
    style_right_bold = ParagraphStyle('rightBold', parent=styles['Normal'], fontName='Helvetica-Bold', alignment=TA_RIGHT, fontSize=11)
    style_center_title = ParagraphStyle('centerTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', alignment=TA_CENTER, fontSize=14, spaceAfter=4)
    style_center = ParagraphStyle('center', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12, spaceAfter=2)
    style_normal = ParagraphStyle('normal', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, leading=12)
    style_normal_bold = ParagraphStyle('normalBold', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, leading=12, fontName='Helvetica-Bold')
    style_header = ParagraphStyle('header', parent=styles['Normal'], fontName='Helvetica-Bold', alignment=TA_CENTER, fontSize=8)

    # Encabezado ciudad + consecutivo
    encabezado = Table([
        [Paragraph(ciudad, style_left_bold), Paragraph(f"CUENTA DE COBRO<br/>Nro.&nbsp;{consecutivo}", style_right_bold)]
    ], colWidths=[8*cm, 8*cm])
    encabezado.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(encabezado)
    story.append(Spacer(1, 0.6*cm))

    # Nombre entidad y NIT centrados
    story.append(Paragraph(entidad[0], style_center_title))
    story.append(Paragraph(str(entidad[1]), style_center))
    # Espacio adicional para empujar hacia abajo el bloque de 'LA SUMA DE' y la tabla
    story.append(Spacer(1, 0.8*cm))

    # DEBE A
    story.append(Paragraph("DEBE A:", style_center))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(deudor, style_center_title))
    if deudor_nit:
        story.append(Paragraph(deudor_nit, style_center))
    story.append(Spacer(1, 0.2*cm))

    # LA SUMA DE
    total_letras = _numero_en_letras_es(int(round(total_deuda)))
    story.append(Paragraph(f"LA SUMA DE:&nbsp; {total_letras} PESOS M/CTE", style_normal_bold))
    story.append(Paragraph(f"{_fmt_money(total_deuda)}", style_normal))
    story.append(Spacer(1, 0.2*cm))

    # Párrafo de concepto y período
    inicio_txt = f"01 de {MESES_ES[inicio.month]} de {inicio.year}"
    fin_txt = f"{_ultimo_dia_mes(fin.year, fin.month)} de {MESES_ES[fin.month]} de {fin.year}"
    parrafo = (
        "Por concepto de Cuotas Partes Pensionales sobre pagos realizados en la nómina de Pensionados del SENA "
        f"a fecha de corte {inicio_txt} a corte de {fin_txt} por los pensionados que se relacionan a continuación:"
    )
    story.append(Paragraph(parrafo, style_normal))
    story.append(Spacer(1, 0.3*cm))

    # Tabla
    headers = [
        Paragraph('No. Cédula', style_header),
        Paragraph('Apellidos y Nombres', style_header),
        Paragraph('Ingreso nómina', style_header),
        Paragraph('RESOLUCION N°', style_header),
        Paragraph('% Cuota Parte', style_header),
        Paragraph('Vr. Cuota Parte Mes', style_header),
        Paragraph('Saldo Capital Causado', style_header),
        Paragraph('Intereses Acumulados', style_header),
        Paragraph('TOTAL DEUDA', style_header),
    ]

    data = [headers]
    for f in filas:
        doc_id = f"{int(f['id']):,}"
        ingreso = f["ingreso_nomina"].strftime('%d-%b-%y').lower() if f["ingreso_nomina"] else ''
        data.append([
            doc_id,
            f['nombre'],
            ingreso,
            f['resolucion'],
            f"{f['porcentaje']*100:.2f}%",
            f"{int(round(f['vr_cuota_mes'])):,}",
            f"{int(round(f['total_capital'])):,}",
            f"{int(round(f['total_interes'])):,}",
            f"{int(round(f['total_deuda'])):,}",
        ])

    # Totales fila final
    data.append([
        '', '', '', '', '', 'TOTAL',
        f"{int(round(total_capital)):,}",
        f"{int(round(total_interes)):,}",
        f"{int(round(total_deuda)):,}",
    ])

    # Ajuste fino de anchos (suman ~19cm para márgenes de 1cm a cada lado)
    col_widths = [
        2.0*cm,  # No. Cédula
        4.2*cm,  # Apellidos y Nombres
        1.8*cm,  # Ingreso nómina
        2.0*cm,  # Resolución N°
        1.5*cm,  # % Cuota Parte
        2.0*cm,  # Vr. Cuota Parte Mes
        2.0*cm,  # Saldo Capital Causado
        1.8*cm,  # Intereses Acumulados
        1.7*cm,  # TOTAL DEUDA
    ]
    tabla = Table(data, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.8, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.Color(0.92,0.92,0.92)),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

        # Encabezados
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8.5),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),

        # Filas
        ('FONTSIZE', (0,1), (-1,-2), 8),
        ('ALIGN', (0,1), (0,-2), 'RIGHT'),   # Cédula
        ('ALIGN', (1,1), (1,-2), 'LEFT'),    # Nombres
        ('ALIGN', (2,1), (3,-2), 'CENTER'),  # Ingreso y Resolución
        ('ALIGN', (4,1), (-1,-2), 'RIGHT'),  # Valores y porcentajes

        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.Color(0.97,0.97,0.97)]),

        # Totales (última fila)
        ('FONTNAME', (5,-1), (5,-1), 'Helvetica-Bold'),
        ('FONTNAME', (6,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (5,-1), (-1,-1), 9),
        ('ALIGN', (6,-1), (-1,-1), 'RIGHT'),

        # Padding fino
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))

    story.append(tabla)

    # Render
    doc.build(story)
    print(f"✓ PDF consolidado generado: {nombre_pdf}")
    print(f"   - Entidad: {entidad[0]} (NIT {entidad[1]})")
    print(f"   - Consecutivo Nro.: {consecutivo}")
    print(f"   - Pensionados: {len(filas)}")
    print(f"   - Total capital: {_fmt_money(total_capital)} | Intereses: {_fmt_money(total_interes)} | Total: {_fmt_money(total_deuda)}")
    return nombre_pdf


def _main():
    import argparse
    parser = argparse.ArgumentParser(description='Generar Cuenta de Cobro consolidada por entidad (NIT)')
    parser.add_argument('--nit', required=True, help='NIT de la entidad (ej. 800103913)')
    parser.add_argument('--deudor', default='SERVICIO NACIONAL DE APRENDIZAJE - SENA', help='Nombre del deudor (DEBE A:)')
    parser.add_argument('--ciudad', default='BOGOTA, D.C.', help='Ciudad para el encabezado')
    args = parser.parse_args()

    generar_pdf_consolidado(args.nit, deudor=args.deudor, ciudad=args.ciudad)


if __name__ == '__main__':
    _main()
