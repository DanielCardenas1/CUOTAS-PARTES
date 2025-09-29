from app.db import get_session
from sqlalchemy import text

s = get_session()
try:
    row = s.execute(
        text('SELECT pensionado_identificacion, SUM(total_liquidacion) as acumulado FROM cuenta_cobro WHERE pensionado_identificacion = :id GROUP BY pensionado_identificacion'),
        {'id': '26489799'}
    ).fetchone()
    if row:
        print(row[0], float(row[1]))
    else:
        print('No hay registros en cuenta_cobro para 26489799')
finally:
    s.close()
