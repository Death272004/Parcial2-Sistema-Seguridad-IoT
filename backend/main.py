"""
backend/main.py
=====================================================================
ORQUESTADOR DEL BACKEND - Sistema de Seguridad IoT (Parcial #2 - DS8)

Se encarga de todo lo que ocurre fuera del dispositivo:

    MQTT  <->  SQLite  <->  ThingSpeak

    1. Se suscribe a la telemetría y a los eventos del ESP32.
    2. Almacena cada lectura y evento en SQLite (con timestamp).
    3. Reenvía la telemetría a ThingSpeak cada 15 s (dashboard).
    4. Consulta ThingSpeak TalkBack y reenvía los comandos que el
       usuario crea en la nube hacia el dispositivo por MQTT.
    5. Registra la trazabilidad de cada comando (enviado -> aplicado).

Ejecutar desde la raíz del proyecto:

    python -m backend.main
=====================================================================
"""

import time

from backend import config
from backend.database import Database
from backend.mqtt_bridge import MqttBridge
from backend.thingspeak import ThingSpeakClient


class Backend:
    """Aplicación de integración entre MQTT, SQLite y ThingSpeak."""

    def __init__(self):
        self.db = Database()
        self.bridge = MqttBridge(on_telemetry=self._on_telemetry,
                                 on_event=self._on_event)
        self.thingspeak = ThingSpeakClient()

        self._lock_state = {"latest": None, "pending_command_id": None}
        self._last_thingspeak = 0.0
        self._last_talkback = 0.0

    # ------------------------------------------------------------------
    # Handlers MQTT
    # ------------------------------------------------------------------
    def _on_telemetry(self, payload: dict):
        """Guarda cada lectura de sensores en SQLite y la deja en RAM."""
        try:
            self.db.insert_lectura(payload)
        except Exception as error:
            print("[db] error guardando lectura:", error)

        self._lock_state["latest"] = payload
        print("[telemetría] {device} | estado={state} movimiento={motion} "
              "luz={lux} lx | alarma={alarm}".format(
                  device=payload.get("device"),
                  state=payload.get("state"),
                  motion=payload.get("motion"),
                  lux=payload.get("lux"),
                  alarm=payload.get("alarm")))

    def _on_event(self, payload: dict):
        """Guarda el evento y actualiza el estado del comando pendiente."""
        try:
            self.db.insert_evento(payload)
        except Exception as error:
            print("[db] error guardando evento:", error)

        event_type = payload.get("type", "")
        print("[evento] {:<20} | {}".format(event_type,
                                            payload.get("detail", "")))

        # Trazabilidad: el dispositivo confirma la recepción del comando.
        # Se busca primero el comando pendiente enviado por este proceso
        # (TalkBack) y, si no, el último enviado por cualquier canal (CLI).
        pending = self._lock_state["pending_command_id"]
        if event_type == "COMMAND_RECEIVED":
            if not pending:
                row = self.db.ultimo_comando_enviado(
                    str(payload.get("command", "")))
                pending = row["id"] if row else None
            if pending:
                self.db.update_comando(pending, "APLICADO",
                                       payload.get("detail"))
                self._lock_state["pending_command_id"] = None
        elif event_type in ("COMMAND_UNKNOWN", "COMMAND_INVALID") and pending:
            self.db.update_comando(pending, "RECHAZADO",
                                   payload.get("detail"))
            self._lock_state["pending_command_id"] = None

    # ------------------------------------------------------------------
    # Temporizadores (dashboard y TalkBack)
    # ------------------------------------------------------------------
    def _sync_thingspeak(self, snapshot: dict, now: float):
        """Envía la telemetría a ThingSpeak respetando el plan gratuito."""
        if not self.thingspeak.dashboard_enabled:
            return
        if now - self._last_thingspeak < config.THINGSPEAK_INTERVAL_S:
            return
        if self.thingspeak.update(snapshot):
            self._last_thingspeak = now

    def _poll_talkback(self, now: float):
        """Toma de la nube el siguiente comando y lo reenvía por MQTT."""
        if not self.thingspeak.talkback_enabled:
            return
        if now - self._last_talkback < config.TALKBACK_POLL_S:
            return
        self._last_talkback = now

        pending = self.thingspeak.next_command()
        if not pending:
            return

        command = str(pending.get("command", "")).strip()
        print("[thingspeak] comando recibido desde la nube:", command)

        if command.upper() not in config.VALID_COMMANDS:
            self.db.insert_comando(
                "thingspeak", command or "VACIO", estado="RECHAZADO",
                detalle="Comando no soportado por el dispositivo")
            print("[thingspeak] RECHAZADO (válido: {})".format(
                ", ".join(config.VALID_COMMANDS)))
            return

        ok = self.bridge.publish_command(command, origen="thingspeak")
        command_id = self.db.insert_comando(
            "thingspeak", command,
            estado="ENVIADO" if ok else "ERROR",
            detalle="Origen: ThingSpeak TalkBack #{}".format(
                self.thingspeak.talkback_id))
        if ok:
            self._lock_state["pending_command_id"] = command_id

    # ------------------------------------------------------------------
    # Ciclo principal
    # ------------------------------------------------------------------
    def run(self):
        print("=" * 62)
        print(" BACKEND - Sistema de Seguridad IoT")
        print(" MQTT  {}:{} | SQLite {}".format(
            config.MQTT_HOST, config.MQTT_PORT, config.DB_PATH))
        print(" ThingSpeak dashboard: {}".format(
            "HABILITADO" if self.thingspeak.dashboard_enabled
            else "deshabilitado (falta THINGSPEAK_WRITE_KEY)"))
        print(" ThingSpeak TalkBack : {}".format(
            "HABILITADO" if self.thingspeak.talkback_enabled
            else "deshabilitado (faltan claves de TalkBack)"))
        print("=" * 62)

        self.db.insert_comando("sistema", "START", estado="APLICADO",
                               detalle="Backend iniciado")

        if not self.bridge.connect():
            print("No fue posible conectar al broker MQTT. Revisa tu red.")
            return 1

        self._last_thingspeak = time.time()
        self._last_talkback = time.time()

        try:
            while True:
                now = time.time()
                snapshot = self._lock_state.get("latest")

                if snapshot:
                    self._sync_thingspeak(snapshot, now)
                self._poll_talkback(now)

                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[backend] detenido por el usuario")
        finally:
            self.bridge.stop()
            self.db.insert_comando("sistema", "STOP", estado="APLICADO",
                                   detalle="Backend detenido")
            self.db.close()
            print("[backend] sesión finalizada de forma ordenada")
        return 0


def main():
    return Backend().run()


if __name__ == "__main__":
    raise SystemExit(main())
