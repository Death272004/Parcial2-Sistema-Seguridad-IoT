# 🚨 Sistema IoT de Seguridad — Detección y Alertas

**Parcial #2 — Desarrollo de Software VIII: Sistema IoT de Monitoreo y Control Inteligente**
Universidad Tecnológica de Panamá (UTP) · Escenario elegido: **4) Sistema de Seguridad - Detección y alertas**

Sistema completo que detecta intrusiones, activa alarmas visuales y sonoras, almacena los datos en
SQLite, los visualiza en **ThingSpeak** y permite **control remoto bidireccional** desde la nube:
ESP32 (simulado en **Wokwi**) ⇄ **MQTT** ⇄ **Backend Python** ⇄ **SQLite + ThingSpeak**.

🔗 **Simulación en Wokwi:** https://wokwi.com/projects/480350734339804161

📦 **Proyecto Wokwi (zip):** [`wokwi/wokwi-sistema-seguridad-iot.zip`](wokwi/wokwi-sistema-seguridad-iot.zip)

---

## 📐 Arquitectura general

```
┌──────────────────────────────┐        ┌──────────────────────────────┐
│  DISPOSITIVO (Wokwi / ESP32) │        │      BROKER MQTT (nube)      │
│  MicroPython modular         │───────▶│  broker.hivemq.com:1883      │
│                              │ telem. │                              │
│  Sensores:                   │ events │   seguridad/casa-01/         │
│   · PIR  (movimiento)  GPIO13│        │        ├─ telemetry         │
│   · LDR  (luz)         GPIO34│◀───────│        ├─ event              │
│  Actuadores:                 │command │        └─ command            │
│   · LED rojo alarma    GPIO25│        └──────────────┬───────────────┘
│   · LED verde estado   GPIO27│                       │
│   · Buzzer (PWM)       GPIO26│        ┌──────────────▼───────────────┐
│   · OLED SSD1306 (I2C)       │        │   BACKEND (Python 3)         │
│  Botón armar/desarmar GPIO14 │        │   · puente MQTT (paho)       │
└──────────────────────────────┘        │   · SQLite (históricos)      │
                                        │   · ThingSpeak (dashboard)   │
                                        │   · TalkBack (comandos)      │
                                        └──────────────┬───────────────┘
                                                       │ HTTP REST
                                        ┌──────────────▼───────────────┐
                                        │  THINGSPEAK (plataforma cloud)│
                                        │  · dashboard en tiempo real  │
                                        │  · TalkBack: comandos nube→EQ │
                                        └──────────────────────────────┘
```

### Flujo de datos

| # | Flujo | Dirección | Transporte |
|---|-------|-----------|------------|
| 1 | Lectura de sensores (PIR + LDR) | hardware → firmware | GPIO / ADC |
| 2 | Telemetría cada 5 s | dispositivo → nube | MQTT `telemetry` |
| 3 | Eventos (movimiento, alarma, comandos) | dispositivo → nube | MQTT `event` |
| 4 | Comandos `ARM/DISARM/SILENCE/STATUS/PING` | nube → dispositivo | MQTT `command` |
| 5 | Persistencia de lecturas, eventos y comandos | backend → SQLite | SQL |
| 6 | Dashboard en tiempo real | backend → ThingSpeak | HTTPS |
| 7 | Comandos creados en la nube | ThingSpeak → backend → dispositivo | HTTPS + MQTT |

---

## 🧩 Componentes

### Sensores (mínimo 2 requeridos)

| Sensor | Parte Wokwi | GPIO | Magnitud |
|--------|-------------|------|----------|
| PIR HC-SR501 | `wokwi-pir-motion-sensor` | 13 | Movimiento (digital) |
| Módulo LDR | `wokwi-photoresistor-sensor` | 34 (ADC) | Iluminación en lux (analógico) |

### Actuadores (mínimo 2 requeridos)

| Actuador | Parte Wokwi | GPIO | Función |
|----------|-------------|------|---------|
| LED rojo | `wokwi-led` + R 220 Ω | 25 | Alarma visual (parpadea) |
| LED verde | `wokwi-led` + R 220 Ω | 27 | Indicador de sistema ARMADO |
| Buzzer | `wokwi-buzzer` | 26 | Sirena (PWM 2 kHz) |
| OLED 128×64 | `board-ssd1306` | 21/22 (I2C) | Estado en pantalla |
| Botón táctil | `wokwi-pushbutton` | 14 | Armar / desarmar localmente |

---

## 📁 Estructura del repositorio

