def obtener_ipc_desde_bd(año_inicio, año_fin):
    """Obtiene el IPC acumulado desde BD"""
    session = get_session()
    try:
        query = text("SELECT anio, valor FROM ipc_anual WHERE anio >= :inicio AND anio <= :fin ORDER BY anio")
        result = session.execute(query, {'inicio': año_inicio, 'fin': año_fin}).fetchall()
        ipc_acumulado = 1.0
        for row in result:
            ipc_valor = float(row[1])
            ipc_acumulado *= ipc_valor
        return ipc_acumulado
    except Exception as e:
        print(f"Error consultando IPC: {e}")
        return 1.0
    finally:
        session.close()
from app.db import get_session
from sqlalchemy import text
from datetime import date
from dateutil.relativedelta import relativedelta
def tiene_prima_mes(numero_mesadas, mes):
    """Determina si un pensionado tiene prima en un mes específico"""
    mesadas = int(numero_mesadas)
    if mesadas == 12:
        return False  # Sin prima
    elif mesadas == 13:
        return mes == 12  # Solo diciembre
    elif mesadas == 14:
        return mes in [6, 12]  # Junio y diciembre
    else:
        return False
def calcular_cartera_mes(pensionado, año, mes, fecha_fin):
    """
    Calcula la cartera de la cuenta de cobro de un mes específico:
    capital de ese mes + intereses acumulados desde ese mes hasta fecha_fin.
    """
    # Calcular porcentaje de cuota parte
    session = get_session()
    try:
        query = text("SELECT porcentaje_cuota_parte FROM pensionado WHERE identificacion = :id LIMIT 1")
        result = session.execute(query, {'id': pensionado[0]}).fetchone()
        porcentaje_cuota_parte = float(result[0]) if result and result[0] else 0.2259
    finally:
        session.close()
    base_calculo = float(pensionado[5])
    numero_mesadas = pensionado[2]

    # Ajustar base de cálculo de 2025 al año de la cuenta de cobro usando IPC
    base_ajustada_ipc = ajustar_base_por_ipc(base_calculo, año)
    capital_fijo_mes = base_ajustada_ipc * porcentaje_cuota_parte
    # Si el mes tiene prima, duplicar el capital
    if tiene_prima_mes(numero_mesadas, mes):
        capital_fijo_mes = capital_fijo_mes * 2

    fecha_inicio = date(año, mes, 1)
    fecha_corte = fecha_fin
    num_meses = (fecha_fin.year - año) * 12 + (fecha_fin.month - mes) + 1

    intereses_acumulados = 0.0
    for j in range(num_meses):
        fecha_interes = fecha_inicio + relativedelta(months=j)
        año_int = fecha_interes.year
        mes_int = fecha_interes.month
        fecha_cuenta_int = date(año_int, mes_int, 1)
        interes_mensual = calcular_interes_mensual_unico(capital_fijo_mes, fecha_cuenta_int, fecha_corte)
        intereses_acumulados += interes_mensual

    cartera_mes = capital_fijo_mes + intereses_acumulados
    return capital_fijo_mes, intereses_acumulados, cartera_mes
def calcular_consolidado_global(pensionado, fecha_inicio, fecha_fin):
    """
    Calcula el consolidado global de cartera:
    Para cada mes, suma capital + intereses acumulados desde ese mes hasta fecha_fin.
    Luego suma todas esas carteras mensuales.
    """
    cuentas = []
    fecha_corte = fecha_fin
    num_meses = (fecha_fin.year - fecha_inicio.year) * 12 + (fecha_fin.month - fecha_inicio.month) + 1
    # Calcular porcentaje de cuota parte
    session = get_session()
    try:
        query = text("SELECT porcentaje_cuota_parte FROM pensionado WHERE identificacion = :id LIMIT 1")
        result = session.execute(query, {'id': pensionado[0]}).fetchone()
        porcentaje_cuota_parte = float(result[0]) if result and result[0] else 0.2259
    finally:
        session.close()
    base_calculo = float(pensionado[5])
    numero_mesadas = pensionado[2]

    # Ajustar base de cálculo de 2025 al año de la cuenta de cobro usando IPC
    año_cuenta_cobro = fecha_inicio.year
    base_ajustada_ipc = ajustar_base_por_ipc(base_calculo, año_cuenta_cobro)
    capital_fijo_tabla = base_ajustada_ipc * porcentaje_cuota_parte



