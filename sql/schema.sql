-- =====================================================================
-- schema.sql
-- Base de datos SQLite del Sistema de Seguridad IoT (Parcial #2 - DS8)
-- Utilizado por: backend/database.py
--
-- Tres tablas principales:
--   lecturas -> datos de sensores con timestamp (históricos)
--   eventos  -> eventos de seguridad (movimiento, alarma, comandos)
--   comandos -> comandos ejecutados y su estado de aplicación
-- =====================================================================

PRAGMA journal_mode = WAL;

-- ---------------------------------------------------------------------
-- 1. LECTURAS DE SENSORES (telemetría)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lecturas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT    NOT NULL,
    ts_dispositivo  INTEGER,                       -- epoch del ESP32 (NTP)
    recibido_at     TEXT    NOT NULL,              -- fecha/hora local ISO-8601
    motion          INTEGER NOT NULL,              -- 1 = movimiento detectado
    lux             REAL,                          -- iluminación calculada
    light_state     TEXT,                          -- OSCURO / NORMAL / CLARO
    armed           INTEGER NOT NULL,              -- 1 = sistema armado
    alarm           INTEGER NOT NULL,              -- 1 = alarma activa
    detail          TEXT,                          -- descripción del estado
    last_cmd        TEXT                           -- último comando recibido
);

CREATE INDEX IF NOT EXISTS idx_lecturas_recibido ON lecturas(recibido_at);
CREATE INDEX IF NOT EXISTS idx_lecturas_motion   ON lecturas(motion);

-- ---------------------------------------------------------------------
-- 2. EVENTOS DE SEGURIDAD
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eventos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT    NOT NULL,
    ts_dispositivo  INTEGER,
    recibido_at     TEXT    NOT NULL,
    tipo            TEXT    NOT NULL,              -- MOTION_DETECTED, ARMED...
    detalle         TEXT,
    estado          TEXT,                          -- DESARMADO/ARMADO/ALARMA
    fuente          TEXT,                          -- pir / mqtt / boton_local
    extra           TEXT                           -- JSON con datos extra
);

CREATE INDEX IF NOT EXISTS idx_eventos_tipo ON eventos(tipo);
CREATE INDEX IF NOT EXISTS idx_eventos_ts   ON eventos(recibido_at);

-- ---------------------------------------------------------------------
-- 3. COMANDOS EJECUTADOS (trazabilidad de control remoto)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comandos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT    NOT NULL,
    recibido_at     TEXT    NOT NULL,
    origen          TEXT    NOT NULL,              -- mqtt / thingspeak / cli
    comando         TEXT    NOT NULL,              -- ARM, DISARM, SILENCE...
    estado          TEXT    NOT NULL DEFAULT 'RECIBIDO',
    detalle         TEXT
);

CREATE INDEX IF NOT EXISTS idx_comandos_ts ON comandos(recibido_at);

-- ---------------------------------------------------------------------
-- 4. VISTAS ÚTILES PARA LOS HISTÓRICOS
-- ---------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS vista_ultima_lectura AS
SELECT * FROM lecturas WHERE id = (SELECT MAX(id) FROM lecturas);

CREATE VIEW IF NOT EXISTS vista_alarmas AS
SELECT recibido_at, tipo, detalle, fuente
FROM eventos
WHERE tipo IN ('ALARM_ON', 'ALARM_SILENCED', 'ALARM_TIMEOUT',
               'MOTION_DETECTED')
ORDER BY id DESC;
