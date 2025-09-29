from mostrar_liquidacion_36 import generar_36_cuentas_pensionado
from app.db import get_session
from sqlalchemy import text
from datetime import date

# Fetch pensionado data from DB to get base values
ident = '26489799'
s = get_session()
try:
    p = s.execute(text('SELECT identificacion, nombre, numero_mesadas, fecha_ingreso_nomina, empresa, base_calculo_cuota_parte, porcentaje_cuota_parte, nit_entidad FROM pensionado WHERE identificacion = :id'), {'id': ident}).fetchone()
    if not p:
        print('Pensionado no encontrado')
        raise SystemExit(1)
    pensionado = tuple(p)
finally:
    s.close()

fecha_corte = date(2025,8,31)
cuentas = generar_36_cuentas_pensionado(pensionado, fecha_corte)

print(f"Cuentas generadas: {len(cuentas)}\n")
print('Mes | Capital | Interes | Total')
for c in cuentas:
    print(f"{c['fecha_cuenta'].strftime('%Y-%m')} | {c['capital']:,.2f} | {c['interes']:,.2f} | {c['capital']+c['interes']:,.2f}")

cap_total = sum(c['capital'] for c in cuentas)
int_total = sum(c['interes'] for c in cuentas)
print('\nTotales calculados:')
print(f'Capital: {cap_total:,.2f}')
print(f'Intereses: {int_total:,.2f}')
print(f'Total: {cap_total+int_total:,.2f}')
