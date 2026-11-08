"""
actuators.py
=====================================================================
Capa de ACTUADORES del Sistema de Seguridad (Parcial #2 - DS8).

Componentes controlados por el ESP32:

  * Led        -> LED de estado (verde) y LED de alarma (rojo)
  * Buzzer     -> alarma sonora con PWM (sin bloquear el bucle)
  * AlarmPanel -> orquesta LED + buzzer con parpadeo/pitido no
                  bloqueante mediante un simple "tick" temporal.

El diseño es no bloqueante a propósito: el bucle principal llama a
`AlarmPanel.tick()` en cada iteración y el panel decide si debe
cambiar de estado según el tiempo transcurrido.
=====================================================================
"""

from machine import Pin, PWM

import config


class Led:
    """LED de 5 mm con ánodo (A) conectado al GPIO y cátodo (C) a GND."""

    def __init__(self, pin_number, initial=0):
        self._pin = Pin(pin_number, Pin.OUT, value=initial)
        self._state = bool(initial)

    def on(self):
        self._pin.value(1)
        self._state = True

    def off(self):
        self._pin.value(0)
        self._state = False

    def toggle(self):
        self._pin.value(0 if self._state else 1)
        self._state = not self._state

    @property
    def is_on(self):
        return self._state


class Buzzer:
    """Buzzer piezoeléctrico controlado con PWM.

    Se usa PWM (y no un simple nivel alto) porque el zumbador
    piezoeléctrico necesita una señal alternada para sonar.
    Si el firmware no soporta PWM sobre el pin, cae en modo digital.
    """

    def __init__(self, pin_number, freq=config.ALARM_FREQ_HZ):
        self._pin = Pin(pin_number, Pin.OUT, value=0)
        self._freq = freq
        self._pwm = None
        self._on = False

    def _ensure_pwm(self):
        if self._pwm is None:
            try:
                self._pwm = PWM(self._pin, freq=self._freq, duty=512)
            except (TypeError, ValueError):
                self._pwm = False  # modo degradado: sin PWM

    def start(self):
        """Emitir el tono de alarma."""
        self._ensure_pwm()
        if self._pwm is False:
            self._pin.value(1)
        else:
            try:
                self._pwm.duty(512)
            except AttributeError:
                self._pwm.duty_u16(32768)
        self._on = True

    def stop(self):
        """Silenciar el zumbador."""
        if self._pwm and self._pwm is not False:
            try:
                self._pwm.duty(0)
            except AttributeError:
                self._pwm.duty_u16(0)
        self._pin.value(0)
        self._on = False

    @property
    def is_on(self):
        return self._on


class AlarmPanel:
    """Panel de alarma: LED rojo parpadeante + buzzer intermitente.

    Uso típico en el bucle principal:

        panel = AlarmPanel()
        while True:
            panel.set_active(True)   # se activa con la detección
            panel.tick(time.ticks_ms())
    """

    def __init__(self,
                 led_pin=config.PIN_LED_ALARM,
                 buzzer_pin=config.PIN_BUZZER,
                 blink_ms=config.ALARM_BLINK_MS,
                 beep_ms=config.ALARM_BEEP_MS):
        self.led = Led(led_pin)
        self.buzzer = Buzzer(buzzer_pin)
        self._blink_ms = blink_ms
        self._beep_ms = beep_ms
        self._active = False
        self._last_toggle = 0

    def set_active(self, active):
        """Activa/desactiva la alarma visual y sonora."""
        active = bool(active)
        if active == self._active:
            return
        self._active = active
        if active:
            self.led.on()
            self.buzzer.start()
        else:
            self.led.off()
            self.buzzer.stop()

    @property
    def is_active(self):
        return self._active

    def tick(self, now_ms):
        """Alterna LED y buzzer cada _blink_ms/_beep_ms (no bloqueante)."""
        if not self._active:
            return
        elapsed = now_ms - self._last_toggle
        if elapsed >= 0 and elapsed >= self._blink_ms:
            self._last_toggle = now_ms
            self.led.toggle()
            if self.buzzer.is_on:
                self.buzzer.stop()
            else:
                self.buzzer.start()

    def shutdown(self):
        """Apaga todo (útil al detener la simulación)."""
        self.set_active(False)
