import os
import streamlit as st
                            # --- Vista previa de la liquidación desde la BD ---
from datetime import date
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import subprocess
import pandas as pd
from app.db import engine

# --- Funciones utilitarias para obtener pensionados y entidades ---
def get_pensionados(entidad_id=None):
    if entidad_id:
        rows = q("SELECT pensionado_id as id, nombre, identificacion as ident FROM pensionado WHERE nit_entidad = (SELECT nit FROM entidad WHERE entidad_id=:eid)", {"eid": entidad_id}).fetchall()
    else:
        rows = q("SELECT pensionado_id as id, nombre, identificacion as ident FROM pensionado").fetchall()
    return [dict(row._mapping) for row in rows]

def get_entidades():
    rows = q("SELECT entidad_id as id, nombre, nit FROM entidad").fetchall()
    return [dict(row._mapping) for row in rows]

# Si la función desindexar_base_cuota_parte está en este archivo, no hace falta importar
# Si está en otro archivo, importa así:
# from app.utilidades import desindexar_base_cuota_parte

# --- Utilidad para desindexar base de cálculo según IPC ---
def desindexar_base_cuota_parte(base_actual, anio_actual, anio_objetivo, engine):
    """
    Calcula la base de cálculo de cuota parte para un año objetivo, descontando el IPC año a año desde el año actual.
    base_actual: base de cálculo en anio_actual (ej: 2025)
    anio_actual: año de la base (ej: 2025)
    anio_objetivo: año al que se quiere llevar la base (ej: 2022)
    engine: SQLAlchemy engine para consultar la tabla ipc_anual
    """
    base = float(base_actual)
    if anio_objetivo >= anio_actual:
        return base
    with engine.begin() as conn:
        for anio in range(anio_actual, anio_objetivo, -1):
            res = conn.execute(text("SELECT valor FROM ipc_anual WHERE anio = :anio"), {"anio": anio}).first()
            if res and res[0] is not None:
                ipc = float(res[0])
                base = base / (1 + ipc)
            else:
                # Si no hay IPC para ese año, se asume 0
                pass
    return base

def q(query, params=None):
    with engine.begin() as conn:
        return conn.execute(text(query), params or {})


