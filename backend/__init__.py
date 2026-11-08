"""
backend/__init__.py
=====================================================================
Paquete backend del Sistema de Seguridad IoT (Parcial #2 - DS8).

Módulos:
    config.py       -> parámetros y variables de entorno
    database.py     -> persistencia SQLite
    mqtt_bridge.py  -> puente MQTT (nube <-> dispositivo)
    thingspeak.py   -> integración con ThingSpeak / TalkBack
    main.py         -> orquestador del backend
    queries.py      -> línea de comandos para los históricos
    cli.py          -> envío manual de comandos al dispositivo
=====================================================================
"""