```
Parcial2-Sistema-Seguridad-IoT/
├── README.md                     ← este archivo
├── requirements.txt              ← dependencias del backend
├── firmware/                     ← código del dispositivo (Wokwi)
│   ├── main.py                   ← bucle principal / orquestador
│   ├── config.py                 ← pines, red, MQTT, umbrales
│   ├── sensors.py                ← PIR + LDR (conversión a lux)
│   ├── actuators.py              ← LEDs, buzzer, panel de alarma
│   ├── display.py                ← pantalla OLED SSD1306
│   ├── net_mqtt.py               ← WiFi + cliente MQTT
│   ├── security.py               ← máquina de estados / eventos
│   ├── diagram.json              ← circuito de Wokwi (cableado)
│   └── libraries.txt             ← bibliotecas de Wokwi
├── wokwi/
│   └── wokwi-sistema-seguridad-iot.zip ← proyecto descargado de Wokwi
├── backend/                      ← integración Python 3
│   ├── main.py                   ← orquestador (MQTT ↔ SQLite ↔ ThingSpeak)
│   ├── config.py                 ← configuración y variables de entorno
│   ├── database.py               ← capa SQLite (thread-safe)
│   ├── mqtt_bridge.py            ← puente MQTT (paho 1.x / 2.x)
│   ├── thingspeak.py             ← cliente ThingSpeak + TalkBack
│   ├── queries.py                ← CLI de históricos
│   └── cli.py                    ← envío manual de comandos
├── cloud/matlab/                 ← extra: MATLAB en ThingSpeak
│   ├── automatizacion_talkback.m ← reglas en la nube → encola comandos TalkBack
│   ├── visualizacion_historial.m ← gráfica de historial para el dashboard
│   └── README.md                 ← cómo pegarlos y programarlos (TimeControl)
├── sql/
│   ├── schema.sql                ← esquema de la base de datos
│   └── consultas.sql             ← consultas de histórico comentadas
├── tests/
│   └── simulador_dispositivo.py  ← emula el ESP32 para probar el backend
├── docs/
│   ├── arquitectura.md           ← diagramas y modelos de datos
│   ├── guia-paso-a-paso.md       ← guía completa (fuente del PDF)
│   ├── guia-paso-a-paso.pdf      ← guía en PDF para entregar
│   └── capturas/                 ← capturas de pantalla (entregable)
└── data/                         ← se genera seguridad.db aquí
```

---

## ⚡ Inicio rápido

### 1. Backend (Python 3.9+)

```bash
pip install -r requirements.txt
python -m backend.main
```

### 2. Dispositivo (Wokwi)

1. Crea un proyecto **ESP32 + MicroPython** en [wokwi.com](https://wokwi.com).
2. Copia el contenido de `firmware/diagram.json` en la pestaña *Diagram*.
3. Agrega los archivos `main.py`, `config.py`, `sensors.py`, `actuators.py`,
   `display.py`, `net_mqtt.py` y `security.py` (botón **+** junto a las pestañas).
4. En *Library Manager* agrega `micropython-umqtt.simple` y `micropython-ssd1306`.
5. Dale ▶ **Start Simulation**.

### 3. Probar sin hardware (opcional)

```bash
python -m tests.simulador_dispositivo --segundos 30 --movimiento
```

---

## 🎮 Comandos de control remoto

```bash
python -m backend.cli ARM        # activar vigilancia
python -m backend.cli DISARM     # desactivar vigilancia
python -m backend.cli SILENCE    # silenciar la alarma
python -m backend.cli STATUS     # pedir el estado
python -m backend.cli PING       # comprobar conectividad
```

También desde la nube:

* **Cliente MQTT web** (HiveMQ) publicando en `seguridad/casa-01/command`.
* **ThingSpeak TalkBack**: crear el comando en la interfaz web; el backend lo
  toma y lo reenvía al dispositivo.
* **Automático con MATLAB (extra)**: un *MATLAB Analysis* programado con
  *TimeControl* revisa el canal cada 5 min y, si estuvo oscuro con el sistema
  desarmado, encola `ARM` en TalkBack por sí solo. Ver
  [`cloud/matlab/README.md`](cloud/matlab/README.md).

## 📊 Consultas de históricos

```bash
python -m backend.queries resumen
python -m backend.queries lecturas -n 20
python -m backend.queries eventos --tipo MOTION_DETECTED
python -m backend.queries comandos
python -m backend.queries entre --desde 2026-11-08T00:00:00 --hasta 2026-11-08T23:59:59
```

---

## ✅ Requisitos del parcial

| Requisito | Dónde se cumple |
|-----------|-----------------|
| Mínimo 2 sensores | `firmware/sensors.py` (PIR + LDR) |
| Mínimo 2 actuadores | `firmware/actuators.py` (LED, buzzer) + OLED en `display.py` |
| Python modular y documentado | 7 módulos con docstring y una responsabilidad c/u |
| Manejo de GPIO con librerías apropiadas | `machine.Pin`, `machine.ADC`, `machine.PWM`, `machine.I2C` |
| Lectura de sensores en tiempo real | bucle de muestreo cada 500 ms en `main.py` |
| Control de actuadores | `AlarmPanel` con parpadeo/pitido no bloqueante |
| Cliente MQTT en el dispositivo | `firmware/net_mqtt.py` (`umqtt.simple`) |
| Base de datos con timestamp | `sql/schema.sql` + `backend/database.py` |
| Consultas de histórico | `backend/queries.py` y `sql/consultas.sql` |
| Plataforma en la nube + dashboard | ThingSpeak (`backend/thingspeak.py`) |
| Recepción de comandos desde la nube | ThingSpeak TalkBack → MQTT → dispositivo |
| Programación modular y orientada a eventos | `SecuritySystem` + cola de comandos + callbacks MQTT |

---

## 👤 Autor

**Richard Rodríguez** — [github.com/Death272004](https://github.com/Death272004)
Licenciatura en Desarrollo y Gestión de Software · UTP