def mostrar_vista_previa_liquidacion(nit, ident, periodo):
        # Mostrar parámetros usados en la consulta y reproceso para depuración
        st.info(f"Parámetros consulta: nit={nit}, ident={ident}, periodo={periodo}")
        filas = q(
            """
SELECT 
    CONCAT('CCP-', DATE_FORMAT(fecha_pago, '%Y%m'), '-', p.pago_id) AS Consecutivo,
    fecha_pago AS Periodo,
    capital AS Capital,
    interes AS Interés,
    valor AS Total
FROM pago p
WHERE p.pensionado_id = (SELECT pensionado_id FROM pensionado WHERE identificacion=:ident AND nit_entidad=:nit)
    AND fecha_pago = :periodo
ORDER BY fecha_pago
            """,
            {"nit": nit, "ident": ident, "periodo": periodo}
        ).all()
        if filas:
            import pandas as pd
            df = pd.DataFrame(filas, columns=["Consecutivo","Periodo","Capital","Interés","Total"])
            import calendar
            def periodo_rango(fecha):
                inicio = fecha.replace(day=1)
                fin = fecha.replace(day=calendar.monthrange(fecha.year, fecha.month)[1])
                return f"{inicio.strftime('%d/%m/%Y')} al {fin.strftime('%d/%m/%Y')}"
            df["Periodo"] = df["Periodo"].apply(periodo_rango)
            st.subheader(":mag: Vista previa de la liquidación")
            st.dataframe(df, use_container_width=True)
            st.write(f"**Totales**: Capital={df['Capital'].sum():,.2f} | Interés={df['Interés'].sum():,.2f} | Total={df['Total'].sum():,.2f}")
            # --- Botón de reprocesar liquidación ---
            reprocesar = st.button("Reprocesar liquidación (actualizar cálculo)", key=f"reprocesar_{ident}_{periodo}")
            if reprocesar:
                with st.spinner("Reprocesando..."):
                    from sqlalchemy import text
                    # Obtener base_actual real desde pensionado
                    base_row = q("SELECT base_calculo_cuota_parte FROM pensionado WHERE identificacion=:ident AND nit_entidad=:nit", {"ident": ident, "nit": nit}).first()
                    base_actual = float(base_row[0]) if base_row and base_row[0] is not None else 0.0
                    params_repro = {
                        "nit": nit,
                        "ident": ident,
                        "base_actual": base_actual,
                        "periodo": pd.to_datetime(periodo),
                        "anio_base": pd.to_datetime(periodo).year,
                        "ultima_pago": None,
                        "p_modo": "reprocesar"
                    }
                    st.info(f"Parámetros reproceso: {params_repro}")
                    call_repro = text("CALL sp_generar_liq_mensual(:nit, :ident, :base_actual, :periodo, :anio_base, :ultima_pago, :p_modo)")
                    try:
                        with engine.begin() as conn:
                            result_repro = conn.execute(call_repro, params_repro)
                            repro_row = result_repro.fetchone()
                        if repro_row:
                            st.success("Liquidación reprocesada y actualizada correctamente.")
                            # Refrescar la vista previa
                            st.experimental_rerun()
                        else:
                            st.error("No se pudo reprocesar la liquidación.")
                    except Exception as e:
                        st.error(f"Error al reprocesar: {e}")
                # --- Botón de exportación individual PDF/Excel ---
                from datetime import date
                import subprocess
                periodo_inicio = pd.to_datetime(periodo).strftime('%Y-%m-01')
                exportar_ind = st.button("Exportar esta liquidación a PDF/Excel (carpeta)", key=f"exportar_{ident}_{periodo_inicio}")
                if exportar_ind:
                    with st.spinner("Exportando..."):
                        result = subprocess.run([
                            'python',
                            './scripts/exportar_cuenta_cobro_mes.py',
                            '--pensionado', str(ident),
                            '--solo_mes', periodo_inicio
                        ], capture_output=True, text=True)
                        if result.returncode == 0:
                            st.success(f"¡Exportación completada! Busca el PDF y Excel en la carpeta 'reportes_liquidacion/<NIT_ENTIDAD>/'")
                        else:
                            st.error(f"Error al exportar: {result.stderr}")
                st.markdown("---")


# --- SECCIÓN PRINCIPAL DE LIQUIDACIÓN ---
st.title("Generador de Cuentas de Cobro (Cuotas Partes)")
st.markdown("**Liquidar este pensionado**")

# Selección de pensionado
pensionados = get_pensionados()
pensionado = st.selectbox(
    "Pensionado",
    pensionados,
    format_func=lambda x: f"{x['nombre']} - {x['ident']}",
    key="selectbox_pensionado_unico"
)

# Obtener base de cálculo del pensionado
datos_pens = q("SELECT base_calculo_cuota_parte FROM pensionado WHERE pensionado_id=:pid", {"pid": pensionado["id"]}).first() if pensionado else (None,)
base_actual_p = float(datos_pens[0]) if datos_pens and datos_pens[0] is not None else 0.0
# Buscar última fecha de pago real en la tabla pago
ult_pago_row = q("SELECT MAX(fecha_pago) FROM pago WHERE pensionado_id=:pid", {"pid": pensionado["id"]}).first() if pensionado else (None,)
ult_pago_p = ult_pago_row[0] if ult_pago_row and ult_pago_row[0] is not None else None

# Selección de año y mes a liquidar
from datetime import date
import calendar
import locale
from dateutil.relativedelta import relativedelta
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    try:
                            # --- Vista previa de la liquidación desde la BD ---
        locale.setlocale(locale.LC_TIME, 'es_CO.UTF-8')
    except:
        locale.setlocale(locale.LC_TIME, '')
