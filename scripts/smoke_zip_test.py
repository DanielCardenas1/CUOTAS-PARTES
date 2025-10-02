import os
import sys
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import get_session
from sqlalchemy import text

# Use helpers from the app for totals
try:
    from mostrar_liquidacion_36 import generar_36_cuentas_pensionado
except Exception:
    generar_36_cuentas_pensionado = None

from app_ui import generar_zip_individual_plantilla


def pick_entity_with_pensionados(session):
    row = session.execute(text(
        """
        SELECT e.nit, e.nombre
        FROM entidad e
        WHERE EXISTS (SELECT 1 FROM pensionado p WHERE p.nit_entidad = e.nit)
        LIMIT 1
        """
    )).fetchone()
    return (str(row[0]), row[1]) if row else (None, None)


def get_some_pensionados(session, nit, limit=3):
    # Same order as generar_pdf_oficial expects: id, nombre, mesadas, ingreso_nomina, empresa, base, porcentaje, nit
    rows = session.execute(text(
        """
        SELECT identificacion, nombre, numero_mesadas, fecha_ingreso_nomina, empresa,
               base_calculo_cuota_parte, porcentaje_cuota_parte, nit_entidad
        FROM pensionado
        WHERE nit_entidad = :nit
        ORDER BY nombre
        LIMIT :limit
        """
    ), {"nit": nit, "limit": limit}).fetchall()
    return rows


def build_todas_las_cuentas(rows):
    todas = []
    for r in rows:
        total_capital = 0.0
        total_intereses = 0.0
        if generar_36_cuentas_pensionado:
            try:
                cuentas = generar_36_cuentas_pensionado(r, date(2025, 8, 31))
                total_capital = float(sum(c.get('capital', 0.0) for c in cuentas))
                total_intereses = float(sum(c.get('interes', 0.0) for c in cuentas))
            except Exception:
                pass
        todas.append({
            'pensionado': {
                'cedula': str(r[0]),
                'nombre': r[1],
                'porcentaje_cuota': float(r[6] or 0.0),
            },
            'total_capital': total_capital,
            'total_intereses': total_intereses,
            'total_pensionado': total_capital + total_intereses,
            'cuentas': []  # not needed for consolidated table since totals provided
        })
    return todas


def main():
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reportes_liquidacion')
    os.makedirs(out_dir, exist_ok=True)
    out_zip = os.path.join(out_dir, 'SMOKE_TEST.zip')

    with get_session() as s:
        nit, nombre = pick_entity_with_pensionados(s)
        if not nit:
            print('No se encontró una entidad con pensionados activos.')
            return 2
        print(f'Entidad encontrada: {nombre} ({nit})')
        pens = get_some_pensionados(s, nit, limit=2)
        print(f'Se tomarán {len(pens)} pensionados para la prueba rápida...')
        todas = build_todas_las_cuentas(pens)

    # Generar ZIP en memoria
    zip_bytes = generar_zip_individual_plantilla(nit, nombre, todas)
    with open(out_zip, 'wb') as f:
        f.write(zip_bytes)
    print(f'ZIP de prueba generado: {out_zip}  Tamaño: {len(zip_bytes):,} bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
