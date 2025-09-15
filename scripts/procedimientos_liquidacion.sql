DELIMITER $$
-- Procedimientos almacenados para liquidación mensual y global
-- Adaptados a la estructura de tus tablas actuales




DROP PROCEDURE IF EXISTS sp_generar_liq_mensual$$
CREATE PROCEDURE sp_generar_liq_mensual(
    IN p_nit_entidad VARCHAR(20),
    IN p_identificacion VARCHAR(30),
    IN p_base_actual DECIMAL(18,2),
    IN p_periodo DATE,
    IN p_anio_base INT,
    IN p_ultima_fecha_pago DATE,
    IN p_modo ENUM('preview','crear','reprocesar') -- NUEVO
)
BEGIN
    DECLARE v_pensionado_id BIGINT;
    DECLARE v_porcentaje    DECIMAL(9,6);
    DECLARE v_num_mesadas   INT;
    DECLARE v_base_mes      DECIMAL(18,2);
    DECLARE v_capital       DECIMAL(18,2);
    DECLARE v_dtf_ea        DECIMAL(9,6);
    DECLARE v_interes       DECIMAL(18,2);
    DECLARE v_total         DECIMAL(18,2);
    DECLARE v_anio_obj      INT;
    DECLARE v_anio_cursor   INT;
    DECLARE v_ipc           DECIMAL(9,6);
    DECLARE v_dias_mes      INT;
    DECLARE v_es_prima      BOOLEAN;
    DECLARE v_inicio        DATE;
    DECLARE v_fin           DATE;
    DECLARE v_prev_month_start DATE;
    DECLARE v_pago_id BIGINT DEFAULT NULL;
    DECLARE v_total_prev DECIMAL(18,2);
    DECLARE v_cap_prev   DECIMAL(18,2);
    DECLARE v_int_prev   DECIMAL(18,2);
    DECLARE v_fecha_creacion DATETIME;
    DECLARE v_fecha_actualizacion DATETIME;

    main_block: BEGIN

        -- 1) Validaciones y datos del pensionado
        SELECT p.pensionado_id, p.porcentaje_cuota_parte, p.numero_mesadas
        INTO   v_pensionado_id, v_porcentaje,            v_num_mesadas
        FROM pensionado p
        WHERE p.identificacion = p_identificacion
          AND p.nit_entidad    = p_nit_entidad
        LIMIT 1;

        IF v_pensionado_id IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Pensionado no encontrado';
        END IF;

        -- Evitar duplicar/liquidar meses ya pagos (opcional)
        IF p_ultima_fecha_pago IS NOT NULL AND LAST_DAY(p_periodo) <= p_ultima_fecha_pago THEN
            LEAVE main_block;
        END IF;

        -- 2) Determinar período calendario
        SET v_inicio   = DATE_SUB(p_periodo, INTERVAL (DAY(p_periodo)-1) DAY);
        SET v_fin      = LAST_DAY(p_periodo);
        SET v_dias_mes = DAY(v_fin);
        SET v_anio_obj = YEAR(v_inicio);

        -- 3) Traer la base del año objetivo (desindexar por IPC desde p_anio_base → v_anio_obj)
        SET v_base_mes = p_base_actual;
        SET v_anio_cursor = p_anio_base;
        WHILE v_anio_cursor > v_anio_obj DO
            SELECT valor INTO v_ipc FROM ipc_anual WHERE anio = v_anio_cursor LIMIT 1;
            IF v_ipc IS NULL THEN SET v_ipc = 0; END IF;
            SET v_base_mes = v_base_mes / (1 + v_ipc);
            SET v_anio_cursor = v_anio_cursor - 1;
        END WHILE;

        -- 4) ¿Hay prima?
        SET v_es_prima =
            (v_num_mesadas = 14 AND MONTH(v_inicio) IN (6,12))
            OR
            (v_num_mesadas = 13 AND MONTH(v_inicio) = 12);

        -- 5) Cuota parte: base de cálculo × % cuota parte × (1 o 2 si prima)
    SET v_capital = v_base_mes * v_porcentaje * (CASE WHEN v_es_prima THEN 2 ELSE 1 END);

        -- 6) Interés solo si el periodo liquidado es anterior o igual al mes inmediatamente anterior
        SET v_prev_month_start = DATE_SUB(DATE_SUB(CURDATE(), INTERVAL DAY(CURDATE())-1 DAY), INTERVAL 1 MONTH);
        IF v_fin < v_prev_month_start THEN
            SELECT tasa INTO v_dtf_ea
            FROM dtf_mensual
            WHERE YEAR(periodo) = YEAR(v_inicio) AND MONTH(periodo) = MONTH(v_inicio)
            LIMIT 1;
            IF v_dtf_ea IS NULL THEN SET v_dtf_ea = 0; END IF;
            -- La tasa ya está en decimales, no dividir entre 100
            SET v_interes = ROUND( v_capital * ( POW(1 + v_dtf_ea, v_dias_mes/365.0 ) - 1 ), 2 );
        ELSE
            SET v_interes = 0;
        END IF;
        SET v_total = v_capital + v_interes;

        -- 7) Buscar si ya existe liquidación para ese pensionado y periodo
        SELECT p.pago_id, p.valor, p.capital, p.interes, p.fecha_creacion, p.fecha_actualizacion
        INTO   v_pago_id,  v_total_prev, v_cap_prev, v_int_prev, v_fecha_creacion, v_fecha_actualizacion
        FROM pago p
        WHERE p.pensionado_id = v_pensionado_id
          AND p.fecha_pago    = v_inicio
        LIMIT 1;

        -- 8) Persistencia y control de duplicados según p_modo
        IF p_modo = 'preview' THEN
            SELECT
                'PREVIEW'           AS estado,
                v_inicio            AS periodo_inicio,
                v_fin               AS periodo_fin,
                v_capital           AS capital_calculado,
                v_interes           AS interes_calculado,
                v_total             AS total_calculado,
                (v_pago_id IS NOT NULL) AS es_duplicado,
                v_pago_id           AS pago_existente_id,
                v_cap_prev          AS capital_existente,
                v_int_prev          AS interes_existente,
                v_total_prev        AS total_existente,
                v_fecha_creacion    AS fecha_creacion,
                v_fecha_actualizacion AS fecha_actualizacion;
            LEAVE main_block;
        END IF;

        IF p_modo = 'crear' THEN
            IF v_pago_id IS NOT NULL THEN
                SELECT
                    'DUPLICADO'   AS estado,
                    v_pago_id     AS pago_existente_id,
                    v_inicio      AS periodo_inicio,
                    v_fin         AS periodo_fin,
                    v_total_prev  AS total_existente,
                    v_fecha_creacion AS fecha_creacion,
                    v_fecha_actualizacion AS fecha_actualizacion;
                LEAVE main_block;
            ELSE
                INSERT INTO pago (pensionado_id, fecha_pago, valor, capital, interes, observaciones)
                VALUES (v_pensionado_id, v_inicio, v_total, v_capital, v_interes, 'Liquidación generada (crear)');
                SELECT
                    'CREADO'        AS estado,
                    LAST_INSERT_ID() AS pago_id,
                    v_inicio        AS periodo_inicio,
                    v_fin           AS periodo_fin,
                    v_capital       AS capital,
                    v_interes       AS interes,
                    v_total         AS total;
                LEAVE main_block;
            END IF;
        END IF;

        IF p_modo = 'reprocesar' THEN
            IF v_pago_id IS NOT NULL THEN
                -- Guardar histórico del valor anterior
                INSERT INTO pago_historial (
                    pago_id, fecha_version, valor_anterior, capital_anterior, interes_anterior, motivo
                ) VALUES (
                    v_pago_id, NOW(), v_total_prev, v_cap_prev, v_int_prev, 'Reproceso solicitado'
                );

                -- Actualizar el registro existente con los nuevos cálculos
                UPDATE pago
                SET valor = v_total,
                    capital = v_capital,
                    interes = v_interes,
                    observaciones = CONCAT('Reprocesado ', DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i'))
                WHERE pago_id = v_pago_id;

                SELECT
                    'REPROCESADO' AS estado,
                    v_pago_id     AS pago_id,
                    v_inicio      AS periodo_inicio,
                    v_fin         AS periodo_fin,
                    v_capital     AS capital_nuevo,
                    v_interes     AS interes_nuevo,
                    v_total       AS total_nuevo,
                    v_total_prev  AS total_anterior,
                    v_fecha_creacion AS fecha_creacion,
                    v_fecha_actualizacion AS fecha_actualizacion;
                LEAVE main_block;
            ELSE
                -- No existía: lo creamos
                INSERT INTO pago (pensionado_id, fecha_pago, valor, capital, interes, observaciones)
                VALUES (v_pensionado_id, v_inicio, v_total, v_capital, v_interes, 'Liquidación generada (reprocesar, no existía)');
                SELECT
                    'CREADO'         AS estado,
                    LAST_INSERT_ID() AS pago_id,
                    v_inicio         AS periodo_inicio,
                    v_fin            AS periodo_fin,
                    v_capital        AS capital,
                    v_interes        AS interes,
                    v_total          AS total;
                LEAVE main_block;
            END IF;
        END IF;

        -- Si p_modo trae otro valor:
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT = 'p_modo inválido. Use: preview | crear | reprocesar';

    END main_block;
END$$



DROP PROCEDURE IF EXISTS sp_generar_liq_36$$
CREATE PROCEDURE sp_generar_liq_36(
    IN p_nit_entidad VARCHAR(20),
    IN p_identificacion VARCHAR(30),
    IN p_base_actual DECIMAL(18,2),
    IN p_anio_base INT,
    IN p_ultima_fecha_pago DATE,
    IN p_periodo_hasta DATE
)
BEGIN
    DECLARE i INT DEFAULT 0;
    DECLARE v_periodo DATE;
    SET v_periodo = p_periodo_hasta;
    WHILE i < 36 DO
        CALL sp_generar_liq_mensual(p_nit_entidad, p_identificacion, p_base_actual, v_periodo, p_anio_base, p_ultima_fecha_pago);
        SET v_periodo = DATE_SUB(v_periodo, INTERVAL 1 MONTH);
        SET i = i + 1;
    END WHILE;
END$$



DROP PROCEDURE IF EXISTS sp_liq_global_informativo$$
CREATE PROCEDURE sp_liq_global_informativo(
        IN p_nit_entidad VARCHAR(20),
        IN p_identificacion VARCHAR(30),
        IN p_periodo_desde DATE,
        IN p_periodo_hasta DATE
)
BEGIN
        SELECT p.pensionado_id, pl.fecha_inicio, pl.fecha_fin, p.valor, p.observaciones
        FROM pago p
        JOIN periodo_liquidacion pl ON p.periodo_liquidacion_id = pl.periodo_liquidacion_id
        JOIN pensionado pe ON p.pensionado_id = pe.pensionado_id
        WHERE pe.identificacion = p_identificacion
            AND pe.nit_entidad = p_nit_entidad
            AND pl.fecha_inicio >= p_periodo_desde
            AND pl.fecha_fin <= p_periodo_hasta
        ORDER BY pl.fecha_inicio;
END$$

DELIMITER ;
