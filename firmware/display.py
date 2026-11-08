"""
display.py
=====================================================================
Capa de PRESENTACIÓN - Display OLED SSD1306 128x64 (I2C).

Muestra en tiempo real el estado del sistema de seguridad:
estado, detección de movimiento, nivel de luz y alarma.

Diseño defensivo: si la biblioteca `micropython-ssd1306` no está
instalada o el display no responde en el bus I2C, el módulo sigue
funcionando sin display (se desactiva a sí mismo) y el resto del
sistema no se ve afectado.
=====================================================================
"""

import config

try:
    from ssd1306 import SSD1306_I2C
except ImportError:          # biblioteca no agregada en Wokwi
    SSD1306_I2C = None

try:
    from machine import I2C, Pin
except ImportError:          # entorno de pruebas sin MicroPython
    I2C = None


class OledDisplay:
    """Envuelve el OLED SSD1306 y ofrece un método `render(snapshot)`."""

    def __init__(self,
                 sda=config.I2C_SDA,
                 scl=config.I2C_SCL,
                 width=config.OLED_WIDTH,
                 height=config.OLED_HEIGHT):
        self.available = False
        self._oled = None
        self._width = width
        self._height = height

        if I2C is None or SSD1306_I2C is None:
            print("[display] biblioteca ssd1306 no disponible -> sin OLED")
            return

        try:
            i2c = I2C(0, sda=Pin(sda), scl=Pin(scl), freq=config.I2C_FREQ)
            found = i2c.scan()
            if not found:
                print("[display] no se detectó ningún dispositivo I2C")
                return
            self._oled = SSD1306_I2C(width, height, i2c)
            self.available = True
            print("[display] OLED SSD1306 listo en 0x{:02X}".format(found[0]))
        except Exception as error:                # pragma: no cover
            print("[display] error inicializando OLED:", error)

    def _line(self, text, row, col=0):
        """Escribe una línea recortada al ancho del display."""
        if not self.available:
            return
        # 128 px / 8 px por caracter = 16 caracteres por línea
        max_chars = self._width // 8
        self._oled.text(str(text)[:max_chars], col, row * 8)

    def render(self, snapshot):
        """Dibuja la pantalla de estado a partir del snapshot del sistema.

        `snapshot` es un dict devuelto por SecuritySystem.snapshot().
        """
        if not self.available:
            return
        try:
            oled = self._oled
            oled.fill(0)

            self._line("SEGURIDAD IoT", 0)
            oled.hline(0, 9, self._width, 1)

            estado = snapshot.get("state", "?")
            self._line("Estado: {}".format(estado), 2)

            mov = "SI" if snapshot.get("motion") else "NO"
            lux = snapshot.get("lux", 0)
            self._line("Mov: {}  Luz: {}".format(mov, lux), 3)

            alarma = snapshot.get("alarm", False)
            self._line("Alarma: {}".format("ACTIVA" if alarma else "off"), 4)

            self._line("MQTT: {}".format(snapshot.get("mqtt", "?")), 5)
            oled.hline(0, 50, self._width, 1)
            self._line(snapshot.get("detail", "")[:16], 6)

            oled.show()
        except Exception as error:                # pragma: no cover
            print("[display] error de renderizado:", error)

    def show_message(self, message, row=3):
        """Muestra un mensaje puntual (bienvenida, error, etc.)."""
        if not self.available:
            return
        try:
            self._oled.fill(0)
            self._line("SEGURIDAD IoT", 0)
            self._line(message, row)
            self._oled.show()
        except Exception as error:                # pragma: no cover
            print("[display] error mostrando mensaje:", error)
