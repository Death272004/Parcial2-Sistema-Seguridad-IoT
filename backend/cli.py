"""
backend/cli.py
=====================================================================
Enviador manual de comandos al dispositivo (control remoto).

Uso (desde la raíz del proyecto):

    python -m backend.cli ARM            # arma el sistema
    python -m backend.cli DISARM         # desarma el sistema
    python -m backend.cli SILENCE        # silencia la alarma
    python -m backend.cli STATUS         # pide el estado actual
    python -m backend.cli PING           # comprueba conectividad
    python -m backend.cli --list         # comandos válidos

Cada comando queda registrado en la tabla `comandos` de SQLite.
=====================================================================
"""

import argparse
import sys

from backend import config
from backend.database import Database
from backend.mqtt_bridge import MqttBridge


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.cli",
        description="Envía comandos al sistema de seguridad por MQTT",
    )
    parser.add_argument("comando", nargs="?",
                        help="ARM | DISARM | SILENCE | STATUS | PING")
    parser.add_argument("--list", action="store_true",
                        help="muestra los comandos disponibles")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.list or not args.comando:
        print("Comandos disponibles:")
        for command in config.VALID_COMMANDS:
            print("  -", command)
        return 0

    command = args.comando.strip().upper()
    if command not in config.VALID_COMMANDS:
        print("Comando inválido:", command)
        print("Válidos:", ", ".join(config.VALID_COMMANDS))
        return 2

    db = Database()
    # client_id propio: nunca debe coincidir con el del backend,
    # de lo contrario el broker expulsaría la sesión del backend.
    bridge = MqttBridge(client_id=config.MQTT_CLIENT_ID + "-cli")

    if not bridge.connect():
        print("No se pudo conectar al broker MQTT.")
        return 1

    sent = bridge.publish_command(command, origen="cli")
    if sent:
        # Estado ENVIADO: el backend lo marcará como APLICADO cuando el
        # dispositivo responda con el evento COMMAND_RECEIVED.
        db.insert_comando(
            "cli", command, estado="ENVIADO",
            detalle="Publicado en {} (pendiente de confirmación)".format(
                config.TOPIC_COMMAND))
    else:
        db.insert_comando(
            "cli", command, estado="ERROR",
            detalle="No fue posible publicar en {}".format(
                config.TOPIC_COMMAND))

    bridge.stop()
    db.close()
    return 0 if sent else 1


if __name__ == "__main__":
    sys.exit(main())
