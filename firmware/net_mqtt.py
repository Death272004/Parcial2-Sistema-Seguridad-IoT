"""
net_mqtt.py
=====================================================================
Capa de COMUNICACIONES: WiFi + cliente MQTT (umqtt.simple).

  * connect_wifi()   -> asocia el ESP32 a la red con tiempo de espera
  * MqttService      -> cliente MQTT con:
                          - publicación de telemetry/event
                          - suscripción al tópico de comandos
                          - cola de comandos (no bloqueante)
                          - reconexión con reintento

El diseño es no bloqueante: `check_messages()` usa `check_msg()`
(retorna inmediatamente si no hay mensajes pendientes), de modo que
el bucle principal nunca se congela esperando la red.
=====================================================================
"""

import time
import network
import json

from umqtt.simple import MQTTClient

import config


def connect_wifi(ssid=config.WIFI_SSID,
                 password=config.WIFI_PASSWORD,
                 timeout_ms=config.WIFI_TIMEOUT_MS):
    """Asocia la interfaz WiFi en modo estación.

    Devuelve True si logró obtener dirección IP, False si expiró.
    """
    print("[wifi] conectando a '{}'...".format(ssid))
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        wlan.connect(ssid, password)
        start = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                print("[wifi] ERROR: sin respuesta de la red")
                return False
            time.sleep_ms(200)

    ip, mask, gateway, dns = wlan.ifconfig()
    print("[wifi] conectado -> IP: {} | Gateway: {}".format(ip, gateway))
    return True


def sync_time():
    """Sincroniza el reloj del ESP32 con un servidor NTP.

    Permite que `time.time()` devuelva un timestamp real (epoch),
    lo que se refleja en los eventos almacenados en la base de datos.
    Devuelve True si se logró sincronizar.
    """
    if not config.NTP_ENABLED:
        return False
    try:
        import ntptime
        ntptime.host = config.NTP_HOST
        ntptime.settime()
        print("[ntp] hora sincronizada:", time.localtime()[:6])
        return True
    except Exception as error:
        print("[ntp] no se pudo sincronizar (se usa el tiempo de arranque):",
              error)
        return False


class MqttService:
    """Cliente MQTT orientado a eventos para el sistema de seguridad.

    Parámetros
    ----------
    on_message : callable(topic:str, payload:str)
        Se invoca desde el bucle de red con cada mensaje entrante.
        Debe devolver el resultado rápidamente: la cola interna
        almacena los mensajes y luego se procesan en el bucle.
    """

    def __init__(self, on_message=None):
        self._client = None
        self._on_message = on_message
        self._command_queue = []
        self.connected = False
        self._last_reconnect = 0

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def connect(self, broker=config.MQTT_BROKER, port=config.MQTT_PORT):
        """Establece la conexión y se suscribe al tópico de comandos."""
        try:
            client = MQTTClient(
                client_id=config.MQTT_CLIENT_ID,
                server=broker,
                port=port,
                user=config.MQTT_USER or None,
                password=config.MQTT_PASSWORD or None,
                keepalive=config.MQTT_KEEPALIVE,
            )
            client.set_callback(self._handle_message)
            client.connect()
            client.subscribe(config.TOPIC_COMMAND)
            self._client = client
            self.connected = True
            print("[mqtt] conectado a {}:{}".format(broker, port))
            print("[mqtt] suscrito a", config.TOPIC_COMMAND)
            return True
        except Exception as error:
            print("[mqtt] ERROR al conectar:", error)
            self.connected = False
            self._client = None
            return False

    def _handle_message(self, topic, payload):
        """Callback de llegada de mensaje (se ejecuta en la red)."""
        try:
            topic = topic.decode() if isinstance(topic, bytes) else topic
            payload = payload.decode() if isinstance(payload, bytes) else payload
        except Exception:
            return
        if topic != config.TOPIC_COMMAND:
            return
        # Encola: la lógica de negocio se resuelve en el bucle principal
        self._command_queue.append(payload)
        if self._on_message:
            try:
                self._on_message(topic, payload)
            except Exception as error:
                print("[mqtt] error en callback:", error)

    def check_messages(self):
        """Procesa mensajes entrantes sin bloquear el bucle."""
        if not self.connected or self._client is None:
            return
        try:
            self._client.check_msg()
        except Exception as error:
            print("[mqtt] error recibiendo:", error)
            self.connected = False

    def drain_commands(self):
        """Devuelve y vacía la cola de comandos pendientes."""
        pending = self._command_queue[:]
        self._command_queue = []
        return pending

    def ensure_connected(self, broker=config.MQTT_BROKER, port=config.MQTT_PORT):
        """Reconecta automáticamente si la sesión se cayó (backoff 5 s)."""
        if self.connected:
            return True
        now = time.ticks_ms()
        if self._last_reconnect and \
           time.ticks_diff(now, self._last_reconnect) < 5000:
            return False
        self._last_reconnect = now
        print("[mqtt] intentando reconectar...")
        return self.connect(broker, port)

    # ------------------------------------------------------------------
    # Publicación
    # ------------------------------------------------------------------
    def publish(self, topic, payload, retain=False):
        """Publica un dict como JSON en el tópico indicado."""
        if not self.connected or self._client is None:
            print("[mqtt] sin conexión, se omite publicar en", topic)
            return False
        try:
            body = payload if isinstance(payload, str) else json.dumps(payload)
            self._client.publish(topic, body.encode(), retain=retain)
            return True
        except Exception as error:
            print("[mqtt] ERROR publicando:", error)
            self.connected = False
            return False

    def publish_telemetry(self, snapshot):
        """Publica la lectura de sensores en el tópico de telemetría."""
        return self.publish(config.TOPIC_TELEMETRY, snapshot)

    def publish_event(self, event):
        """Publica un evento de seguridad en el tópico de eventos."""
        return self.publish(config.TOPIC_EVENT, event)

    def disconnect(self):
        """Cierra la sesión MQTT de forma ordenada."""
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
        self.connected = False
