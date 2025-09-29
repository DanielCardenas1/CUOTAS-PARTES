#!/usr/bin/env python3
"""
Script para probar el período personalizado y verificar las fechas
"""

import sys
sys.path.append('.')

from mostrar_liquidacion_36 import generar_36_cuentas_pensionado_custom
from datetime import date

# Datos de prueba del pensionado (simulando la tupla que viene de la BD)
pensionado_test = (
    26489799,  # identificacion
    'Cerquera Fajardo Angela',  # nombre
    14,  # numero_mesadas
    date(2020, 1, 1),  # fecha_ingreso_nomina
    'HOSPITAL DE OCCIDENTE S.A.',  # empresa
    2302789.5,  # base_calculo_cuota_parte
    0.2259,  # porcentaje_cuota_parte
    '800103913'  # nit_entidad
)

# Probar período personalizado: agosto 2023 hasta agosto 2025
print("Generando cuentas para período AGOSTO 2023 - AGOSTO 2025...")
fecha_corte = date(2025, 8, 31)
fecha_inicio = date(2023, 8, 1)

# Calcular meses disponibles hasta fecha_corte
meses_disponibles = (fecha_corte.year - fecha_inicio.year) * 12 + (fecha_corte.month - fecha_inicio.month) + 1
print(f"Meses disponibles desde {fecha_inicio} hasta {fecha_corte}: {meses_disponibles}")

cuentas = generar_36_cuentas_pensionado_custom(pensionado_test, 2023, 8, fecha_corte, meses_disponibles)

if cuentas:
    print(f"\n✅ Se generaron {len(cuentas)} cuentas")
    print(f"📅 Primera cuenta: {cuentas[0]['fecha_cuenta']}")
    print(f"📅 Última cuenta: {cuentas[-1]['fecha_cuenta']}")
    
    # Verificar que el período sea correcto
    fecha_inicio = cuentas[0]['fecha_cuenta']
    fecha_fin = cuentas[-1]['fecha_cuenta']
    
    # Convertir fechas a formato español
    meses_es = {
        1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
        5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO', 
        9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
    }
    
    mes_inicio = meses_es[fecha_inicio.month]
    año_inicio = fecha_inicio.year
    mes_fin = meses_es[fecha_fin.month]
    año_fin = fecha_fin.year
    
    periodo_texto = f'{mes_inicio} DEL {año_inicio} A {mes_fin} DEL {año_fin}'
    print(f"📄 Período para PDF: CUOTAS PARTES POR COBRAR {periodo_texto}")
    
    # Mostrar algunas cuentas para verificar
    print(f"\n📊 Primeras 3 cuentas:")
    for i in range(min(3, len(cuentas))):
        cuenta = cuentas[i]
        print(f"  {i+1}. {cuenta['fecha_cuenta']} - Capital: ${cuenta['capital']:,.2f} - Intereses: ${cuenta['interes']:,.2f}")
    
    print(f"\n📊 Últimas 3 cuentas:")
    for i in range(max(0, len(cuentas)-3), len(cuentas)):
        cuenta = cuentas[i]
        print(f"  {i+1}. {cuenta['fecha_cuenta']} - Capital: ${cuenta['capital']:,.2f} - Intereses: ${cuenta['interes']:,.2f}")
        
    # Calcular totales
    total_capital = sum(c['capital'] for c in cuentas)
    total_intereses = sum(c['interes'] for c in cuentas)
    total_final = total_capital + total_intereses
    
    print(f"\n💰 TOTALES:")
    print(f"   Capital: ${total_capital:,.2f}")
    print(f"   Intereses: ${total_intereses:,.2f}")
    print(f"   Total: ${total_final:,.2f}")
    
else:
    print("❌ No se generaron cuentas")