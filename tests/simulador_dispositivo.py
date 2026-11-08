"""
tests/simulador_dispositivo.py
=====================================================================
SIMULADOR DEL DISPOSITIVO (lado Python) - Sistema de Seguridad IoT.

Permite probar TODO el backend sin abrir Wokwi: reproduce el
comportamiento del ESP32 (publica telemetría y eventos, y recibe
comandos por MQTT), de modo que se puede validar la cadena

        simulador -> broker -> backend -> SQLite

antes de pasar al firmware real en el simulador de hardware.

Uso (desde la raíz del proyecto):

    python -m tests.simulador_dispositivo              # modo demo
    python -m tests.simulador_dispositivo --segundos 60
    python -m tests.simulador_dispositivo --movimiento  # fuerza una intrusión
=====================================================================
"""

import argparse
import json
import random
import sys
import time

import paho.mqtt.client as mqtt

from backend import config


class SimulatedDevice:
    """Emula al ESP32: mismos tópicos y mismo formato de mensajes."""

    def __init__(self, motion=False):
        self.state = "DESARMADO"
        self.motion = motion
        self.lux = random.uniform(80, 450)
        self.alarm = False
        self.commands = []
        self.client = mqtt.Client(
            client_id="seguridad-simulador-001")

    # ------------------------------------------------------------------
    def on_connect(self, client, userdata, flags, *args):
        client.subscribe(config.TOPIC_COMMAND)
        print("[sim] conectado y suscrito a", config.TOPIC_COMMAND)
        self.publish_event({
            "device": config.DEVICE_ID,
            "ts": int(time.time()),
            "type": "SYSTEM_START",
            "detail": "Simulador del dispositivo iniciado",
            "state": self.state,
            "armed": 0,
            "alarm": 0,
            "source": "simulador",
        })

    def on_message(self, client, userdata, msg):
        payload = json.loads(msg.payload.decode())
        command = str(payload.get("cmd", "")).upper()
        self.commands.append(command)
        print("[sim] COMANDO RECIBIDO ->", command)

        if command == "ARM":
            self.state = "ARMADO"
            detail = "Sistema ARMADO: vigilancia activa"
        elif command == "DISARM":
            self.state = "DESARMADO"
            detail = "Sistema DESARMADO: vigilancia inactiva"
        elif command == "SILENCE" and self.alarm:
            self.state, self.alarm = "ARMADO", False
            detail = "Alarma silenciada manualmente (sigue armado)"
        elif command == "STATUS":
            detail = "Estado reportado: {}".format(self.state)
        elif command == "PING":
            detail = "Dispositivo en línea y respondiendo"
        else:
            detail = "Comando no reconocido: {}".format(command)

        self.publish_event({
            "device": config.DEVICE_ID,
            "ts": int(time.time()),
            "type": "COMMAND_RECEIVED",
            "detail": detail,
            "state": self.state,
            "armed": 1 if self.state != "DESARMADO" else 0,
            "alarm": 1 if self.alarm else 0,
            "source": "mqtt",
            "command": command,
        })

    # ------------------------------------------------------------------
    def publish_event(self, event):
        self.client.publish(config.TOPIC_EVENT, json.dumps(event))

    def publish_telemetry(self):
        payload = {
            "device": config.DEVICE_ID,
            "ts": int(time.time()),
            "state": self.state,
            "armed": 1 if self.state != "DESARMADO" else 0,
            "alarm": 1 if self.alarm else 0,
            "motion": 1 if self.motion else 0,
            "lux": round(self.lux, 1),
            "light": ("OSCURO" if self.lux < 30 else
                      "NORMAL" if self.lux < 500 else "CLARO"),
            "detail": "simulación de lectura",
            "mqtt": "OK",
            "last_cmd": self.commands[-1] if self.commands else "-",
        }
        self.client.publish(config.TOPIC_TELEMETRY, json.dumps(payload))
        return payload

    # ------------------------------------------------------------------
    def run(self, seconds=30, force_motion=False, motion_at=12):
        print("=" * 62)
        print(" SIMULADOR DEL DISPOSITIVO ({} s)".format(seconds))
        print(" telemetry:", config.TOPIC_TELEMETRY)
        print(" event    :", config.TOPIC_EVENT)
        print(" command  :", config.TOPIC_COMMAND)
        print("=" * 62)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(config.MQTT_HOST, config.MQTT_PORT, 60)
        self.client.loop_start()

        start = time.time()
        last_sample = 0.0
        try:
            while time.time() - start < seconds:
                now = time.time()
                if now - last_sample >= 2:
                    last_sample = now
                    self.lux = max(0.0, self.lux + random.uniform(-25, 25))

                    # Si se pidió movimiento, lo presenta a los N segundos
                    if force_motion and now - start >= motion_at \
                            and not self.motion:
                        self.motion = True
                        if self.state == "ARMADO":
                            self.state = "ALARMA"
                            self.alarm = True
                        self.publish_event({
                            "device": config.DEVICE_ID,
                            "ts": int(now),
                            "type": "MOTION_DETECTED",
                            "detail": "Movimiento detectado en la zona "
                                      "protegida (simulado)",
                            "state": self.state,
                            "armed": 1 if self.state != "DESARMADO" else 0,
                            "alarm": 1 if self.alarm else 0,
                            "source": "pir",
                            "lux": round(self.lux, 1),
                        })
                        if self.alarm:
                            self.publish_event({
                                "device": config.DEVICE_ID,
                                "ts": int(now),
                                "type": "ALARM_ON",
                                "detail": "ALARMA ACTIVADA: intrusión simulada",
                                "state": self.state,
                                "armed": 1,
                                "alarm": 1,
                                "source": "pir",
                            })

                    payload = self.publish_telemetry()
                    print("[sim] telemetría ->", payload["state"],
                          "| motion:", payload["motion"],
                          "| lux:", payload["lux"])

                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\n[sim] detenido")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
        print("[sim] finalizado. Comandos recibidos:", self.commands)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m tests.simulador_dispositivo",
        description="Emula el ESP32 para probar el backend sin Wokwi")
    parser.add_argument("--segundos", type=int, default=30)
    parser.add_argument("--movimiento", action="store_true",
                        help="genera una intrusión a los 12 segundos")
    parser.add_argument("--movimiento-en", type=int, default=12,
                        help="segundos transcurridos antes de la intrusión")
    args = parser.parse_args(argv)

    SimulatedDevice().run(seconds=args.segundos,
                          force_motion=args.movimiento,
                          motion_at=args.movimiento_en)
    return 0


if __name__ == "__main__":
    sys.exit(main())