def ajustar_base_por_ipc(base_2025, año_cuenta):
    """Ajusta la base de cálculo de 2025 al año de la cuenta usando datos reales de BD"""
    if año_cuenta >= 2025:
        return base_2025
    
    # IPC acumulado desde el año de la cuenta hasta 2025
    ipc_acumulado = obtener_ipc_desde_bd(año_cuenta, 2025)
    
    # Base ajustada = Base 2025 / IPC acumulado
    base_ajustada = base_2025 / ipc_acumulado
    
    return base_ajustada

def obtener_dtf_mes(año, mes):
    """Obtiene la DTF para un mes específico (con integración BD)"""
    # Consultar primero en la base de datos
    session = get_session()
    
    try:
        # Construir fecha del primer día del mes
        fecha_consulta = date(año, mes, 1)
        
        # Consultar DTF desde la base de datos
        query = text("SELECT tasa FROM dtf_mensual WHERE periodo = :fecha")
        result = session.execute(query, {'fecha': fecha_consulta}).fetchone()
        
        try:
            # Construir fecha del primer día del mes
            fecha_consulta = date(año, mes, 1)

            # Consultar DTF desde la base de datos
            query = text("SELECT tasa FROM dtf_mensual WHERE periodo = :fecha")
            result = session.execute(query, {'fecha': fecha_consulta}).fetchone()

            if result:
                # La tasa está en decimal, convertir a porcentaje
                dtf_decimal = float(result[0])
                dtf_porcentaje = dtf_decimal * 100
                return dtf_porcentaje
            else:
                print(f"ADVERTENCIA: No se encontró DTF para {año}-{mes:02d}. Por favor ingresa el valor manualmente.")
                dtf_manual = float(input(f"DTF para {año}-{mes:02d} (%): "))
                return dtf_manual

        # ...existing code...
def calcular_interes_mensual_unico(capital_fijo, fecha_cuenta, fecha_corte):
    """Calcula interés usando DTF y días del MISMO mes de la cuenta (como en Excel)"""
    if fecha_cuenta >= fecha_corte:
        return 0.0
    # El interés se calcula usando DTF y días del MISMO mes de la cuenta
    fecha_interes = fecha_cuenta
    if fecha_interes > fecha_corte:
        return 0.0
    dtf_ea = obtener_dtf_mes(fecha_interes.year, fecha_interes.month) / 100
    # Calcular días del mismo mes de la cuenta
    if fecha_interes.month == 12:
        fecha_fin_mes = date(fecha_interes.year + 1, 1, 1) - relativedelta(days=1)
    else:
        fecha_fin_mes = date(fecha_interes.year, fecha_interes.month + 1, 1) - relativedelta(days=1)
    dias_mes = fecha_fin_mes.day
    if dias_mes > 0:
        factor_interes = ((1 + dtf_ea) ** (dias_mes / 365)) - 1
        interes_mes = capital_fijo * factor_interes
        return round(interes_mes, 2)
    return 0.0
        fecha_fin_mes = date(fecha_interes.year, fecha_interes.month + 1, 1) - relativedelta(days=1)
    
    # Días del mes completo (generalmente 30 o 31)
    dias_mes = fecha_fin_mes.day
    
    # Fórmula Excel: Capital * (((1 + DTF)^(días/365)) - 1)
    if dias_mes > 0:
        factor_interes = ((1 + dtf_ea) ** (dias_mes / 365)) - 1
        interes_mes = capital_fijo * factor_interes
        return round(interes_mes, 2)
    
    return 0.0

def generar_36_cuentas_pensionado(pensionado, fecha_corte):
    """Genera las 36 cuentas independientes para un pensionado - Sep 2022 a Ago 2025"""
    fecha_inicial = date(2022, 9, 1)  # Sep 2022
    return _generar_cuentas_periodo(pensionado, fecha_inicial, fecha_corte, 36)

def generar_36_cuentas_pensionado_oct(pensionado, fecha_corte):
    """Genera las 36 cuentas independientes para un pensionado - Oct 2022 a Ago 2025"""
    fecha_inicial = date(2022, 10, 1)  # Oct 2022
    return _generar_cuentas_periodo(pensionado, fecha_inicial, fecha_corte, 36)

def generar_36_cuentas_pensionado_custom(pensionado, año_inicio, mes_inicio, fecha_corte, num_meses=36):
    """Genera cuentas para un pensionado desde cualquier mes/año especificado hasta la fecha de corte"""
    fecha_inicial = date(año_inicio, mes_inicio, 1)
    return _generar_cuentas_periodo(pensionado, fecha_inicial, fecha_corte, num_meses)

