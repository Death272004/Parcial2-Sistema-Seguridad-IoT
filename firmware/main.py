"""
main.py
=====================================================================
PUNTO DE ENTRADA DEL FIRMWARE
Sistema IoT de Monitoreo y Control Inteligente - PARCIAL #2
Escenario 4: Sistema de Seguridad - Detección y alertas
Materia: Desarrollo de Software VIII (UTP)

Responsabilidades (arquitectura modular y orientada a eventos):

    1. Levantar la comunicación (WiFi + MQTT + NTP).
    2. Instanciar sensores, actuadores y display (capas separadas).
    3. Ejecutar el bucle de muestreo no bloqueante que:
         - lee los sensores en tiempo real,
         - alimenta la máquina de estados (SecuritySystem),
         - despacha los comandos que llegan desde la nube,
         - publica telemetría y eventos por MQTT,
         - refresca el display OLED y el panel de alarma.

Cada archivo del firmware tiene una única responsabilidad:
    config.py     -> parámetros ajustables
    sensors.py    -> lectura de PIR y LDR
    actuators.py  -> LEDs, buzzer y panel de alarma
    display.py    -> pantalla OLED
    net_mqtt.py   -> red WiFi y cliente MQTT
    security.py   -> lógica de negocio / máquina de estados
    main.py       -> orquestación y bucle principal
=====================================================================
"""

import time
from machine import Pin

import config
from sensors import MotionSensor, LightSensor
from actuators import AlarmPanel, Led
from display import OledDisplay
from net_mqtt import connect_wifi, sync_time, MqttService
from security import SecuritySystem


def build_event_emitter(mqtt):
    """Devuelve el receptor de eventos: imprime y publica por MQTT."""

    def emitter(event):
        print("[evento] {type:<20} | {detail} (fuente: {source})".format(**event))
        mqtt.publish_event(event)

    return emitter


def read_button(button, last_press_ms):
    """Detección de flanco de bajada con antirrebote (no bloqueante).

    Devuelve (hubo_pression, ultimo_tiempo_de_presion).
    """
    now = time.ticks_ms()
    if button.value() == 0:                      # activo en bajo
        if time.ticks_diff(now, last_press_ms) > config.BUTTON_DEBOUNCE_MS:
            return True, now
    return False, last_press_ms


def main():
    print("=" * 62)
    print(" SISTEMA DE SEGURIDAD IoT - Detección y alertas")
    print(" Parcial #2 | Desarrollo de Software VIII | UTP")
    print("=" * 62)

    # ------------------------------------------------------------------
    # 1. Inicialización de componentes
    # ------------------------------------------------------------------
    display = OledDisplay()
    display.show_message("Iniciando...")

    pir = MotionSensor()
    ldr = LightSensor()
    alarm_panel = AlarmPanel()
    status_led = Led(config.PIN_LED_STATUS)
    button = Pin(config.PIN_BUTTON, Pin.IN, Pin.PULL_UP)

    print("[init] PIR en GPIO{} | LDR en GPIO{}".format(pir.pin_number,
                                                        ldr.pin_number))
    print("[init] Alarma en GPIO{}/{} | Estado en GPIO{}".format(
        config.PIN_LED_ALARM, config.PIN_BUZZER, config.PIN_LED_STATUS))

    # ------------------------------------------------------------------
    # 2. Conectividad: WiFi -> NTP -> MQTT
    # ------------------------------------------------------------------
    wifi_ok = connect_wifi()
    if wifi_ok:
        sync_time()

    mqtt = MqttService()
    mqtt_ok = wifi_ok and mqtt.connect()

    # La máquina de estados publica sus eventos a través de MQTT
    system = SecuritySystem(emit=build_event_emitter(mqtt))
    system.mqtt_status = "OK" if mqtt_ok else "OFF"

    if not wifi_ok:
        display.show_message("ERROR: sin WiFi")
        system.emit("WIFI_ERROR", "No se pudo conectar a la red WiFi",
                    source="red")
    elif not mqtt_ok:
        display.show_message("ERROR: sin MQTT")
        system.emit("MQTT_ERROR", "No se pudo conectar al broker MQTT",
                    source="red")

    system.emit("SYSTEM_START",
                "Sistema de seguridad iniciado en modo DESARMADO",
                source="arranque")

    # ------------------------------------------------------------------
    # 3. Bucle principal (orientado a eventos y no bloqueante)
    # ------------------------------------------------------------------
    last_sample = 0
    last_telemetry = 0
    last_display = 0
    last_button_press = 0
    button_previous = 1

    try:
        while True:
            now = time.ticks_ms()

            # 3.1 Comandos entrantes desde la nube (MQTT)
            mqtt.check_messages()
            for payload in mqtt.drain_commands():
                system.handle_command(payload, source="mqtt")

            # 3.2 Botón local: arma/desarma el sistema
            pressed, last_button_press = read_button(button, last_button_press)
            if pressed and button_previous == 1:
                system.toggle(source="boton_local")
            button_previous = button.value()

            # 3.3 Muestreo de sensores en tiempo real
            if time.ticks_diff(now, last_sample) >= config.SAMPLE_MS:
                last_sample = now
                motion = pir.read()
                lux = ldr.read_lux()
                system.update(motion, lux, now_ms=now)

            # 3.4 Actuadores: parpadeo del LED y pitido del buzzer
            alarm_panel.set_active(system.state == config.STATE_ALARM)
            alarm_panel.tick(now)

            # LED verde = indicador de sistema ARMADO
            if system.state == config.STATE_ARMED:
                status_led.on()
            else:
                status_led.off()

            # 3.5 Telemetría periódica hacia la nube
            if time.ticks_diff(now, last_telemetry) >= config.TELEMETRY_MS:
                last_telemetry = now
                system.mqtt_status = "OK" if mqtt.connected else "OFF"
                mqtt.publish_telemetry(system.snapshot())

            # 3.6 Refresco del display OLED
            if time.ticks_diff(now, last_display) >= config.DISPLAY_MS:
                last_display = now
                display.render(system.snapshot())

            # 3.7 Mantenimiento de la sesión MQTT
            mqtt.ensure_connected()

            time.sleep_ms(config.LOOP_SLEEP_MS)

    except KeyboardInterrupt:
        print("\n[main] simulación detenida por el usuario")
    finally:
        # Apagado ordenado de actuadores y red
        alarm_panel.shutdown()
        status_led.off()
        mqtt.disconnect()
        print("[main] sistema apagado de forma segura")


if __name__ == "__main__":
    main()
