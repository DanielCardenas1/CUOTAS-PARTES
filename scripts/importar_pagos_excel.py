import pandas as pd
from sqlalchemy import create_engine, text

# Configuración de conexión (ajusta usuario y contraseña si es necesario)
engine = create_engine("mysql+pymysql://liq_user:liq_pass@127.0.0.1:3306/liquidaciones?charset=utf8mb4")

EXCEL_PATH = r"C:\Users\danie\OneDrive\Documentos\liquidaciones_project\PRUEBAS BASE DE DATOS.xlsx"

# Leer hoja PAGOS
df = pd.read_excel(EXCEL_PATH, sheet_name='PAGOS')

cols_fijas = ['Nombre', 'Identificacion', 'Empresa', 'NIT. ENTIDAD']
cols_meses = [col for col in df.columns if col not in cols_fijas]

with engine.begin() as conn:
    for _, row in df.iterrows():
        nombre = str(row['Nombre']) if not pd.isna(row['Nombre']) else None
        identificacion = str(row['Identificacion']) if not pd.isna(row['Identificacion']) else None
        empresa = str(row['Empresa']) if not pd.isna(row['Empresa']) else None
        nit_entidad = str(row['NIT. ENTIDAD']) if not pd.isna(row['NIT. ENTIDAD']) else None
        for col in cols_meses:
            valor = row[col]
            if pd.isna(valor) or valor == 0:
                continue
            # Intentar parsear la fecha del encabezado
            try:
                fecha_pago = pd.to_datetime(col, format='%B %Y', errors='coerce')
                if pd.isna(fecha_pago):
                    fecha_pago = pd.to_datetime(col.title(), format='%B %Y', errors='coerce')
                if pd.isna(fecha_pago):
                    continue
                fecha_pago = fecha_pago.replace(day=1)
            except Exception:
                continue
            # Insertar pago
            conn.execute(
                text("""
                INSERT INTO pago (nombre, identificacion, empresa, nit_entidad, fecha_pago, valor, observaciones)
                VALUES (:nombre, :identificacion, :empresa, :nit_entidad, :fecha_pago, :valor, :obs)
                ON DUPLICATE KEY UPDATE valor=VALUES(valor), observaciones=VALUES(observaciones)
                """),
                {
                    "nombre": nombre,
                    "identificacion": identificacion,
                    "empresa": empresa,
                    "nit_entidad": nit_entidad,
                    "fecha_pago": fecha_pago.date(),
                    "valor": valor,
                    "obs": 'Pago real importado de Excel'
                }
            )
print("Pagos reales importados desde Excel.")
