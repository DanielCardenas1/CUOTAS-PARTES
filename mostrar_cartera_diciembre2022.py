"""
Script para mostrar la liquidación de cartera de cuenta de cobro de un pensionado,
con cálculo de capital, intereses acumulados y totales para un periodo específico.
"""

import sys
from datetime import date
from dateutil.relativedelta import relativedelta
from app.db import get_session
from sqlalchemy import text

def obtener_porcentaje_cuota_parte(identificacion):
    session = get_session()
    try:
        query = text("SELECT porcentaje_cuota_parte FROM pensionado WHERE identificacion = :id LIMIT 1")
        result = session.execute(query, {'id': identificacion}).fetchone()
        return float(result[0]) if result and result[0] else 0.2259
    finally:
        session.close()

def ajustar_base_por_ipc(base_2025, año_cuenta):
    if año_cuenta >= 2025:
        return base_2025
    session = get_session()
    try:
        ipc_acumulado = 1.0
        for año in range(año_cuenta + 1, 2025 + 1):
            query = text("SELECT valor FROM ipc_anual WHERE anio = :año")
            result = session.execute(query, {'año': año}).fetchone()
            ipc_acumulado *= 1.0 + (float(result[0]) if result else 0.03)
        return base_2025 / ipc_acumulado
    finally:
        session.close()

def obtener_dtf_mes(año, mes):
    session = get_session()
    try:
        fecha_consulta = date(año, mes, 1)
        query = text("SELECT tasa FROM dtf_mensual WHERE periodo = :fecha")
        result = session.execute(query, {'fecha': fecha_consulta}).fetchone()
        return float(result[0]) * 100 if result else 10.0
    except Exception:
        return 10.0
    finally:
        session.close()

def tiene_prima_mes(numero_mesadas, mes):
    mesadas = int(numero_mesadas)
    if mesadas == 12:
        return False
    elif mesadas == 13:
        return mes == 12
    elif mesadas == 14:
        return mes in [6, 12]
    return False

def calcular_interes_mensual_unico(capital_fijo, fecha_cuenta, fecha_corte):
    if fecha_cuenta >= fecha_corte:
        return 0.0
    if fecha_cuenta > fecha_corte:
        return 0.0
    dtf_ea = obtener_dtf_mes(fecha_cuenta.year, fecha_cuenta.month) / 100
    if fecha_cuenta.month == 12:
        fecha_fin_mes = date(fecha_cuenta.year + 1, 1, 1) - relativedelta(days=1)
    else:
        fecha_fin_mes = date(fecha_cuenta.year, fecha_cuenta.month + 1, 1) - relativedelta(days=1)
    dias_mes = fecha_fin_mes.day
    if dias_mes > 0:
        factor_interes = ((1 + dtf_ea) ** (dias_mes / 365)) - 1
        return round(capital_fijo * factor_interes, 2)
    return 0.0

def calcular_cartera_mes(pensionado, año, mes, año_fin, mes_fin):
    porcentaje_cuota_parte = obtener_porcentaje_cuota_parte(pensionado[0])
    base_calculo = float(pensionado[5])
    base_ajustada_ipc = ajustar_base_por_ipc(base_calculo, año)
    capital_fijo_mes = base_ajustada_ipc * porcentaje_cuota_parte
    fecha_inicio = date(año, mes, 1)
    fecha_fin = date(año_fin, mes_fin, 1)
    # Si la fecha final es menor que la inicial, usar la inicial
    if fecha_fin < fecha_inicio:
        fecha_fin = fecha_inicio
    num_meses = (fecha_fin.year - año) * 12 + (fecha_fin.month - mes) + 1
    intereses_acumulados = 0.0
    for j in range(num_meses):
        fecha_interes = fecha_inicio + relativedelta(months=j)
        interes_mensual = calcular_interes_mensual_unico(capital_fijo_mes, fecha_interes, fecha_fin)
        intereses_acumulados += interes_mensual
    cartera_mes = capital_fijo_mes + intereses_acumulados
    return capital_fijo_mes, intereses_acumulados, cartera_mes

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Mostrar cartera de cuenta de cobro para un periodo personalizado')
    parser.add_argument('--año-inicio', type=int, default=2022, help='Año inicial')
    parser.add_argument('--mes-inicio', type=int, default=9, help='Mes inicial')
    parser.add_argument('--año-fin', type=int, default=date.today().year, help='Año final')
    parser.add_argument('--mes-fin', type=int, default=date.today().month, help='Mes final')
    args = parser.parse_args()

    session = get_session()
    try:
        query = text('''SELECT identificacion, nombre, numero_mesadas, fecha_ingreso_nomina, empresa, base_calculo_cuota_parte FROM pensionado WHERE identificacion = '26489799' LIMIT 1''')
        result = session.execute(query).fetchone()
    finally:
        session.close()
    if not result:
        print("No se encontró el pensionado 26489799")
        return
    pensionado = list(result)
    capital_mes, intereses_mes, cartera_mes = calcular_cartera_mes(
        pensionado, args.año_inicio, args.mes_inicio, args.año_fin, args.mes_fin)
    print(f"CARTERA DE CUENTA DE COBRO {args.mes_inicio:02d}/{args.año_inicio} a {args.mes_fin:02d}/{args.año_fin}:")
    print(f"- Capital inicial: ${capital_mes:,.2f}")
    print(f"- Intereses acumulados: ${intereses_mes:,.2f}")
    print(f"- Total cartera: ${cartera_mes:,.2f}")

if __name__ == "__main__":
    main()
