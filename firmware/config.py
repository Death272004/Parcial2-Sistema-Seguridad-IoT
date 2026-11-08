"""
config.py
=====================================================================
Sistema IoT de Monitoreo y Control Inteligente - PARCIAL #2
Escenario elegido: 4) Sistema de Seguridad - Detección y alertas
Materia: Desarrollo de Software VIII (UTP)

Archivo de configuración central.
TODOS los parámetros ajustables del dispositivo (pines, red, MQTT,
umbrales y temporizaciones) viven aquí. Modificar un valor no obliga
a tocar el resto del código: es el "panel de control" del firmware.
=====================================================================
"""

# ----------------------------------------------------------------------
# 1. RED WIFI (Wokwi simula la red "Wokwi-GUEST" sin contraseña)
# ----------------------------------------------------------------------
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""                 # Wokwi-GUEST no requiere contraseña
WIFI_TIMEOUT_MS = 30000            # tiempo máximo de espera para asociar
NTP_ENABLED = True                 # sincronizar hora real (timestamps)
NTP_HOST = "pool.ntp.org"

# ----------------------------------------------------------------------
# 2. BROKER MQTT (broker público gratuito, sin registro)
#    Alternativas: "test.mosquitto.org", "broker.emqx.io"
# ----------------------------------------------------------------------
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "seguridad-esp32-001"
MQTT_USER = ""                     # vacío = conexión anónima
MQTT_PASSWORD = ""
MQTT_KEEPALIVE = 60

# ----------------------------------------------------------------------
# 3. TÓPICOS MQTT (estructura jerárquica por dispositivo)
#    dispositivo -> nube : telemetry / event
#    nube       -> dispositivo : command
# ----------------------------------------------------------------------
DEVICE_ID = "casa-01"
TOPIC_TELEMETRY = "seguridad/{}/telemetry".format(DEVICE_ID)
TOPIC_EVENT = "seguridad/{}/event".format(DEVICE_ID)
TOPIC_COMMAND = "seguridad/{}/command".format(DEVICE_ID)

# ----------------------------------------------------------------------
# 4. MAPEO DE PINES (ESP32 DevKit V4 en Wokwi)
#    Sensores : PIR (movimiento) + LDR (luz ambiental)
#    Actuadores: LED alarma + LED estado + buzzer + OLED
# ----------------------------------------------------------------------
PIN_PIR = 13           # PIR HC-SR501  -> OUT
PIN_LDR = 34           # LDR (módulo AO) -> GPIO34 (ADC1, sólo entrada)
PIN_LED_ALARM = 25     # LED rojo de alarma ( ánodo )
PIN_LED_STATUS = 27    # LED verde de estado ARMADO ( ánodo )
PIN_BUZZER = 26        # Buzzer piezoeléctrico ( pin 2 = positivo )
PIN_BUTTON = 14        # Botón armar/desarmar ( a GND, pull-up interno )

# Bus I2C del display OLED SSD1306 (128x64, dirección 0x3C)
I2C_SDA = 21
I2C_SCL = 22
I2C_FREQ = 400000
OLED_WIDTH = 128
OLED_HEIGHT = 64

# ----------------------------------------------------------------------
# 5. CALIBRACIÓN DEL FOTOSENSOR (LDR)
#    Fórmula tomada de la documentación oficial del módulo en Wokwi.
# ----------------------------------------------------------------------
LDR_VCC = 3.3          # tensión de alimentación del módulo (V)
LDR_R10 = 10000.0      # resistencia fija del divisor (ohmios)
LDR_GAMMA = 0.7        # pendiente log(R)-log(lux) del LDR
LDR_RL10 = 50.0        # resistencia del LDR a 10 lux (kOhm)
LDR_RAW_MAX = 4095     # resolución del ADC de 12 bits

# Umbrales de clasificación de la luz ambiente (lux)
UMBRAL_LUZ_OSCURO = 30.0
UMBRAL_LUZ_CLARO = 500.0

# ----------------------------------------------------------------------
# 6. TEMPORIZACIONES Y COMPORTAMIENTO DE LA ALARMA
# ----------------------------------------------------------------------
SAMPLE_MS = 500            # periodo de muestreo de sensores
TELEMETRY_MS = 5000        # periodo de publicación de telemetría
DISPLAY_MS = 400           # periodo de refresco del OLED
BUTTON_DEBOUNCE_MS = 250   # antirrebote del botón local
LOOP_SLEEP_MS = 50         # descanso del bucle principal

ALARM_TIMEOUT_S = 30       # la alarma se silencia sola a los 30 s
ALARM_BLINK_MS = 250       # parpadeo del LED rojo
ALARM_BEEP_MS = 200        # duración de cada pitido del buzzer
ALARM_FREQ_HZ = 2000       # frecuencia del pitido de alarma

# Estados posibles del sistema de seguridad
STATE_DISARMED = "DESARMADO"
STATE_ARMED = "ARMADO"
STATE_ALARM = "ALARMA"
