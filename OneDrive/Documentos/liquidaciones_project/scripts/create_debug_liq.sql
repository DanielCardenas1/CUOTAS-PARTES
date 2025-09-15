-- Crear tabla de depuración fuera del procedimiento
CREATE TABLE IF NOT EXISTS debug_liq (
    debug_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    pensionado_id BIGINT,
    periodo DATE,
    v_fin DATE,
    v_prev_month_start DATE,
    v_interes DECIMAL(18,2),
    creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
