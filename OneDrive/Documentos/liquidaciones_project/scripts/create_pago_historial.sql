CREATE TABLE IF NOT EXISTS pago_historial (
  pago_historial_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  pago_id           BIGINT NOT NULL,
  fecha_version     DATETIME NOT NULL,
  valor_anterior    DECIMAL(18,2) NOT NULL,
  capital_anterior  DECIMAL(18,2) NOT NULL,
  interes_anterior  DECIMAL(18,2) NOT NULL,
  motivo            VARCHAR(255),
  FOREIGN KEY (pago_id) REFERENCES pago(pago_id)
);