hoy = date.today()
default_year = hoy.year
default_month = hoy.month
# Calcular fecha mínima (36 meses atrás)
min_date = (hoy.replace(day=1) - relativedelta(months=35))
min_year = min_date.year
min_month = min_date.month
max_year = hoy.year
anios = list(range(max_year, min_year - 1, -1))
col_anio, col_mes = st.columns(2)
with col_anio:
    anio_liq = st.selectbox("Año a liquidar", anios, index=0, key="selectbox_anio_unico")
# Limitar meses según el año seleccionado
if anio_liq == min_year:
    meses_validos = list(range(min_month, 13))
elif anio_liq == max_year:
    meses_validos = list(range(1, default_month + 1))
else:
    meses_validos = list(range(1, 13))
meses_es = [calendar.month_name[m].capitalize() for m in meses_validos]
with col_mes:
    mes_liq_num = st.selectbox("Mes a liquidar", meses_validos, index=len(meses_validos)-1, format_func=lambda m: calendar.month_name[m].capitalize(), key="selectbox_mes_unico")
mes_liq = date(anio_liq, mes_liq_num, 1)



# Calcular base ajustada por IPC
anio_base = 2025  # Año fijo de la base de cálculo
if datos_pens and datos_pens[0] is not None:
    base_cuota_parte = desindexar_base_cuota_parte(datos_pens[0], anio_base, anio_liq, engine)
else:
    base_cuota_parte = 0.0

# Mostrar solo una vez los campos principales
col_liq1, col_liq2 = st.columns(2)
with col_liq1:
    st.number_input("Base actual (BASE DE CÁLCULO)", value=base_cuota_parte, disabled=True, key="base_actual_p_unico")
with col_liq2:
    if ult_pago_p:
        st.date_input("Última fecha de pago", value=ult_pago_p, key="ult_pago_p_unico", disabled=True)
    else:
        st.text_input("Última fecha de pago", value="Sin pagos", key="ult_pago_p_unico", disabled=True)

# Advertir si hay cuotas fuera de rango en la liquidación
if pensionado:
    query = "SELECT periodo FROM liquidacion_detalle d JOIN liquidacion l ON l.liquidacion_id = d.liquidacion_id WHERE d.pensionado_id = %s ORDER BY periodo"
    import pandas as pd
    df_periodos = pd.read_sql_query(query, engine, params=(pensionado["id"],))
    if not df_periodos.empty:
        periodos_fuera = df_periodos[df_periodos['periodo'] < min_date]
        if not periodos_fuera.empty:
            st.warning(f"Existen cuotas generadas anteriores a {min_date.strftime('%B %Y')}. Estas están prescritas y no deben cobrarse.")
