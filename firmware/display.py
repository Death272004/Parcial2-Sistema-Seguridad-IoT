"""
display.py

Capa de PRESENTACIÓN - Display OLED SSD1306 128x64 (I2C).

Muestra en tiempo real el estado del sistema de seguridad:
estado, detección de movimiento, nivel de luz y alarma.

Diseño DEFENSIVO:
  * Si la biblioteca `micropython-ssd1306` no está instalada o el display
    no responde, el módulo se desactiva a sí mismo y el resto del sistema
    sigue funcionando.
  * Compatibilidad con diferentes versiones del driver ssd1306: el código
    detecta automáticamente los métodos disponibles (hline/vline vs fill/pixel)
    y usa los que existan.
  * Todas las operaciones de renderizado están envueltas en try/except para
    que un error en el display no crashee el firmware.
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


def _safe_hline(oled, x, y, length, color=1):
    """Intenta dibujar una línea horizontal; si el método no existe, usa fill."""
    try:
        oled.hline(x, y, length, color)
    except AttributeError:
        # Fallback: dibujar un rectángulo de 1 píxel de alto
        oled.fill_rect(x, y, length, 1, color)


def _safe_vline(oled, x, y, length, color=1):
    """Intenta dibujar una línea vertical; si el método no existe, usa fill."""
    try:
        oled.vline(x, y, length, color)
    except AttributeError:
        oled.fill_rect(x, y, 1, length, color)


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
        self._has_hline = False
        self._has_vline = False

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
            # Detectar qué métodos soporta el driver concreto de Wokwi
            self._has_hline = hasattr(self._oled, "hline")
            self._has_vline = hasattr(self._oled, "vline")
            print("[display] OLED SSD1306 listo en 0x{:02X} (hline={}, vline={})."
                  .format(found[0], self._has_hline, self._has_vline))
        except Exception as error:                # pragma: no cover
            print("[display] error inicializando OLED:", error)

    def _line(self, text, row, col=0):
        """Escribe una línea recortada al ancho del display."""
        if not self.available:
            return
        # 128 px / 8 px por caracter = 16 caracteres por línea
        max_chars = self._width // 8
        self._oled.text(str(text)[:max_chars], col, row * 8)

    def _hline(self, oled, x, y, length, color=1):
        """Dibuja una línea horizontal usando el método disponible."""
        if self._has_hline:
            oled.hline(x, y, length, color)
        else:
            _safe_hline(oled, x, y, length, color)

    def _vline(self, oled, x, y, length, color=1):
        """Dibuja una línea vertical usando el método disponible."""
        if self._has_vline:
            oled.vline(x, y, length, color)
        else:
            _safe_vline(oled, x, y, length, color)

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
            self._hline(oled, 0, 9, self._width, 1)

            estado = snapshot.get("state", "?")
            self._line("Estado: {}".format(estado), 2)

            mov = "SI" if snapshot.get("motion") else "NO"
            lux = snapshot.get("lux", 0)
            self._line("Mov: {}  Luz: {}".format(mov, lux), 3)

            alarma = snapshot.get("alarm", False)
            self._line("Alarma: {}".format("ACTIVA" if alarma else "off"), 4)

            self._line("MQTT: {}".format(snapshot.get("mqtt", "?")), 5)
            self._hline(oled, 0, 50, self._width, 1)
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