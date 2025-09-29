"""
Módulo para ajustes históricos y corrección por IPC
"""

def ajustar_base_por_ipc(valor_base, año_inicial, año_final):
    """Ajusta un valor base por IPC entre dos años"""
    
    # IPC acumulado aproximado por años
    ipc_acumulado = {
        2022: 13.12,  # IPC Colombia 2022
        2023: 9.28,   # IPC Colombia 2023  
        2024: 5.11,   # IPC Colombia 2024 (estimado)
        2025: 4.50,   # IPC Colombia 2025 (proyectado)
    }
    
    factor_ajuste = 1.0
    
    for año in range(año_inicial + 1, año_final + 1):
        if año in ipc_acumulado:
            factor_ajuste *= (1 + ipc_acumulado[año] / 100)
    
    return valor_base * factor_ajuste