btn_liq = st.button("Liquidar y guardar", key="btn_liq_unico")
if btn_liq:
    if not pensionado:
        st.error("Selecciona un pensionado.")
    elif mes_liq >= date.today().replace(day=1):
        st.warning("No puedes generar liquidación del mes en curso ni de meses futuros. Solo hasta el mes anterior.")
    else:
        try:
            # Verificar si ya existe un pago para ese pensionado y periodo
            pago_existente = q(
                "SELECT COUNT(*) FROM pago WHERE pensionado_id = :pid AND fecha_pago = :periodo",
                {"pid": pensionado["id"], "periodo": mes_liq}
            ).scalar()
            nit = q("SELECT nit_entidad FROM pensionado WHERE pensionado_id=:pid", {"pid": pensionado["id"]}).scalar()
            if pago_existente and pago_existente > 0:
                st.warning("Ya existe una liquidación/pago para este pensionado y periodo. No se puede duplicar.")
                # Mostrar SIEMPRE la vista previa y el botón de exportar
                mostrar_vista_previa_liquidacion(nit, pensionado["ident"], mes_liq)
            else:
                # Si el periodo a liquidar es igual o anterior a la última fecha de pago, usar modo 'reprocesar'
                modo_liq = "crear"
                ultima_pago_param = ult_pago_p
                if ult_pago_p and mes_liq <= ult_pago_p:
                    modo_liq = "reprocesar"
                    # Buscar la última fecha de pago anterior al periodo a liquidar
                    prev_pago_row = q(
                        "SELECT MAX(fecha_pago) FROM pago WHERE pensionado_id=:pid AND fecha_pago < :periodo",
                        {"pid": pensionado["id"], "periodo": mes_liq}
                    ).first()
                    ultima_pago_param = prev_pago_row[0] if prev_pago_row and prev_pago_row[0] is not None else None
                params_crear = {
                    "nit": nit,
                    "ident": pensionado["ident"],
                    "base_actual": base_cuota_parte,
                    "periodo": mes_liq,
                    "anio_base": mes_liq.year,
                    "ultima_pago": ultima_pago_param,
                    "p_modo": modo_liq
                }
                call_crear = text("CALL sp_generar_liq_mensual(:nit, :ident, :base_actual, :periodo, :anio_base, :ultima_pago, :p_modo)")
                with engine.begin() as conn:
                    result_crear = conn.execute(call_crear, params_crear)
                    try:
                        crear_row = result_crear.fetchone()
                    except Exception as fetch_exc:
                        crear_row = None
                if crear_row:
                    # Manejar valores None para evitar error de formato
                    capital = crear_row[4] if crear_row[4] is not None else 0.0
                    interes = crear_row[5] if crear_row[5] is not None else 0.0
                    total = crear_row[6] if crear_row[6] is not None else 0.0
                    st.success(f"Liquidación creada: Capital={capital:,.2f}, Interés={interes:,.2f}, Total={total:,.2f}")
                    mostrar_vista_previa_liquidacion(nit, pensionado["ident"], mes_liq)
                else:
                    st.error("No se pudo crear la liquidación. Puede que los parámetros sean incorrectos.\n\nParámetros enviados al SP:")
                    st.code(str(params_crear), language="python")
        except Exception as e:
            st.error(f"Error al liquidar: {e}")
else:
    entidades = get_entidades()
    entidad = st.selectbox(
        "Entidad",
        entidades,
        format_func=lambda x: f"{x['nombre']} ({x['nit']})",
        key="selectbox_entidad_main"
    )
    pensionados = get_pensionados(entidad_id=entidad['id']) if entidad else []
    st.write(f"Pensionados encontrados: {len(pensionados)}")
    if len(pensionados) > 0:
        col1, col2 = st.columns(2)
        with col1:
            exportar_todos = st.button("Exportar todas las cuentas de cobro individuales en una carpeta")
        with col2:
            exportar_mes_actual = st.button("Exportar SOLO cuenta del mes en curso para todos")

        import subprocess
        from datetime import date
        errores = []
        if exportar_todos:
            for p in pensionados:
                try:
                    result = subprocess.run([
                        'python',
                        './scripts/exportar_cuenta_cobro_mes.py',
                        '--pensionado', str(p['ident'])
                    ], capture_output=True, text=True)
                    if result.returncode != 0:
                        errores.append(f"{p['nombre']} ({p['ident']}): {result.stderr}")
                except Exception as e:
                    errores.append(f"{p['nombre']} ({p['ident']}): {e}")
            if errores:
                st.error("Algunos pensionados no se exportaron correctamente:\n" + "\n".join(errores))
            else:
                st.success(f"¡Exportación completada! Los archivos están en la carpeta 'reportes_liquidacion'.")
        if exportar_mes_actual:
            mes_actual = date.today().strftime("%Y-%m-01")
            for p in pensionados:
                try:
                    result = subprocess.run([
                        'python',
                        './scripts/exportar_cuenta_cobro_mes.py',
                        '--pensionado', str(p['ident']),
                        '--solo_mes', mes_actual
                    ], capture_output=True, text=True)
                    if result.returncode != 0:
                        errores.append(f"{p['nombre']} ({p['ident']}): {result.stderr}")
                except Exception as e:
                    errores.append(f"{p['nombre']} ({p['ident']}): {e}")
            if errores:
                st.error("Algunos pensionados no se exportaron correctamente:\n" + "\n".join(errores))
            else:
                st.success(f"¡Exportación del mes actual completada! Los archivos están en la carpeta 'reportes_liquidacion'.")
    else:
        st.warning("No hay pensionados asociados a esta entidad.")

