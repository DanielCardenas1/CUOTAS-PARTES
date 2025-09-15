import pymysql
from datetime import date

# Configura tus datos de conexión
conn = pymysql.connect(
    host='localhost',
    user='TU_USUARIO',
    password='TU_PASSWORD',
    db='TU_BASE',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

def obtener_ultima_fecha_pago(cursor, pensionado_id):
    cursor.execute("SELECT MAX(fecha_pago) as ultima_fecha FROM pago WHERE pensionado_id = %s", (pensionado_id,))
    row = cursor.fetchone()
    return row['ultima_fecha'] if row and row['ultima_fecha'] else '2000-01-01'

try:
    with conn.cursor() as cursor:
        # Obtener todos los pensionados
        cursor.execute("SELECT p.pensionado_id, p.identificacion, p.nit_entidad, p.base_actual, p.anio_base FROM pensionado p")
        pensionados = cursor.fetchall()
        hoy = date.today()
        for p in pensionados:
            ultima_fecha_pago = obtener_ultima_fecha_pago(cursor, p['pensionado_id'])
            # Llamar al procedimiento para los últimos 36 meses
            cursor.callproc('sp_generar_liq_36', [
                p['nit_entidad'],
                p['identificacion'],
                p['base_actual'],
                p['anio_base'],
                ultima_fecha_pago,
                hoy.replace(day=1) # p_periodo_hasta: primer día del mes actual
            ])
            while cursor.nextset():
                pass
        print(f"Liquidaciones generadas para {len(pensionados)} pensionados.")
    conn.commit()
finally:
    conn.close()
