"""
backend/thingspeak.py
=====================================================================
Integración con ThingSpeak (plataforma en la nube del proyecto).

Funciones:
  * update(snapshot)      -> envía los campos del canal (dashboard)
  * next_command()        -> toma el siguiente comando de TalkBack
  * add_command(texto)    -> encola un comando desde la nube
  * list_commands()       -> lista los comandos pendientes

ThingSpeak TalkBack es el mecanismo oficial de la plataforma para
enviar comandos "desde la nube hacia el dispositivo": el usuario
crea el comando en la interfaz web de ThingSpeak, el backend lo
recibe por REST y lo reenvía al ESP32 por MQTT.
=====================================================================
"""

import requests

from backend import config


class ThingSpeakClient:
    """Cliente REST de ThingSpeak + TalkBack."""

    def __init__(self, write_key=None, channel_id=None,
                 talkback_id=None, talkback_key=None, api=None):
        self.write_key = write_key or config.THINGSPEAK_WRITE_KEY
        self.channel_id = channel_id or config.THINGSPEAK_CHANNEL_ID
        self.talkback_id = talkback_id or config.THINGSPEAK_TALKBACK_ID
        self.talkback_key = talkback_key or config.THINGSPEAK_TALKBACK_KEY
        self.api = (api or config.THINGSPEAK_API).rstrip("/")
        self.timeout = 10

    # ------------------------------------------------------------------
    # Estado de la integración
    # ------------------------------------------------------------------
    @property
    def dashboard_enabled(self) -> bool:
        """True si hay Write API Key configurada."""
        return bool(self.write_key)

    @property
    def talkback_enabled(self) -> bool:
        """True si TalkBack está configurado (comandos desde la nube)."""
        return bool(self.talkback_id and self.talkback_key)

    # ------------------------------------------------------------------
    # 1. Dashboard en tiempo real
    # ------------------------------------------------------------------
    def update(self, snapshot: dict) -> bool:
        """Publica la última lectura en los campos del canal.

        Mapeo de campos:
            field1 -> motion   field3 -> armed
            field2 -> lux      field4 -> alarm
        """
        if not self.dashboard_enabled:
            return False

        fields = {
            config.FIELD_MAP["motion"]: int(snapshot.get("motion", 0)),
            config.FIELD_MAP["lux"]: float(snapshot.get("lux") or 0),
            config.FIELD_MAP["armed"]: int(snapshot.get("armed", 0)),
            config.FIELD_MAP["alarm"]: int(snapshot.get("alarm", 0)),
        }
        payload = {"api_key": self.write_key, **fields}
        # "status" es el campo de texto del canal (máx. 255 caracteres)
        payload["status"] = "{} | {}".format(
            snapshot.get("state", ""), str(snapshot.get("detail", ""))[:100])

        try:
            response = requests.post(self.api + "/update", data=payload,
                                     timeout=self.timeout)
            if response.status_code == 200 and response.text.strip():
                print("[thingspeak] entrada publicada (entry_id={})".format(
                    response.text.strip()))
                return True
            print("[thingspeak] respuesta inesperada -> HTTP {} {}".format(
                response.status_code, response.text[:120]))
        except requests.RequestException as error:
            print("[thingspeak] ERROR de red:", error)
        return False

    # ------------------------------------------------------------------
    # 2. Comandos desde la nube (TalkBack)
    # ------------------------------------------------------------------
    def _talkback_url(self, suffix: str) -> str:
        return "{}/talkbacks/{}/{}".format(self.api, self.talkback_id, suffix)

    def next_command(self):
        """Devuelve y retira el siguiente comando de la cola TalkBack.

        Endpoint oficial:
            POST /talkbacks/<id>/commands/execute.json?api_key=<key>

        Devuelve dict {"id": int, "command": str} o None si la cola
        está vacía.
        """
        if not self.talkback_enabled:
            return None
        try:
            response = requests.post(
                self._talkback_url("commands/execute.json"),
                data={"api_key": self.talkback_key},
                timeout=self.timeout,
            )
            if response.status_code != 200:
                print("[thingspeak] TalkBack HTTP {}".format(
                    response.status_code))
                return None
            text = response.text.strip()
            if not text or text == "{}":
                return None                    # cola vacía
            data = response.json()
            command = data.get("command_string")
            if not command:
                return None
            return {"id": data.get("id"), "command": command}
        except requests.RequestException as error:
            print("[thingspeak] ERROR TalkBack:", error)
            return None

    def add_command(self, command_string: str):
        """Encola un comando en TalkBack (útil desde scripts/CI)."""
        if not self.talkback_enabled:
            return False
        try:
            response = requests.post(
                self._talkback_url("commands.json"),
                data={"api_key": self.talkback_key,
                      "command_string": command_string},
                timeout=self.timeout,
            )
            return response.status_code == 200
        except requests.RequestException as error:
            print("[thingspeak] ERROR agregando comando:", error)
            return False

    def list_commands(self):
        """Lista los comandos pendientes en la cola TalkBack."""
        if not self.talkback_enabled:
            return []
        try:
            response = requests.get(
                self._talkback_url("commands.json"),
                params={"api_key": self.talkback_key},
                timeout=self.timeout,
            )
            if response.status_code == 200 and response.text.strip():
                return response.json()
        except requests.RequestException as error:
            print("[thingspeak] ERROR listando comandos:", error)
        return []