def _generar_cuentas_periodo(pensionado, fecha_inicial, fecha_corte, num_meses):
    """Función auxiliar para generar cuentas en un período específico"""
    cuentas = []
    
    # Calcular porcentaje de cuota parte (usando columna 12 según datos BD)
    session = get_session()
    try:
        query = text("SELECT porcentaje_cuota_parte FROM pensionado WHERE identificacion = :id LIMIT 1")
        result = session.execute(query, {'id': pensionado[0]}).fetchone()
        porcentaje_cuota_parte = float(result[0]) if result and result[0] else 0.2259  # Default 22.59%
    finally:
        session.close()
    
    # Base de cálculo desde BD
    base_calculo = float(pensionado[5])  # base_calculo_cuota_parte
    numero_mesadas = pensionado[2]  # numero_mesadas
    
    # Calcular el año de la cuenta de cobro (primer mes del período)
    año_cuenta_cobro = fecha_inicial.year
    # Ajustar base de cálculo de 2025 al año de la cuenta de cobro usando IPC
    base_ajustada_ipc = ajustar_base_por_ipc(base_calculo, año_cuenta_cobro)
    ipc_factor = base_calculo / base_ajustada_ipc if base_ajustada_ipc != 0 else 1.0
    # CAPITAL FIJO para toda la tabla de intereses: base ajustada × % cuota parte
    capital_fijo_tabla = base_ajustada_ipc * porcentaje_cuota_parte

    for i in range(num_meses):  # Número de meses especificado
        fecha_mes = fecha_inicial + relativedelta(months=i)
        año = fecha_mes.year
        mes = fecha_mes.month

        # Prima solo afecta el capital para la cuenta de cobro, NO para intereses
        prima = 0
        capital_final = capital_fijo_tabla
        if tiene_prima_mes(numero_mesadas, mes):
            prima = capital_fijo_tabla  # Prima equivalente
            capital_final = capital_fijo_tabla + prima

        # INTERÉS SIEMPRE sobre el capital base de la cuenta de cobro (ajustado por IPC y porcentaje), nunca duplicado por prima
        fecha_cuenta = date(año, mes, 1)
        interes_mensual = calcular_interes_mensual_unico(capital_fijo_tabla, fecha_cuenta, fecha_corte)

        # Obtener días y DTF del mismo mes de la cuenta para mostrar en reporte
        mes_interes = fecha_cuenta  # Mismo mes, no mes siguiente
        if mes_interes <= fecha_corte:
            dtf_interes = obtener_dtf_mes(mes_interes.year, mes_interes.month)
            # Calcular días del mismo mes de la cuenta
            if mes_interes.month == 12:
                fecha_fin_mes = date(mes_interes.year + 1, 1, 1) - relativedelta(days=1)
            else:
                fecha_fin_mes = date(mes_interes.year, mes_interes.month + 1, 1) - relativedelta(days=1)
            dias_interes = fecha_fin_mes.day
        else:
            dtf_interes = 0.0
            dias_interes = 0

        cuenta = {
            'año': año,
            'mes': mes,
            'fecha_cuenta': fecha_cuenta,
            'capital': capital_fijo_tabla,  # SIEMPRE el capital base de la cuenta de cobro (ajustado por IPC y porcentaje), nunca duplicado por prima
            'capital_base': capital_fijo_tabla,
            'interes': interes_mensual,
            'prima': prima,
            'porcentaje_cuota': porcentaje_cuota_parte * 100,
            'base_calculo': base_calculo,
            'base_ajustada_ipc': base_ajustada_ipc,
            'ipc_factor': ipc_factor,
            'dias_interes': dias_interes,
            'dtf_interes': dtf_interes
        }

        cuentas.append(cuenta)
    
    return cuentas

