SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS pago;
DROP TABLE IF EXISTS periodo_liquidacion;
DROP TABLE IF EXISTS pensionado;
DROP TABLE IF EXISTS entidad;
DROP TABLE IF EXISTS dtf_mensual;
DROP TABLE IF EXISTS ipc_anual;
DROP TABLE IF EXISTS liquidacion;

SET FOREIGN_KEY_CHECKS = 1;

-- 1. Tabla entidad
CREATE TABLE entidad (
  entidad_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  nit VARCHAR(20) NOT NULL,
  nombre VARCHAR(200) NOT NULL
);

-- 2. Tabla pensionado
CREATE TABLE pensionado (
  pensionado_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(200),
  identificacion VARCHAR(30),
  res_no VARCHAR(50),
  reliqui VARCHAR(50),
  consulta VARCHAR(50),
  estado_cartera VARCHAR(50),
  fecha_ingreso_nomina DATE,
  ultima_fecha_pago DATE,
  capital_pendiente DECIMAL(18,2),
  intereses_pendientes DECIMAL(18,2),
  regional VARCHAR(100),
  porcentaje_cuota_parte DECIMAL(8,4),
  cuota_parte_inicial DECIMAL(18,2),
  numero_mesadas INT,
  porcentaje_salud DECIMAL(8,4),
  pension_pagada_sena DECIMAL(18,2),
  pension_pagada_iss DECIMAL(18,2),
  empresa VARCHAR(200),
  nit_entidad VARCHAR(20),
  cedula_sustituto VARCHAR(30),
  nombre_sustituto VARCHAR(200),
  base_calculo_cuota_parte DECIMAL(18,2)
);

-- 3. Tabla dtf_mensual
CREATE TABLE dtf_mensual (
  periodo DATE PRIMARY KEY,
  tasa DECIMAL(9,6) NOT NULL
);

-- 4. Tabla ipc_anual
CREATE TABLE ipc_anual (
  anio INT PRIMARY KEY,
  valor DECIMAL(9,6) NOT NULL
);

-- 5. Tabla periodo_liquidacion
CREATE TABLE periodo_liquidacion (
  periodo_liquidacion_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  fecha_inicio DATE NOT NULL,
  fecha_fin DATE NOT NULL
);

CREATE TABLE pago (
  pago_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  pensionado_id BIGINT NOT NULL,
  periodo_liquidacion_id BIGINT,
  fecha_pago DATE NOT NULL,
  valor DECIMAL(18,2) NOT NULL,
  observaciones VARCHAR(255),
  FOREIGN KEY (pensionado_id) REFERENCES pensionado(pensionado_id),
  FOREIGN KEY (periodo_liquidacion_id) REFERENCES periodo_liquidacion(periodo_liquidacion_id)
);

-- Tabla de liquidaciones mensuales por pensionado y periodo
CREATE TABLE IF NOT EXISTS liquidacion (
  liquidacion_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  pensionado_id BIGINT NOT NULL,
  fecha DATE NOT NULL,
  capital DECIMAL(18,2) NOT NULL,
  interes DECIMAL(18,2) NOT NULL,
  valor DECIMAL(18,2) NOT NULL,
  observaciones VARCHAR(255),
  fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
  fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (pensionado_id) REFERENCES pensionado(pensionado_id)
);