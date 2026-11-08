"""
sensors.py
=====================================================================
Capa de SENSORES del Sistema de Seguridad (Parcial #2 - DS8).

Este módulo abstrae el hardware para que la lógica de negocio no
dependa de los pines: sólo se consumen objetos de alto nivel.

  * MotionSensor -> sensor PIR de movimiento infrarrojo (digital)
  * LightSensor  -> módulo fotoresistivo LDR (analógico) con
                    conversión calibrada a lux.

Ambos exponen el patrón "leer -> devolver valor" y están pensados
para invocarse en un bucle de muestreo no bloqueante.
=====================================================================
"""

from machine import Pin, ADC

import config


class MotionSensor:
    """Sensor PIR (HC-SR501) conectado a un pin digital.

    El PIR pone su pin OUT en ALTO durante `delayTime` segundos
    (5 s por defecto en Wokwi) cuando detecta movimiento.
    """

    def __init__(self, pin_number=config.PIN_PIR):
        self._pin = Pin(pin_number, Pin.IN)
        self._last_state = False
        self._pin_number = pin_number

    @property
    def pin_number(self):
        """Pin GPIO al que está conectado (útil para trazabilidad)."""
        return self._pin_number

    def read(self):
        """Devuelve True si hay movimiento activo en este instante."""
        state = self._pin.value() == 1
        self._last_state = state
        return state

    @property
    def last_state(self):
        """Último estado leído, sin volver a tocar el hardware."""
        return self._last_state

    def has_new_event(self):
        """(evento_nuevo, estado_actual): True sólo en el flanco de subida.

        Patrón orientado a eventos: devuelve True una sola vez por
        cada activación del PIR, evitando reprocesar el mismo estado.
        """
        previous = self._last_state
        current = self._pin.value() == 1
        self._last_state = current
        return (current and not previous), current


class LightSensor:
    """Módulo LDR (salida analógica AO) con conversión a lux.

    El módulo forma un divisor de tensión: el LDR va hacia VCC y una
    resistencia de 10 kΩ hacia GND, de modo que a más luz el LDR
    baja de resistencia y la tensión en AO disminuye.

        V = VCC * R10 / (R_LDR + R10)  ->  R_LDR = R10 * (VCC/V - 1)
        lux = (RL10 * 10^3 * 10^GAMMA / R_LDR) ^ (1/GAMMA)
    """

    def __init__(self, pin_number=config.PIN_LDR):
        self._pin_number = pin_number
        self._adc = ADC(Pin(pin_number))
        # Rango completo de 0 a ~3.3 V (ATTN_11DB)
        try:
            self._adc.atten(ADC.ATTN_11DB)
        except (AttributeError, ValueError):
            pass  # algunos firmwares ya vienen configurados
        self._raw = 0
        self._lux = 0.0

    @property
    def pin_number(self):
        return self._pin_number

    def _read_raw(self):
        """Lee el ADC y normaliza a 12 bits (0..4095)."""
        try:
            return self._adc.read()            # firmwares MicroPython clásicos
        except AttributeError:
            return self._adc.read_u16() >> 4   # firmwares nuevos (16 bits)

    def read_raw(self):
        """Devuelve la lectura cruda del convertidor analógico-digital."""
        self._raw = self._read_raw()
        return self._raw

    def read_lux(self):
        """Convierte la lectura analógica en iluminación (lux)."""
        raw = self._read_raw()
        self._raw = raw

        if raw <= 0:
            # Tensión ~0 V => resistencia del LDR muy alta => oscuridad
            self._lux = 0.0
            return 0.0

        voltage = (raw / float(config.LDR_RAW_MAX)) * config.LDR_VCC

        # Evita divisiones por cuyo denominador tienda a 0 (LDR muy oscuro)
        if voltage <= 0.01:
            self._lux = 0.0
            return 0.0
        if voltage >= config.LDR_VCC * 0.99:
            self._lux = 99999.0
            return self._lux

        resistance = config.LDR_R10 * (config.LDR_VCC / voltage - 1.0)
        if resistance <= 0:
            self._lux = 99999.0
            return self._lux

        lux = (config.LDR_RL10 * 1000.0 *
               (10 ** config.LDR_GAMMA) / resistance) ** (1.0 / config.LDR_GAMMA)

        self._lux = round(lux, 1)
        return self._lux

    @property
    def last_lux(self):
        """Último valor de lux calculado."""
        return self._lux

    @property
    def last_raw(self):
        """Última lectura cruda del ADC."""
        return self._raw

    @staticmethod
    def classify(lux):
        """Clasifica la iluminación en una categoría textual."""
        if lux < config.UMBRAL_LUZ_OSCURO:
            return "OSCURO"
        if lux < config.UMBRAL_LUZ_CLARO:
            return "NORMAL"
        return "CLARO"
