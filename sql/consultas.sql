-- =====================================================================
-- consultas.sql
-- Consultas de histórico del Sistema de Seguridad IoT (Parcial #2 - DS8)
--
-- Base de datos: SQLite
-- Archivo:       data/seguridad.db  (se genera al ejecutar el backend)
--
-- Cómo ejecutarlas:
--   sqlite3 data/seguridad.db < sql/consultas.sql
--   o bien desde el REPL:
--     $ sqlite3 data/seguridad.db
--     sqlite> .read sql/consultas.sql
--
-- (También están disponibles en Python con:
--     python -m backend.queries resumen | lecturas | eventos | comandos )
-- =====================================================================

.mode column
.headers on

-- ---------------------------------------------------------------------
-- 1. Últimas 20 lecturas de sensores, de la más reciente a la más vieja
-- ---------------------------------------------------------------------
SELECT id,
       recibido_at,
       motion   AS movimiento,
       lux,
       light_state AS luz,
       armed    AS armado,
       alarm    AS alarma,
       detail
FROM lecturas
ORDER BY id DESC
LIMIT 20;

-- ---------------------------------------------------------------------
-- 2. Momentos en los que se detectó movimiento (historial de intrusiones)
-- ---------------------------------------------------------------------
SELECT recibido_at,
       detalle,
       estado,
       fuente,
       extra
FROM eventos
WHERE tipo = 'MOTION_DETECTED'
ORDER BY id DESC;

-- ---------------------------------------------------------------------
-- 3. Histórico completo de alarmas (activadas, silenciadas, por timeout)
-- ---------------------------------------------------------------------
SELECT recibido_at, tipo, detalle, fuente
FROM vista_alarmas;

-- ---------------------------------------------------------------------
-- 4. Comandos ejecutados, con su estado final (trazabilidad)
--     ENVIADO  -> el backend lo publicó por MQTT
--     APLICADO -> el dispositivo confirmó la recepción
--     RECHAZADO-> comando inválido o no soportado
-- ---------------------------------------------------------------------
SELECT id,
       recibido_at,
       origen,
       comando,
       estado,
       detalle
FROM comandos
ORDER BY id DESC;

-- ---------------------------------------------------------------------
-- 5. Lecturas dentro de un rango de fechas (parámetros: cambiar valores)
-- ---------------------------------------------------------------------
SELECT recibido_at, motion, lux, armed, alarm
FROM lecturas
WHERE recibido_at BETWEEN '2026-11-08T00:00:00' AND '2026-11-08T23:59:59'
ORDER BY recibido_at DESC;

-- ---------------------------------------------------------------------
-- 6. Promedio, máximo y mínimo de iluminación registrada
-- ---------------------------------------------------------------------
SELECT ROUND(AVG(lux), 1) AS lux_promedio,
       MAX(lux)           AS lux_maximo,
       MIN(lux)           AS lux_minimo,
       COUNT(*)           AS muestras
FROM lecturas
WHERE lux IS NOT NULL;

-- ---------------------------------------------------------------------
-- 7. Cantidad de eventos por tipo (distribución de actividad)
-- ---------------------------------------------------------------------
SELECT tipo,
       COUNT(*)             AS cantidad,
       MAX(recibido_at)     AS ultimo
FROM eventos
GROUP BY tipo
ORDER BY cantidad DESC;

-- ---------------------------------------------------------------------
-- 8. Lecturas tomadas con el sistema armado y movimiento detectado
--    (posibles intrusiones registradas en la base)
-- ---------------------------------------------------------------------
SELECT recibido_at, lux, light_state, detail
FROM lecturas
WHERE armed = 1 AND motion = 1
ORDER BY id DESC;

-- ---------------------------------------------------------------------
-- 9. Última lectura conocida del sistema
-- ---------------------------------------------------------------------
SELECT * FROM vista_ultima_lectura;

-- ---------------------------------------------------------------------
-- 10. Resumen general (un vistazo rápido al sistema)
-- ---------------------------------------------------------------------
SELECT (SELECT COUNT(*) FROM lecturas)   AS total_lecturas,
       (SELECT COUNT(*) FROM eventos)    AS total_eventos,
       (SELECT COUNT(*) FROM comandos)   AS total_comandos,
       (SELECT COUNT(*) FROM eventos
         WHERE tipo = 'MOTION_DETECTED') AS movimientos,
       (SELECT COUNT(*) FROM eventos
         WHERE tipo = 'ALARM_ON')        AS alarmas;
