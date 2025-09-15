import pymysql

# Configura tus datos de conexión
conn = pymysql.connect(
    host='localhost',
    user='TU_USUARIO',
    password='TU_PASSWORD',
    db='TU_BASE',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

try:
    with conn.cursor() as cursor:
        # Llama al procedimiento almacenado con tus parámetros reales
        cursor.callproc('sp_generar_liq_mensual', [
            'NIT_ENTIDAD',         # Reemplaza por el NIT real
            'IDENTIFICACION',      # Reemplaza por la identificación real
            1000000.00,           # p_base_actual
            '2025-09-01',         # p_periodo (YYYY-MM-DD)
            2025,                 # p_anio_base
            '2025-08-01'          # p_ultima_fecha_pago (YYYY-MM-DD)
        ])
        # Consumir todos los resultados para evitar error 2014
        while cursor.nextset():
            pass
    conn.commit()
    print('Procedimiento ejecutado correctamente.')
finally:
    conn.close()
