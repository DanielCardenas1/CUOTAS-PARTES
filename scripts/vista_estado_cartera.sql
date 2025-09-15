-- Vista de estado de cartera con intereses de mora
-- Muestra por cada cuenta de cobro (liquidacion_detalle) el valor liquidado, pagado, saldo, intereses de mora y estado

CREATE OR REPLACE VIEW v_estado_cartera AS
SELECT
  ld.liquidacion_id,
  l.consecutivo AS cuenta_cobro,
  e.nit AS nit_entidad,
  e.nombre AS entidad,
  p.identificacion,
  p.nombre AS pensionado,
  ld.periodo AS periodo,
  ld.capital + ld.interes AS valor_liquidado,
  COALESCE(SUM(pg.valor), 0) AS valor_pagado,
  (ld.capital + ld.interes - COALESCE(SUM(pg.valor), 0)) AS saldo_pendiente,
  CASE 
    WHEN (ld.capital + ld.interes - COALESCE(SUM(pg.valor), 0)) > 0 AND ld.periodo < DATE_FORMAT(CURDATE(), '%Y-%m-01')
      THEN ROUND((ld.capital + ld.interes - COALESCE(SUM(pg.valor), 0)) * COALESCE(dt.tasa,0), 2)
    ELSE 0
  END AS intereses_mora,
  CASE 
    WHEN (ld.capital + ld.interes - COALESCE(SUM(pg.valor), 0)) > 0 AND ld.periodo < DATE_FORMAT(CURDATE(), '%Y-%m-01')
      THEN 'En mora'
    WHEN (ld.capital + ld.interes - COALESCE(SUM(pg.valor), 0)) <= 0 THEN 'Pagada'
    ELSE 'Al día'
  END AS estado
FROM liquidacion l
JOIN entidad e ON l.entidad_id = e.entidad_id
JOIN liquidacion_detalle ld ON ld.liquidacion_id = l.liquidacion_id
JOIN pensionado p ON ld.pensionado_id = p.pensionado_id
LEFT JOIN pago pg ON pg.identificacion = p.identificacion AND pg.nit_entidad = e.nit AND pg.fecha_pago = ld.periodo
LEFT JOIN dtf_mensual dt ON dt.periodo = ld.periodo
GROUP BY ld.liquidacion_id, ld.periodo;
