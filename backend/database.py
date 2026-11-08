"""
backend/database.py
=====================================================================
Capa de persistencia: SQLite (lecturas, eventos y comandos).

Características:
  * Crea el esquema automáticamente a partir de `sql/schema.sql`.
  * Timestamps en ISO-8601 locales + timestamp del dispositivo.
  * API simple: insert_lectura / insert_evento / insert_comando.
  * Soporte de consultas para los históricos (módulo backend.queries).
  * Hilo seguro: el puente MQTT corre en un hilo distinto al
    principal, por lo que la conexión se comparte con candado
    (RLock) y `check_same_thread=False`.

Uso:
    from backend.database import Database
    db = Database()
    db.insert_lectura(payload)
    print(db.ultimas_lecturas(10))
=====================================================================
"""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from backend import config


class Database:
    """Repositorio de datos del sistema de seguridad (thread-safe)."""

    def __init__(self, path=None):
        self.path = Path(path) if path else Path(config.DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Conexión y esquema
    # ------------------------------------------------------------------
    @property
    def connection(self) -> sqlite3.Connection:
        """Devuelve la conexión activa (la crea y aplica el esquema)."""
        if self._conn is None:
            # check_same_thread=False: la usaremos desde el hilo MQTT
            self._conn = sqlite3.connect(
                str(self.path), check_same_thread=False, timeout=30)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._init_schema()
        return self._conn

    def _init_schema(self):
        """Ejecuta sql/schema.sql (fuente única del esquema)."""
        schema_file = config.SQL_DIR / "schema.sql"
        if not schema_file.exists():            # pragma: no cover
            raise FileNotFoundError(
                "No se encontró {} — ejecuta el proyecto desde la raíz "
                "del repositorio.".format(schema_file))
        sql = schema_file.read_text(encoding="utf-8")
        self._conn.executescript(sql)
        self._conn.commit()

    @staticmethod
    def now_iso() -> str:
        """Fecha/hora local en formato ISO-8601."""
        return datetime.now().isoformat(timespec="seconds")

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------
    # INSERTS
    # ------------------------------------------------------------------
    def insert_lectura(self, payload: dict) -> int:
        """Guarda una lectura de telemetría recibida del dispositivo."""
        with self._lock:
            conn = self.connection
            cursor = conn.execute(
                """
                INSERT INTO lecturas
                  (device_id, ts_dispositivo, recibido_at, motion, lux,
                   light_state, armed, alarm, detail, last_cmd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("device", config.DEVICE_ID),
                    payload.get("ts"),
                    self.now_iso(),
                    int(payload.get("motion", 0)),
                    payload.get("lux"),
                    payload.get("light"),
                    int(payload.get("armed", 0)),
                    int(payload.get("alarm", 0)),
                    payload.get("detail"),
                    payload.get("last_cmd"),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def insert_evento(self, payload: dict) -> int:
        """Guarda un evento de seguridad recibido por MQTT."""
        with self._lock:
            conn = self.connection
            known = {"device", "ts", "type", "detail", "state",
                     "armed", "alarm", "source"}
            extra = {k: v for k, v in payload.items() if k not in known}
            cursor = conn.execute(
                """
                INSERT INTO eventos
                  (device_id, ts_dispositivo, recibido_at, tipo, detalle,
                   estado, fuente, extra)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("device", config.DEVICE_ID),
                    payload.get("ts"),
                    self.now_iso(),
                    payload.get("type", "DESCONOCIDO"),
                    payload.get("detail"),
                    payload.get("state"),
                    payload.get("source"),
                    json.dumps(extra, ensure_ascii=False) if extra else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def insert_comando(self, origen: str, comando: str,
                       estado: str = "RECIBIDO",
                       detalle: str = None) -> int:
        """Registra un comando enviado/recibido por cualquier canal."""
        with self._lock:
            conn = self.connection
            cursor = conn.execute(
                """
                INSERT INTO comandos
                  (device_id, recibido_at, origen, comando, estado, detalle)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    config.DEVICE_ID,
                    self.now_iso(),
                    origen,
                    comando.upper(),
                    estado,
                    detalle,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update_comando(self, command_id: int, estado: str,
                       detalle: str = None):
        """Actualiza el estado de aplicación de un comando."""
        with self._lock:
            conn = self.connection
            conn.execute(
                "UPDATE comandos SET estado = ?, detalle = ? WHERE id = ?",
                (estado, detalle, command_id),
            )
            conn.commit()

    def ultimo_comando_enviado(self, comando: str):
        """Devuelve el id del comando más reciente aún pendiente de ACK."""
        with self._lock:
            return self.connection.execute(
                """
                SELECT id FROM comandos
                WHERE comando = ? AND estado = 'ENVIADO'
                ORDER BY id DESC LIMIT 1
                """,
                (comando.upper(),),
            ).fetchone()

    # ------------------------------------------------------------------
    # CONSULTAS (históricos)
    # ------------------------------------------------------------------
    def ultimas_lecturas(self, limit: int = 20):
        """Últimas lecturas de sensores, de la más reciente a la vieja."""
        with self._lock:
            return self.connection.execute(
                "SELECT * FROM lecturas ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def eventos(self, limit: int = 20, tipo: str = None):
        """Últimos eventos, opcionalmente filtrados por tipo."""
        with self._lock:
            if tipo:
                return self.connection.execute(
                    "SELECT * FROM eventos WHERE tipo = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (tipo.upper(), limit),
                ).fetchall()
            return self.connection.execute(
                "SELECT * FROM eventos ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def comandos(self, limit: int = 20):
        """Últimos comandos registrados."""
        with self._lock:
            return self.connection.execute(
                "SELECT * FROM comandos ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def entre_fechas(self, desde: str, hasta: str, limite: int = 500):
        """Lecturas dentro de un rango de fechas (ISO-8601)."""
        with self._lock:
            return self.connection.execute(
                """
                SELECT * FROM lecturas
                WHERE recibido_at BETWEEN ? AND ?
                ORDER BY recibido_at DESC LIMIT ?
                """,
                (desde, hasta, limite),
            ).fetchall()

    def resumen(self) -> dict:
        """Estadísticas rápidas del sistema para el reporte."""
        with self._lock:
            conn = self.connection

            def scalar(sql, params=()):
                row = conn.execute(sql, params).fetchone()
                return row[0] if row and row[0] is not None else None

            return {
                "total_lecturas": scalar(
                    "SELECT COUNT(*) FROM lecturas"),
                "total_eventos": scalar(
                    "SELECT COUNT(*) FROM eventos"),
                "total_comandos": scalar(
                    "SELECT COUNT(*) FROM comandos"),
                "movimientos": scalar(
                    "SELECT COUNT(*) FROM eventos "
                    "WHERE tipo = 'MOTION_DETECTED'"),
                "alarmas": scalar(
                    "SELECT COUNT(*) FROM eventos WHERE tipo = 'ALARM_ON'"),
                "comandos_aceptados": scalar(
                    "SELECT COUNT(*) FROM comandos "
                    "WHERE estado = 'APLICADO'"),
                "lux_promedio": scalar(
                    "SELECT ROUND(AVG(lux), 1) FROM lecturas "
                    "WHERE lux IS NOT NULL"),
                "ultima_lectura": scalar(
                    "SELECT recibido_at FROM lecturas "
                    "ORDER BY id DESC LIMIT 1"),
                "ultimo_movimiento": scalar(
                    "SELECT recibido_at FROM eventos "
                    "WHERE tipo = 'MOTION_DETECTED' ORDER BY id DESC LIMIT 1"),
            }
