CREATE OR REPLACE VIEW v_liq_mensual_reporte AS
SELECT
    ROW_NUMBER() OVER (ORDER BY p.pago_id) AS `No.`,
    pe.nombre AS `APELLIDOS Y NOMBRES DEL PENSIONADO`,
    pe.identificacion AS `No. DOCUMENTO`,
    COALESCE(pe.nombre_sustituto, '') AS `SUSTITUTO`,
    COALESCE(pe.cedula_sustituto, '') AS `No. DOCUMENTO SUSTITUTO`,
    pe.porcentaje_cuota_parte AS `% DE CONCURRENCIA`,
    pe.base_calculo_cuota_parte AS `VALOR MESADA`,
    pl.fecha_inicio AS `PERIODO LIQUIDADO (INICIO)`,
    pl.fecha_fin AS `PERIODO LIQUIDADO (FIN)`,
    p.valor AS `CAPITAL`,
    0 AS `INTERESES`,
    p.valor AS `TOTAL`
FROM pago p
JOIN periodo_liquidacion pl ON pl.periodo_liquidacion_id = p.periodo_liquidacion_id
JOIN pensionado pe ON pe.pensionado_id = p.pensionado_id;
