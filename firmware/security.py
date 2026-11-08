"""
security.py
=====================================================================
NÚCLEO DEL SISTEMA - Máquina de estados orientada a eventos.

    +------------+   ARM / botón    +-----------+
    | DESARMADO  | ----------------> |  ARMADO   |
    |            | <---------------- |           |
    +------------+   DISARM / botón  +-----------+
          |                                |
          |  movimiento (ignorado)         |  movimiento
          v                                v
     (sólo aviso)                    +-----------+
                                     |  ALARMA   |
                                     | LED+buzz  |
                                     +-----------+
                                         |  SILENCE / DISARM / timeout
                                         +-------> ARMADO o DESARMADO

Toda transición genera un EVENTO que se publica por MQTT y se guarda
en la base de datos del backend ( SQLite ).

Comandos aceptados (desde la nube o desde el botón local):
    ARM | ARMAR            -> activa la vigilancia
    DISARM | DESARMAR      -> desactiva la vigilancia
    SILENCE | SILENCIAR    -> silencia la alarma, mantiene armado
    STATUS | ESTADO        -> reporta el estado actual
    PING                   -> comprueba que el dispositivo responde
=====================================================================
"""

import time

import config
from sensors import LightSensor


class SecuritySystem:
    """Máquina de estados del sistema de seguridad.

    Parámetros
    ----------
    emit : callable(evento:dict) -> None
        Receptor de eventos generados por el sistema. En el firmware
        se conecta a la publicación MQTT; en pruebas puede ser un print.
    """

    def __init__(self, emit=None):
        self.state = config.STATE_DISARMED
        self.motion = False
        self.lux = 0.0
        self.light_state = "NORMAL"
        self.detail = "Sistema iniciado (desarmado)"
        self.mqtt_status = "-"
        self.last_command = "-"
        self.last_command_source = "-"

        self._emit = emit
        self._motion_latched = False
        self._alarm_started_ms = 0

    # ------------------------------------------------------------------
    # Emisión de eventos
    # ------------------------------------------------------------------
    def set_emitter(self, emit):
        """Conecta el receptor de eventos (inyección de dependencias)."""
        self._emit = emit

    def emit(self, event_type, detail, source="sistema", **extra):
        """Construye y despacha un evento de seguridad."""
        event = {
            "device": config.DEVICE_ID,
            "ts": self.now_epoch(),
            "type": event_type,
            "detail": detail,
            "state": self.state,
            "armed": 1 if self.state != config.STATE_DISARMED else 0,
            "alarm": 1 if self.state == config.STATE_ALARM else 0,
            "source": source,
        }
        event.update(extra)
        self.detail = detail
        if self._emit:
            try:
                self._emit(event)
            except Exception as error:        # pragma: no cover
                print("[seguridad] error emitiendo evento:", error)
        return event

    @staticmethod
    def now_epoch():
        """Timestamp del dispositivo (epoch en segundos)."""
        try:
            return int(time.time())
        except Exception:                    # pragma: no cover
            return 0

    # ------------------------------------------------------------------
    # Cambios de estado
    # ------------------------------------------------------------------
    def _enter_alarm(self, now_ms, reason):
        self.state = config.STATE_ALARM
        self._alarm_started_ms = now_ms
        self.emit("ALARM_ON", "ALARMA ACTIVADA: " + reason, source="pir")

    def arm(self, source="sistema"):
        if self.state == config.STATE_ARMED:
            self.emit("ALREADY_ARMED", "El sistema ya estaba armado", source=source)
            return False
        self.state = config.STATE_ARMED
        self.emit("ARMED", "Sistema ARMADO: vigilancia activa", source=source)
        return True

    def disarm(self, source="sistema"):
        if self.state == config.STATE_DISARMED:
            self.emit("ALREADY_DISARMED", "El sistema ya estaba desarmado",
                      source=source)
            return False
        self.state = config.STATE_DISARMED
        self.emit("DISARMED", "Sistema DESARMADO: vigilancia inactiva",
                  source=source)
        return True

    def silence(self, source="sistema"):
        """Silencia la alarma manteniendo el sistema armado."""
        if self.state != config.STATE_ALARM:
            self.emit("NO_ALARM", "No hay alarma activa que silenciar",
                      source=source)
            return False
        self.state = config.STATE_ARMED
        self.emit("ALARM_SILENCED",
                  "Alarma silenciada manualmente (sigue armado)",
                  source=source)
        return True

    def toggle(self, source="boton_local"):
        """Alterna armado/desarmado (botón físico o comando)."""
        if self.state == config.STATE_DISARMED:
            return self.arm(source)
        return self.disarm(source)

    # ------------------------------------------------------------------
    # Actualización con las lecturas de los sensores
    # ------------------------------------------------------------------
    def update(self, motion, lux, now_ms=None):
        """Procesa una lectura de sensores y dispara eventos si corresponde.

        `motion`   : bool  - estado actual del PIR
        `lux`      : float - iluminación calculada por el LDR
        `now_ms`   : int   - time.ticks_ms() para el timeout de alarma
        """
        if now_ms is None:
            now_ms = time.ticks_ms()

        rising = motion and not self._motion_latched
        self._motion_latched = motion
        self.motion = motion
        self.lux = lux
        self.light_state = LightSensor.classify(lux)

        # --- Detección de movimiento (flanco de subida) ---------------
        if rising:
            detail = "Movimiento detectado en la zona protegida"
            if self.light_state == "OSCURO":
                detail += " [entorno oscuro: posible intrusión nocturna]"
            self.emit("MOTION_DETECTED", detail, source="pir",
                      lux=lux, light=self.light_state)

            if self.state == config.STATE_ARMED:
                self._enter_alarm(now_ms, detail)
            elif self.state == config.STATE_DISARMED:
                self.emit("MOTION_IGNORED",
                          "Movimiento con sistema desarmado: no se activa alarma",
                          source="pir", lux=lux)

        # --- Timeout automático de la alarma -------------------------
        if self.state == config.STATE_ALARM:
            elapsed = time.ticks_diff(now_ms, self._alarm_started_ms)
            if elapsed >= config.ALARM_TIMEOUT_S * 1000:
                self.state = config.STATE_ARMED
                self.emit("ALARM_TIMEOUT",
                          "Alarma silenciada automáticamente tras {} s".format(
                              config.ALARM_TIMEOUT_S),
                          source="temporizador")

    # ------------------------------------------------------------------
    # Comandos recibidos desde la nube
    # ------------------------------------------------------------------
    @staticmethod
    def parse_command(raw):
        """Normaliza el comando recibido.

        Acepta texto plano (``ARM``) o JSON (``{"cmd": "ARM"}``).
        Devuelve el comando en mayúsculas o None si no se pudo leer.
        """
        if raw is None:
            return None
        text = raw.strip() if isinstance(raw, str) else str(raw)
        if not text:
            return None
        if text.startswith("{"):
            try:
                import json
                data = json.loads(text)
                text = str(data.get("cmd") or data.get("command") or "")
            except Exception:
                return None
        text = text.strip().upper()
        return text.split()[0] if text else None

    def handle_command(self, raw, source="mqtt"):
        """Ejecuta un comando entrante y emite el evento correspondiente."""
        command = self.parse_command(raw)
        self.last_command = command or "INVALIDO"
        self.last_command_source = source

        if command is None:
            self.emit("COMMAND_INVALID", "Comando ilegible: {!r}".format(raw),
                      source=source)
            return False

        self.emit("COMMAND_RECEIVED", "Comando recibido: " + command,
                  source=source, command=command)

        if command in ("ARM", "ARMAR"):
            return self.arm(source)
        if command in ("DISARM", "DESARMAR"):
            return self.disarm(source)
        if command in ("SILENCE", "SILENCIAR", "SILENCIO"):
            return self.silence(source)
        if command in ("STATUS", "ESTADO"):
            self.emit("STATUS",
                      "Estado reportado: {}".format(self.state),
                      source=source)
            return True
        if command == "PING":
            self.emit("PONG", "Dispositivo en línea y respondiendo",
                      source=source)
            return True

        self.emit("COMMAND_UNKNOWN",
                  "Comando no reconocido: {}".format(command),
                  source=source)
        return False

    # ------------------------------------------------------------------
    # Snapshot (foto del estado para telemetría / display)
    # ------------------------------------------------------------------
    def snapshot(self):
        """Devuelve el estado actual como dict listo para publicar."""
        return {
            "device": config.DEVICE_ID,
            "ts": self.now_epoch(),
            "state": self.state,
            "armed": 1 if self.state != config.STATE_DISARMED else 0,
            "alarm": 1 if self.state == config.STATE_ALARM else 0,
            "motion": 1 if self.motion else 0,
            "lux": self.lux,
            "light": self.light_state,
            "detail": self.detail,
            "mqtt": self.mqtt_status,
            "last_cmd": self.last_command,
        }