def mostrar_liquidacion_tabla():
    # Mostrar la DTF usada para diciembre 2022
    dtf_dic_2022 = obtener_dtf_mes(2022, 12)
    print(f"DTF usada para diciembre 2022: {dtf_dic_2022:.2f}%")
    # Desglose mes a mes de la cartera de diciembre 2022
    print()
    print("DESGLOSE DE CARTERA DICIEMBRE 2022 MES A MES:")
    base_calculo = float(pensionado[5])
    numero_mesadas = pensionado[2]
    año_cartera = 2022
    mes_cartera = 12
    fecha_fin_cartera = date(2025, 8, 31)
    base_ajustada_ipc = ajustar_base_por_ipc(base_calculo, año_cartera)
    capital_fijo_mes = base_ajustada_ipc * cuentas[0]['porcentaje_cuota'] / 100
    if tiene_prima_mes(numero_mesadas, mes_cartera):
        capital_fijo_mes = capital_fijo_mes * 2
    fecha_inicio = date(año_cartera, mes_cartera, 1)
    num_meses = (fecha_fin_cartera.year - año_cartera) * 12 + (fecha_fin_cartera.month - mes_cartera) + 1
    total_intereses = 0.0
    for j in range(num_meses):
        fecha_interes = fecha_inicio + relativedelta(months=j)
        año_int = fecha_interes.year
        mes_int = fecha_interes.month
        fecha_cuenta_int = date(año_int, mes_int, 1)
        interes_mensual = calcular_interes_mensual_unico(capital_fijo_mes, fecha_cuenta_int, fecha_fin_cartera)
        total_intereses += interes_mensual
        print(f"{fecha_cuenta_int.strftime('%b %Y')}: Capital ${capital_fijo_mes:,.2f} + Interés ${interes_mensual:,.2f} = ${capital_fijo_mes + interes_mensual:,.2f}")
    print(f"TOTAL INTERESES: ${total_intereses:,.2f}")
    print(f"TOTAL CARTERA DICIEMBRE 2022: ${capital_fijo_mes + total_intereses:,.2f}")
    # Mostrar cartera de cuenta de cobro de diciembre 2022
    año_cartera = 2022
    mes_cartera = 12
    fecha_fin_cartera = date(2025, 8, 31)
    capital_mes, intereses_mes, cartera_mes = calcular_cartera_mes(pensionado, año_cartera, mes_cartera, fecha_fin_cartera)
    print()
    print(f"CARTERA DE CUENTA DE COBRO DICIEMBRE 2022:")
    print(f"- Capital diciembre 2022: ${capital_mes:,.2f}")
    print(f"- Intereses acumulados hasta agosto 2025: ${intereses_mes:,.2f}")
    print(f"- Total cartera diciembre 2022: ${cartera_mes:,.2f}")
    # Calcular y mostrar el consolidado global de cartera según la lógica solicitada
    fecha_inicio = date(2022, 9, 1)
    fecha_fin = date(2025, 8, 31)
    total_capital, total_intereses, consolidado = calcular_consolidado_global(pensionado, fecha_inicio, fecha_fin)
    print()
    print("CONSOLIDADO GLOBAL DE CARTERA (Sep 2022 → Ago 2025):")
    print(f"- Total capital: ${total_capital:,.2f}")
    print(f"- Total intereses acumulados: ${total_intereses:,.2f}")
    print(f"- Total cartera (capital + intereses): ${consolidado:,.2f}")
    """Muestra la liquidación de 36 meses en formato tabla"""
    
    # Obtener un pensionado de ejemplo
    session = get_session()
    try:
        query = text('''SELECT identificacion, nombre, numero_mesadas, 
                        fecha_ingreso_nomina, empresa, base_calculo_cuota_parte 
                        FROM pensionado LIMIT 1''')
        result = session.execute(query).fetchone()
    finally:
        session.close()
    
    if not result:
        print("No se encontraron pensionados en la base de datos")
        return
    
    pensionado = list(result)
    
    # Fecha de corte: hasta agosto 2025 (septiembre se liquida por separado)
    fecha_actual = date.today()
    fecha_corte = date(2025, 8, 31)  # Último día de agosto 2025
    
    # Información del pensionado
    print("=" * 80)
    print("LIQUIDACIÓN DE 36 MESES - CUOTAS PARTES (HACIA ATRÁS)")
    print("=" * 80)
    if not result:
        print("No se encontraron pensionados en la base de datos")
        return

    pensionado = list(result)

    # Fecha de corte: hasta agosto 2025 (septiembre se liquida por separado)
    fecha_actual = date.today()
    fecha_corte = date(2025, 8, 31)  # Último día de agosto 2025

    # Información del pensionado
    print("=" * 80)
    print("LIQUIDACIÓN DE 36 MESES - CUOTAS PARTES (HACIA ATRÁS)")
    print("=" * 80)
    print(f"Pensionado: {pensionado[1]}")
    print(f"Identificación: {pensionado[0]}")
    print(f"Empresa: {pensionado[4]}")
    print(f"Base Capital: ${pensionado[5]:,.2f}")
    print(f"Fecha Actual: {fecha_actual}")
    print(f"Período: Sep 2022 → Ago 2025 (36 meses)")
    print(f"Fecha Corte: {fecha_corte}")
    print(f"Nota: Sep 2025 se liquidará por separado")
    print("=" * 80)

    # Generar las 36 cuentas
    print("Generando cuentas...")
    cuentas = generar_36_cuentas_pensionado(pensionado, fecha_corte)

    # Encabezado de la tabla
    print()
    print("MES  FECHA        BASE AJUST.IPC  CAPITAL FIJO    DÍAS  DTF EA   INTERÉS MENSUAL TOTAL CUENTA")
    print("-" * 105)

    # Mostrar cada cuenta (NO mostrar la prima en la columna de capital; mostrar capital_base)
    total_intereses_todas_cuentas = 0

    for i, cuenta in enumerate(cuentas):
        capital_base = cuenta['capital_base']  # Mostrar siempre la base (sin prima)
        interes_mensual = cuenta['interes']  # Interés calculado sobre la base
        total_cuenta = capital_base + interes_mensual

        # Sumar solo intereses para totales generales
        total_intereses_todas_cuentas += interes_mensual

        fecha_str = cuenta['fecha_cuenta'].strftime('%b %Y')
        base_ajustada = cuenta['base_ajustada_ipc']
        dias = cuenta['dias_interes']
        dtf = cuenta['dtf_interes']

        print(f"{i+1:2d}   {fecha_str:10s}  ${base_ajustada:10,.2f}  ${capital_base:10,.2f}  {dias:3d}  {dtf:5.2f}%  ${interes_mensual:10,.2f}  ${total_cuenta:11,.2f}")

    # Totales finales: mostrar capital único (capital base), sumar intereses y total final
    gran_total_capital = cuentas[0]['capital_base'] if cuentas else 0.0
    gran_total_intereses = total_intereses_todas_cuentas
    gran_total = gran_total_capital + gran_total_intereses

    print("-" * 105)
    print(f"TOTALES:                                               ${gran_total_capital:10,.2f}           ${gran_total_intereses:10,.2f}  ${gran_total:11,.2f}")
    print("-" * 105)
    print()
    print("SISTEMA CORREGIDO - 36 MESES HACIA ATRÁS:")
    print(f"- Fecha inicio: {cuentas[0]['fecha_cuenta'].strftime('%b %Y')}")
    print(f"- Fecha fin: {cuentas[-1]['fecha_cuenta'].strftime('%b %Y')}")
    print(f"- Base cálculo 2025: ${cuentas[0]['base_calculo']:,.2f}")
    print(f"- % cuota parte: {cuentas[0]['porcentaje_cuota']:.2f}%")
    print()
    print("AJUSTES POR AÑO:")
    años_mostrados = set()
    for cuenta in cuentas:
        if cuenta['año'] not in años_mostrados:
            print(f"  {cuenta['año']}: ${cuenta['base_calculo']:,.2f} → ${cuenta['base_ajustada_ipc']:,.2f} (÷{cuenta['ipc_factor']:.3f})")
            años_mostrados.add(cuenta['año'])
    print()
    print("CARACTERÍSTICAS:")
    print("- Período: Sep 2022 → Ago 2025 (36 meses exactos)")
    print("- Excluye: Sep 2025 (se liquidará por separado)")
    print("- Cada cuenta tiene CAPITAL FIJO ajustado por IPC del año")
    print("- Interés MENSUAL individual (solo del mes siguiente)")  
    print("- Fórmula Excel: Capital × ((1+DTF)^(días/365) - 1)")
    print("- DTF tomada de la base de datos")
    print("- NO se capitaliza (interés sobre interés)")

    # Calcular y mostrar el consolidado global de cartera según la lógica solicitada
    fecha_inicio = date(2022, 9, 1)
    fecha_fin = date(2025, 8, 31)
    total_capital, total_intereses, consolidado = calcular_consolidado_global(pensionado, fecha_inicio, fecha_fin)
    print()
    print("CONSOLIDADO GLOBAL DE CARTERA (Sep 2022 → Ago 2025):")
    print(f"- Total capital: ${total_capital:,.2f}")
    print(f"- Total intereses acumulados: ${total_intereses:,.2f}")
    print(f"- Total cartera (capital + intereses): ${consolidado:,.2f}")