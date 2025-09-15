# Objetivo (Copilot): definir modelos equivalentes a tablas del init_db.sql
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, BIGINT, VARCHAR, DATE, DATETIME, DECIMAL, Integer, Enum

Base = declarative_base()

# Ejemplo mínimo:
class Entidad(Base):
    __tablename__ = "entidad"
    entidad_id = Column(BIGINT, primary_key=True, autoincrement=True)
    nit = Column(VARCHAR(20), nullable=False)
    nombre = Column(VARCHAR(200), nullable=False)
    email_cobro = Column(VARCHAR(200))
    # ...

class Pensionado(Base):
    __tablename__ = "pensionado"
    pensionado_id = Column(BIGINT, primary_key=True, autoincrement=True)
    identificacion = Column(VARCHAR(30), nullable=False, unique=True)
    nombre = Column(VARCHAR(200), nullable=False)
    estado_cartera = Column(VARCHAR(100))
    fecha_ingreso_nomina = Column(DATE)
    ultima_fecha_pago = Column(DATE)
    capital_pendiente = Column(DECIMAL(18,2))
    intereses_pendientes = Column(DECIMAL(18,2))
    regional = Column(VARCHAR(100))
    porcentaje_cuota_parte = Column(DECIMAL(9,6))
    cuota_parte_inicial = Column(DECIMAL(18,2))
    numero_mesadas = Column(Integer)
    porcentaje_salud = Column(DECIMAL(9,6))
    pension_pagada_sena = Column(DECIMAL(18,2))
    pension_pagada_iss = Column(DECIMAL(18,2))
    empresa = Column(VARCHAR(200))
    nit_entidad = Column(VARCHAR(30))
    cedula_sustituto = Column(VARCHAR(30))
    nombre_sustituto = Column(VARCHAR(200))
    base_calculo_cuota_parte = Column(DECIMAL(18,2))
    res_no = Column(VARCHAR(100))
    reliqui = Column(VARCHAR(100))
    consulta = Column(VARCHAR(100))
# Tabla de pagos mensuales por pensionado y periodo
class Pago(Base):
    __tablename__ = "pago"
    pago_id = Column(BIGINT, primary_key=True, autoincrement=True)
    pensionado_id = Column(BIGINT, nullable=False)
    fecha_pago = Column(DATE, nullable=False)
    valor = Column(DECIMAL(18,2), nullable=False)
    observaciones = Column(VARCHAR(255))

# Tabla de periodos de liquidación (por pensionado, año, mes)
class PeriodoLiquidacion(Base):
    __tablename__ = "periodo_liquidacion"
    periodo_liquidacion_id = Column(BIGINT, primary_key=True, autoincrement=True)
    pensionado_id = Column(BIGINT, nullable=False)
    anio = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)
    fecha_inicio = Column(DATE)
    fecha_fin = Column(DATE)
    base_calculo = Column(DECIMAL(18,2))
    ipc = Column(DECIMAL(9,6))
    dtf = Column(DECIMAL(9,6))
    cuota_parte = Column(DECIMAL(18,2))
    periodos = Column(Integer)
    pagos_periodo = Column(DECIMAL(18,2))
    saldo_pendiente = Column(DECIMAL(18,2))
    intereses = Column(DECIMAL(18,2))
    acumulado = Column(DECIMAL(18,2))

class DtfMensual(Base):
    __tablename__ = "dtf_mensual"
    periodo = Column(DATE, primary_key=True)
    tasa = Column(DECIMAL(9,6), nullable=False)

class Mesada(Base):
    __tablename__ = "mesada"
    mesada_id = Column(BIGINT, primary_key=True, autoincrement=True)
    pensionado_id = Column(BIGINT, nullable=False)
    periodo = Column(DATE, nullable=False)
    valor_mesada = Column(DECIMAL(18,2), nullable=False)
    # ...

class IpcAnual(Base):
    __tablename__ = "ipc_anual"
    anio = Column(Integer, primary_key=True)
    valor = Column(DECIMAL(9,6), nullable=False)
