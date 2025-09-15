import pandas as pd
from sqlalchemy import create_engine, text
from datetime import date

# Configuración de conexión
DB_USER = 'root'
DB_PASS = 'BeMaster.1'
DB_HOST = 'localhost'
DB_PORT = '3306'
DB_NAME = 'liquidaciones'

engine = create_engine(f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Obtener mes en curso (primer día del mes)
hoy = date.today()
mes_actual = hoy.replace(day=1)
anio_base = hoy.year


# Obtener todos los nits únicos de los pensionados
nits = pd.read_sql("SELECT DISTINCT nit_entidad FROM pensionado WHERE nit_entidad IS NOT NULL", engine)['nit_entidad']

for nit in nits:
    pensionados = pd.read_sql(f"SELECT identificacion, base_calculo_cuota_parte, ultima_fecha_pago FROM pensionado WHERE nit_entidad = '{nit}'", engine)
    # Filtrar solo identificaciones numéricas
    pensionados = pensionados[pensionados['identificacion'].astype(str).str.match(r'^\\d+$')]
    print(f"NIT: {nit} - Pensionados: {len(pensionados)}")
    for _, p in pensionados.iterrows():
        ident = p['identificacion']
        base_actual = p['base_calculo_cuota_parte'] if not pd.isnull(p['base_calculo_cuota_parte']) else 0
        ultima_pago = p['ultima_fecha_pago'] if not pd.isnull(p['ultima_fecha_pago']) else None
        with engine.begin() as conn:
            try:
                conn.execute(text("CALL sp_generar_liq_mensual(:nit, :ident, :base_actual, :periodo, :anio_base, :ultima_pago)"),
                    {"nit": nit, "ident": ident, "base_actual": base_actual, "periodo": mes_actual, "anio_base": anio_base, "ultima_pago": ultima_pago})
                print(f"  - Liquidado: {ident}")
            except Exception as e:
                print(f"  - ERROR {ident}: {e}")

print("\nLiquidación del mes actual completada para todas las entidades.")
