"""
backend/mqtt_bridge.py
=====================================================================
Puente MQTT del backend.

Se suscribe a los tópicos de telemetría y eventos del dispositivo y
expone un método para enviarle comandos (control remoto bidireccional).

Compatible con paho-mqtt 1.x y 2.x (la API de callbacks cambió en la
versión 2.0; el código detecta automáticamente la versión instalada).
=====================================================================
"""

import json
import time

import paho.mqtt.client as mqtt

from backend import config


class MqttBridge:
    """Cliente MQTT del lado servidor (backend).

    Parámetros
    ----------
    on_telemetry : callable(dict) -> None
        Recibe cada payload de `seguridad/<device>/telemetry`.
    on_event : callable(dict) -> None
        Recibe cada payload de `seguridad/<device>/event`.
    client_id : str, opcional
        Identificador MQTT. Cada proceso debe usar uno DISTINTO:
        si dos clientes se conectan con el mismo ID, el broker
        expulsa la sesión anterior (y se pierden mensajes).
    """

    def __init__(self, on_telemetry=None, on_event=None, client_id=None):
        self.on_telemetry = on_telemetry
        self.on_event = on_event
        self.connected = False
        self.client_id = client_id or config.MQTT_CLIENT_ID
        self.client = self._build_client()

    # ------------------------------------------------------------------
    # Construcción y ciclo de vida
    # ------------------------------------------------------------------
    def _build_client(self) -> mqtt.Client:
        """Crea el cliente compatible con paho-mqtt 1.x / 2.x."""
        try:                                        # paho-mqtt >= 2.0
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.client_id,
            )
        except AttributeError:                      # paho-mqtt 1.x
            client = mqtt.Client(client_id=self.client_id)

        if config.MQTT_USER:
            client.username_pw_set(config.MQTT_USER, config.MQTT_PASSWORD)

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        return client

    def connect(self) -> bool:
        """Conecta al broker y arranca el loop de red en segundo plano."""
        try:
            self.client.connect(config.MQTT_HOST, config.MQTT_PORT,
                                keepalive=60)
            self.client.loop_start()
            # Espera breve a que on_connect marque la sesión como activa
            for _ in range(30):
                if self.connected:
                    break
                time.sleep(0.1)
            return self.connected
        except Exception as error:
            print("[mqtt] ERROR conectando a {}:{} -> {}".format(
                config.MQTT_HOST, config.MQTT_PORT, error))
            return False

    def stop(self):
        """Detiene el loop y cierra la conexión de forma ordenada."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
        self.connected = False

    # ------------------------------------------------------------------
    # Callbacks de paho-mqtt (firma compatible 1.x y 2.x)
    # ------------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, *args):
        reason = args[0] if args else 0
        if str(reason) not in ("0", "Success"):
            print("[mqtt] conexión rechazada:", reason)
            return
        self.connected = True
        client.subscribe(config.TOPIC_TELEMETRY, qos=0)
        client.subscribe(config.TOPIC_EVENT, qos=0)
        print("[mqtt] conectado a {}:{} y suscrito a:".format(
            config.MQTT_HOST, config.MQTT_PORT))
        print("        -", config.TOPIC_TELEMETRY)
        print("        -", config.TOPIC_EVENT)

    def _on_disconnect(self, client, userdata, *args):
        self.connected = False
        print("[mqtt] sesión desconectada del broker")

    def _on_message(self, client, userdata, msg):
        """Deserializa el JSON y lo despacha al manejador correspondiente."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            print("[mqtt] payload no JSON en", msg.topic)
            return

        if msg.topic == config.TOPIC_TELEMETRY:
            if self.on_telemetry:
                self.on_telemetry(payload)
        elif msg.topic == config.TOPIC_EVENT:
            if self.on_event:
                self.on_event(payload)

    # ------------------------------------------------------------------
    # Publicación de comandos (nube -> dispositivo)
    # ------------------------------------------------------------------
    def publish_command(self, command: str, origen: str = "backend") -> bool:
        """Envía un comando al dispositivo (ARM, DISARM, SILENCE...).

        El payload se envía como JSON para que el dispositivo pueda
        interpretarlo con su parser tolerante (acepta texto plano también).
        """
        body = json.dumps({"cmd": command.upper(),
                           "origin": origen,
                           "ts": int(time.time())})
        try:
            info = self.client.publish(config.TOPIC_COMMAND, body, qos=1)
            info.wait_for_publish(timeout=5)
            print("[mqtt] comando enviado -> {} ({}".format(
                command.upper(), config.TOPIC_COMMAND) + ")")
            return True
        except Exception as error:
            print("[mqtt] ERROR publicando comando:", error)
            return False
