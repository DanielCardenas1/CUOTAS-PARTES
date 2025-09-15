# Objetivo (Copilot):
# - Leer tu Excel .xlsx
# - Mapear columnas por nombre y cargar a BD:
#   * pensionado (Identificacion, Nombre, Estado cartera, etc.)
#   * DTF mensual (Tasa de Depósitos a Término Fijo (DTF) a 90 días, mensual)
#   * IPC anual (Variación Anual del IPC)

import pandas as pd
from dateutil.relativedelta import relativedelta
from app.models import Pensionado, DtfMensual, IpcAnual, Pago
from sqlalchemy import insert
from datetime import datetime

EXCEL_PATH = r"C:\Users\danie\OneDrive\Documentos\liquidaciones_project\PRUEBAS BASE DE DATOS.xlsx"
HOJA_BASE = "a"

def cargar_excel_a_bd(session):
    # Solo actualizar campos res_no, reliqui y consulta de pensionado usando Identificacion
    df = pd.read_excel(EXCEL_PATH, sheet_name='a')
    actualizados = 0
    for _, row in df.iterrows():
        identificacion = None
        if not pd.isna(row.get('Identificacion')):
            try:
                identificacion = str(int(row['Identificacion']))
            except Exception:
                identificacion = str(row['Identificacion'])
        if not identificacion:
            continue
        # Leer exactamente los nombres de columna del Excel
        res_no = row['Res. No'] if 'Res. No' in row and not pd.isna(row['Res. No']) else None
        reliqui = row['Reliqui'] if 'Reliqui' in row and not pd.isna(row['Reliqui']) else None
        consulta = row['Consulta'] if 'Consulta' in row and not pd.isna(row['Consulta']) else None
        pensionado = session.query(Pensionado).filter_by(identificacion=identificacion).first()
        if pensionado:
            pensionado.res_no = str(res_no) if res_no is not None else None
            pensionado.reliqui = str(reliqui) if reliqui is not None else None
            pensionado.consulta = str(consulta) if consulta is not None else None
            actualizados += 1
    session.commit()
    print(f"Actualizados {actualizados} pensionados con res_no, reliqui y consulta.")
    # Importar pagos mensuales desde hoja 'PAGOS'
    try:
        df_pagos = pd.read_excel(EXCEL_PATH, sheet_name='PAGOS')
        # Detectar columnas de meses (todas las columnas excepto las primeras conocidas)
        known_cols = {'Nombre', 'Identificacion', 'Empresa', 'NIT. ENTIDAD', 'Observaciones'}
        meses_cols = [col for col in df_pagos.columns if col not in known_cols]
        for _, row in df_pagos.iterrows():
            identificacion = str(int(row['Identificacion'])) if not pd.isna(row['Identificacion']) else None
            pensionado = session.query(Pensionado).filter_by(identificacion=identificacion).first()
            if not pensionado:
                continue
            for col in meses_cols:
                valor = row.get(col)
                if pd.notna(valor) and valor != 0:
                    try:
                        fecha_pago = pd.to_datetime(col, format='%B %Y', errors='coerce')
                        if pd.isna(fecha_pago):
                            fecha_pago = pd.to_datetime(col.title(), format='%B %Y', errors='coerce')
                        if pd.isna(fecha_pago):
                            continue
                        fecha_pago = fecha_pago.replace(day=1)
                    except Exception:
                        continue
                    pago = session.query(Pago).filter_by(pensionado_id=pensionado.pensionado_id, fecha_pago=fecha_pago).first()
                    if not pago:
                        pago = Pago(
                            pensionado_id=pensionado.pensionado_id,
                            fecha_pago=fecha_pago,
                            valor=valor,
                            observaciones=row.get('Observaciones')
                        )
                        session.add(pago)
                    else:
                        pago.valor = valor
                        pago.observaciones = row.get('Observaciones')
        session.commit()
        print("Pagos mensuales importados/actualizados.")
    except Exception as e:
        print(f"No se pudo importar hoja 'PAGOS': {e}")

    # Importar DTF mensual desde hoja 'DTF'
    try:
        df_dtf = pd.read_excel(EXCEL_PATH, sheet_name='DTF')
        for _, row in df_dtf.iterrows():
            periodo = row.get('Fecha')
            tasa = row.get('Tasa de Depósitos a Término Fijo (DTF) a 90 días, mensual')
            if pd.notna(periodo) and pd.notna(tasa):
                if isinstance(periodo, str):
                    try:
                        periodo = datetime.strptime(periodo, "%d/%m/%Y").date()
                    except ValueError:
                        try:
                            periodo = datetime.strptime(periodo, "%Y-%m-%d").date()
                        except ValueError:
                            continue
                elif isinstance(periodo, pd.Timestamp):
                    periodo = periodo.date()
                try:
                    tasa = float(str(tasa).replace(',', '.'))
                    if tasa > 1:
                        tasa = tasa / 100
                except Exception:
                    continue
                dtf = session.query(DtfMensual).filter_by(periodo=periodo).first()
                if not dtf:
                    dtf = DtfMensual(periodo=periodo, tasa=tasa)
                    session.add(dtf)
                else:
                    dtf.tasa = tasa
        session.commit()
        print("DTF mensual importado/actualizado.")
    except Exception as e:
        print(f"No se pudo importar hoja 'DTF': {e}")

    # Importar IPC anual desde hoja 'IPC'
    try:
        df_ipc = pd.read_excel(EXCEL_PATH, sheet_name='IPC')
        for _, row in df_ipc.iterrows():
            anio = row.get('Año')
            ipc = row.get('Variación Anual del IPC')
            if pd.notna(anio) and pd.notna(ipc):
                try:
                    ipc = float(str(ipc).replace(',', '.'))
                    if ipc > 1:
                        ipc = ipc / 100
                except Exception:
                    continue
                ipc_row = session.query(IpcAnual).filter_by(anio=int(anio)).first()
                if not ipc_row:
                    ipc_row = IpcAnual(anio=int(anio), valor=ipc)
                    session.add(ipc_row)
                else:
                    ipc_row.valor = ipc
        session.commit()
        print("IPC anual importado/actualizado.")
    except Exception as e:
        print(f"No se pudo importar hoja 'IPC': {e}")

if __name__ == "__main__":
    print("Este script está diseñado para ser usado desde la CLI principal con una sesión de BD.")
    print("Usa cargar_excel_a_bd(session) desde app/cli.py para importar los datos.")
