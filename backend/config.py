"""
backend/config.py
=====================================================================
Configuración del backend (Python 3) del Sistema de Seguridad.

Todos los valores pueden sobreescribirse con variables de entorno,
de modo que las claves reales (ThingSpeak) NUNCA se versionan.

    export THINGSPEAK_WRITE_KEY="XXXXXXXXXXXXXXXX"
    python -m backend.main

Valores por defecto pensados para funcionar "out of the box" con el
broker público de HiveMQ y una base de datos SQLite local.
=====================================================================
"""

import os
from pathlib import Path

# ----------------------------------------------------------------------
# Rutas del proyecto
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SQL_DIR = BASE_DIR / "sql"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------
# Dispositivo / tópicos MQTT (deben coincidir con firmware/config.py)
# ----------------------------------------------------------------------
DEVICE_ID = os.environ.get("DEVICE_ID", "casa-01")
TOPIC_TELEMETRY = "seguridad/{}/telemetry".format(DEVICE_ID)
TOPIC_EVENT = "seguridad/{}/event".format(DEVICE_ID)
TOPIC_COMMAND = "seguridad/{}/command".format(DEVICE_ID)

# ----------------------------------------------------------------------
# Broker MQTT
# ----------------------------------------------------------------------
MQTT_HOST = os.environ.get("MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", "seguridad-backend-001")
MQTT_USER = os.environ.get("MQTT_USER", "")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")

# ----------------------------------------------------------------------
# Base de datos SQLite
# ----------------------------------------------------------------------
DB_PATH = Path(os.environ.get(
    "SECURITY_DB", str(DATA_DIR / "seguridad.db")))

# ----------------------------------------------------------------------
# ThingSpeak (plataforma en la nube)
#   CHANNEL_ID   : "Channel ID" (pestaña Channel Settings)
#   WRITE_KEY    : "Write API Key"  -> el backend escribe el canal
#   READ_KEY     : "Read API Key"   -> lectura de campos
#   TALKBACK_*   :TalkBack (opcional) -> comandos desde la nube
# ----------------------------------------------------------------------
THINGSPEAK_CHANNEL_ID = os.environ.get("THINGSPEAK_CHANNEL_ID", "")
THINGSPEAK_WRITE_KEY = os.environ.get("THINGSPEAK_WRITE_KEY", "")
THINGSPEAK_READ_KEY = os.environ.get("THINGSPEAK_READ_KEY", "")
THINGSPEAK_TALKBACK_ID = os.environ.get("THINGSPEAK_TALKBACK_ID", "")
THINGSPEAK_TALKBACK_KEY = os.environ.get("THINGSPEAK_TALKBACK_KEY", "")
THINGSPEAK_API = os.environ.get("THINGSPEAK_API", "https://api.thingspeak.com")

# ThingSpeak free plan permite un update cada 15 segundos
THINGSPEAK_INTERVAL_S = int(os.environ.get("THINGSPEAK_INTERVAL_S", "15"))
TALKBACK_POLL_S = int(os.environ.get("TALKBACK_POLL_S", "10"))

# Mapeo de campos del canal ThingSpeak
FIELD_MAP = {
    "motion": "field1",   # movimiento detectado (0/1)
    "lux": "field2",      # iluminación ambiental (lux)
    "armed": "field3",    # sistema armado (0/1)
    "alarm": "field4",    # alarma activa (0/1)
}

# ----------------------------------------------------------------------
# Comandos soportados por el dispositivo
# ----------------------------------------------------------------------
VALID_COMMANDS = ("ARM", "DISARM", "SILENCE", "STATUS", "PING")
