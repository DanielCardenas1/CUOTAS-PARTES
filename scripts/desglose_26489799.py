from app.db import get_session
from sqlalchemy import text
import csv

ID = '26489799'

s = get_session()
rows = []
try:
    q = text('''
        SELECT consecutivo, periodo_inicio, periodo_fin, total_capital, total_intereses, total_liquidacion, archivo_pdf, fecha_creacion
        FROM cuenta_cobro
        WHERE pensionado_identificacion = :id
        ORDER BY fecha_creacion ASC, consecutivo ASC
    ''')
    res = s.execute(q, {'id': ID}).fetchall()
    for r in res:
        rows.append({
            'consecutivo': r[0],
            'periodo_inicio': r[1].isoformat() if r[1] else '',
            'periodo_fin': r[2].isoformat() if r[2] else '',
            'total_capital': float(r[3] or 0),
            'total_intereses': float(r[4] or 0),
            'total_liquidacion': float(r[5] or 0),
            'archivo_pdf': r[6] or '',
            'fecha_creacion': r[7].isoformat() if r[7] else ''
        })
finally:
    s.close()

# Print a simple table
if not rows:
    print('No hay registros de cuenta_cobro para', ID)
else:
    print(f"Registros encontrados: {len(rows)}\n")
    total = 0.0
    for r in rows:
        print(f"Nro {r['consecutivo']:>3} | {r['periodo_inicio']} -> {r['periodo_fin']} | Capital: ${r['total_capital']:,.2f} | Intereses: ${r['total_intereses']:,.2f} | Total: ${r['total_liquidacion']:,.2f}")
        total += r['total_liquidacion']
    print('\nAcumulado (suma total_liquidacion): ${:,.2f}'.format(total))

    # Write CSV
    csv_file = 'CUENTA_COBRO_DETALLE_26489799.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print('\nCSV creado:', csv_file)