col1, col2 = st.columns(2)
with col1:
    hasta = st.date_input("Mes de corte (hasta)", value=date.today().replace(day=1))
with col2:
    meses = st.number_input("Cantidad de meses hacia atrás", min_value=1, max_value=60, value=36, step=1)

col3, col4 = st.columns(2)
with col3:
    base_actual = st.number_input("Base actual (BASE DE CÁLCULO)", min_value=0.0, value=0.0, step=1000.0)
with col4:
    ult_pago = st.date_input("Última fecha de pago", value=(date.today().replace(day=1) - relativedelta(months=2)))

st.caption("Nota: DTF mensual e IPC anual deben estar cargados en las tablas para un cálculo correcto.")

gen_mensuales = st.button("Generar 36 mensuales")
gen_global = st.button("Generar global informativa")

if gen_mensuales:
    if not entidad or not pensionado:
        st.error("Selecciona entidad y pensionado.")
    elif base_actual <= 0:
        st.error("Ingresa una base actual válida.")
    else:
        try:
            # call_sp_generar_36(entidad["nit"], pensionado["ident"], base_actual, hasta, meses, ult_pago)  # Función no implementada
            st.warning("Función 'call_sp_generar_36' no implementada. Debe definirse para habilitar esta funcionalidad.")
            # st.success("¡Listo! Se generaron las liquidaciones mensuales en la base.")
            # st.info("Ahora puedes exportar PDFs con tu módulo pdf.py si lo deseas.")
            # if st.button("Exportar PDF de cuenta de cobro"):
            #     # Ejecuta el script de exportación PDF
            #     result = subprocess.run(["python", "scripts/exportar_cuenta_cobro_mes.py"], capture_output=True, text=True)
            #     if result.returncode == 0:
            #         st.success("PDF generado correctamente. Busca el archivo en la carpeta reportes_liquidacion.")
            #     else:
            #         st.error(f"Error al generar PDF: {result.stderr}")
        except Exception as e:
            st.error(f"Error generando liquidaciones: {e}")

if gen_global:
    if not entidad or not pensionado:
        st.error("Selecciona entidad y pensionado.")
    else:
        desde = (hasta - relativedelta(months=meses-1)).replace(day=1)
        try:
            # filas = call_sp_global(entidad["nit"], pensionado["ident"], desde, (hasta + relativedelta(months=1) - relativedelta(days=1)))  # Función no implementada
            st.warning("Función 'call_sp_global' no implementada. Debe definirse para habilitar esta funcionalidad.")
            # if not filas:
            #     st.warning("No hay liquidaciones en ese rango.")
            # else:
            #     import pandas as pd
            #     df = pd.DataFrame(filas, columns=["Consecutivo","Periodo","Capital","Interés","Total"])
            #     st.dataframe(df, use_container_width=True)
            #     st.write(f"**Totales**: Capital={df['Capital'].sum():,.2f} | Interés={df['Interés'].sum():,.2f} | Total={df['Total'].sum():,.2f}")
            #     st.caption("Recuerda que la glosa de interés DTF post-vencimiento debe ir en el PDF final.")
        except Exception as e:
            st.error(f"Error consultando consolidado: {e}")
