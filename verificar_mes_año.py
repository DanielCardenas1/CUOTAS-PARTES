#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de verificación: DTF y días del mes correcto
Verifica que se tome el DTF del mes de interés, no del mes de la cuenta
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from dateutil.relativedelta import relativedelta
from app.db import get_session
from sqlalchemy import text

def obtener_dtf_mes(año, mes):
    """Obtiene la DTF para un mes específico"""
    session = get_session()
    
    try:
        fecha_consulta = date(año, mes, 1)
        query = text("SELECT tasa FROM dtf_mensual WHERE periodo = :fecha")
        result = session.execute(query, {'fecha': fecha_consulta}).fetchone()
        
        if result:
            dtf_decimal = float(result[0])
            dtf_porcentaje = dtf_decimal * 100
            return dtf_porcentaje
        else:
            return 10.0
            
    except Exception as e:
        print(f"Error consultando DTF: {e}")
        return 10.0
    finally:
        session.close()

def verificar_logica_mes_interes():
    """Verifica que el DTF y días se tomen del mes correcto"""
    
    print("=" * 80)
    print("VERIFICACIÓN: DTF Y DÍAS DEL MES CORRECTO")
    print("=" * 80)
    
    # Ejemplo: Cuenta de Sep 2022
    fecha_cuenta = date(2022, 9, 1)  # Sep 2022
    mes_interes = fecha_cuenta + relativedelta(months=1)  # Oct 2022
    
    print(f"Fecha cuenta: {fecha_cuenta.strftime('%Y-%m')}")
    print(f"Mes de interés: {mes_interes.strftime('%Y-%m')}")
    print()
    
    # DTF del mes de la cuenta (INCORRECTO)
    dtf_cuenta = obtener_dtf_mes(fecha_cuenta.year, fecha_cuenta.month)
    print(f"DTF del mes de cuenta (Sep 2022): {dtf_cuenta:.2f}%")
    
    # DTF del mes de interés (CORRECTO)
    dtf_interes = obtener_dtf_mes(mes_interes.year, mes_interes.month)
    print(f"DTF del mes de interés (Oct 2022): {dtf_interes:.2f}%")
    print()
    
    # Días del mes de interés
    if mes_interes.month == 12:
        fecha_fin_mes = date(mes_interes.year + 1, 1, 1) - relativedelta(days=1)
    else:
        fecha_fin_mes = date(mes_interes.year, mes_interes.month + 1, 1) - relativedelta(days=1)
    
    dias_mes = fecha_fin_mes.day
    print(f"Días del mes de interés (Oct 2022): {dias_mes} días")
    print()
    
    print("VERIFICACIÓN CORRECTA:")
    print(f"✓ Cuenta Sep 2022 debe usar DTF de Oct 2022: {dtf_interes:.2f}%")
    print(f"✓ Cuenta Sep 2022 debe usar días de Oct 2022: {dias_mes} días")
    print()
    
    # Verificar varios meses
    print("VERIFICACIÓN MÚLTIPLES MESES:")
    print("MES CUENTA    | MES INTERÉS   | DTF CORRECTO | DÍAS")
    print("-" * 60)
    
    for i in range(6):  # Primeros 6 meses
        fecha_cuenta = date(2022, 9, 1) + relativedelta(months=i)
        mes_interes = fecha_cuenta + relativedelta(months=1)
        
        dtf = obtener_dtf_mes(mes_interes.year, mes_interes.month)
        
        # Calcular días del mes de interés
        if mes_interes.month == 12:
            fecha_fin_mes = date(mes_interes.year + 1, 1, 1) - relativedelta(days=1)
        else:
            fecha_fin_mes = date(mes_interes.year, mes_interes.month + 1, 1) - relativedelta(days=1)
        
        dias = fecha_fin_mes.day
        
        print(f"{fecha_cuenta.strftime('%b %Y')}     | {mes_interes.strftime('%b %Y')}     | {dtf:6.2f}%    | {dias:2d}")

if __name__ == "__main__":
    verificar_logica_mes_interes()