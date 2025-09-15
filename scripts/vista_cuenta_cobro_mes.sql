CREATE OR REPLACE VIEW v_cuenta_cobro_mes AS
WITH base AS (
  SELECT
      p.pago_id,
      p.pensionado_id,
      p.periodo_liquidacion_id,
      -- BASE DE CÁLCULO (tu "valor de mesada" para concurrencia)
      COALESCE(pe.base_calculo_cuota_parte, 0) AS base_calculo,
      -- % cuota parte / concurrencia (si no existe, lo estimamos desde p.valor)
      COALESCE(
        pe.porcentaje_cuota_parte,
        CASE
          WHEN COALESCE(pe.base_calculo_cuota_parte, 0) > 0
          THEN ROUND(100 * p.valor / pe.base_calculo_cuota_parte, 6)
          ELSE 0
        END
      ) AS pct_conc
  FROM pago p
  JOIN pensionado pe ON pe.pensionado_id = p.pensionado_id
  JOIN periodo_liquidacion pl ON pl.periodo_liquidacion_id = p.periodo_liquidacion_id
)
SELECT
  pe.identificacion                         AS `No. Cédula`,
  pe.nombre                                 AS `Apellidos y Nombres`,
  ''                                        AS `SUSTITUTO`,
  ''                                        AS `No. DOCUMENTO SUSTITUTO`,
  CAST(b.pct_conc AS DECIMAL(10,6))         AS `% DE CONCURRENCIA`,
  CAST(b.base_calculo AS DECIMAL(18,2))     AS `VALOR MESADA`,
  pl.fecha_inicio                           AS `PERIODO LIQUIDADO (INICIO)`,
  pl.fecha_fin                              AS `PERIODO LIQUIDADO (FIN)`,
  p.valor                                   AS `CAPITAL`,
  p.interes                                 AS `INTERESES`,
  (p.valor + p.interes)                     AS `TOTAL`,
  ''                                        AS `OBSERVACIONES`
FROM pago p
JOIN pensionado pe ON pe.pensionado_id = p.pensionado_id
JOIN base b        ON b.pago_id       = p.pago_id
JOIN periodo_liquidacion pl ON pl.periodo_liquidacion_id = p.periodo_liquidacion_id;
