import os
from datetime import date
import pandas as pd
from sqlalchemy import create_engine
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Configuración de conexión (ajusta tus credenciales)
DB_USER = 'root'
DB_PASS = 'BeMaster.1'
DB_HOST = 'localhost'
DB_PORT = '3306'
DB_NAME = 'liquidaciones'

# Carpeta de salida
OUTPUT_DIR = 'reportes_liquidacion'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Conexión SQLAlchemy
engine = create_engine(f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


# Leer la vista y forzar encabezados oficiales
query = "SELECT * FROM v_liq_mensual_reporte"
df = pd.read_sql(query, engine)

# Encabezados y orden oficiales
columnas_oficiales = [
    "No.",
    "APELLIDOS Y NOMBRES DEL PENSIONADO",
    "No. DOCUMENTO",
    "SUSTITUTO",
    "No. DOCUMENTO SUSTITUTO",
    "% DE CONCURRENCIA",
    "VALOR MESADA",
    "PERIODO LIQUIDADO (INICIO)",
    "PERIODO LIQUIDADO (FIN)",
    "CAPITAL",
    "INTERESES",
    "TOTAL",
    "OBSERVACIONES"
]
df = df[columnas_oficiales]

# Agregar fila de totales

# Totales con nombres oficiales
totales = {
    'CAPITAL': df['CAPITAL'].fillna(0).sum(),
    'INTERESES': df['INTERESES'].fillna(0).sum(),
    'TOTAL': df['TOTAL'].fillna(0).sum()
}
fila_total = {col: '' for col in df.columns}
fila_total["APELLIDOS Y NOMBRES DEL PENSIONADO"] = "TOTAL"
fila_total["CAPITAL"] = totales["CAPITAL"]
fila_total["INTERESES"] = totales["INTERESES"]
fila_total["TOTAL"] = totales["TOTAL"]
df_con_total = pd.concat([df, pd.DataFrame([fila_total])], ignore_index=True)

# Exportar a Excel
excel_out = os.path.join(OUTPUT_DIR, f"LIQUIDACION_MENSUAL_{date.today().isoformat()}.xlsx")
df_con_total.to_excel(excel_out, index=False)
print(f"Excel generado: {excel_out}")

# Exportar a PDF
pdf_out = os.path.join(OUTPUT_DIR, f"LIQUIDACION_MENSUAL_{date.today().isoformat()}.pdf")
doc = SimpleDocTemplate(pdf_out, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
elements = []
styles = getSampleStyleSheet()

# Encabezado
title = Paragraph("<b>LIQUIDACION OFICIAL DE PENSIONADOS</b>", styles["Title"])
elements.append(title)
elements.append(Spacer(1, 10))

# Tabla
data = [list(df_con_total.columns)] + df_con_total.fillna('').values.tolist()
tbl = Table(data, repeatRows=1)
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
    ("TEXTCOLOR",  (0,0), (-1,0), colors.black),
    ("GRID",       (0,0), (-1,-1), 0.5, colors.black),
    ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
    ("ALIGN",      (0,0), (-1,0), "CENTER"),
    ("ALIGN",      (0,1), (-1,-1), "CENTER"),
    ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
    ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.lightgrey]),
    ("FONTSIZE",   (0,0), (-1,-1), 8),
]))
elements.append(tbl)
elements.append(Spacer(1, 10))

valor_letras = Paragraph(
    f"<b>VALOR EN LETRAS:</b> {totales['total']:,.0f} PESOS M/L.",
    styles["Normal"]
)
elements.append(valor_letras)

doc.build(elements)
print(f"PDF generado: {pdf_out}")
