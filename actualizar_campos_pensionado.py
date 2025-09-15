import pandas as pd
from sqlalchemy import create_engine

# Configuración de conexión (ajusta usuario y contraseña)
engine = create_engine("mysql+mysqlconnector://usuario:contraseña@localhost:3306/liquidaciones")

# Carga el Excel directamente
# Usa el archivo correcto
# Asegúrate de tener instalado openpyxl: pip install openpyxl

df = pd.read_excel("PRUEBAS BASE DE DATOS.xlsx")

for _, row in df.iterrows():
    identificacion = str(row['Identificacion'])  # Ajusta si tu Excel tiene otro nombre de columna
    res_no = str(row['Res. No'])
    reliqui = str(row['Reliqui'])
    consulta = str(row['Consulta'])

    engine.execute(
        "UPDATE pensionado SET res_no=%s, reliqui=%s, consulta=%s WHERE identificacion=%s",
        (res_no, reliqui, consulta, identificacion)
    )

print("Actualización completada.")
