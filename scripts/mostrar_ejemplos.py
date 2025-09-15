from app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    print('Primeros 5 pensionados:')
    for row in conn.execute(text('SELECT pensionado_id, nombre, identificacion, empresa FROM pensionado LIMIT 5')):
        print(row)
    print('\nPrimeros 5 pagos:')
    for row in conn.execute(text('SELECT pago_id, pensionado_id, fecha_pago, valor FROM pago LIMIT 5')):
        print(row)
