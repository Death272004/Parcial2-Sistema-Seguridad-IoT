% =====================================================================
% cloud/matlab/automatizacion_talkback.m
% ---------------------------------------------------------------------
% MATLAB Analysis de ThingSpeak: automatización en la nube.
%
% Lee los últimos minutos del canal (Movimiento, Luz, Armado, Alarma),
% aplica reglas y, si corresponde, ENCOLA un comando en TalkBack.
% El backend Python (backend/main.py) toma ese comando por REST y lo
% reenvía al ESP32 por MQTT, igual que un comando escrito a mano:
%
%   ThingSpeak (canal) --> MATLAB Analysis --> TalkBack --> backend --> MQTT --> ESP32
%
% Reglas:
%   R1  Auto-armado nocturno: toda la ventana con luz < UMBRAL_OSCURO
%       y el sistema DESARMADO  -> encola "ARM".
%   R2  Auto-desarmado de día (opcional, apagada por defecto): toda la
%       ventana con luz > UMBRAL_CLARO, sistema ARMADO y sin alarma
%       -> encola "DISARM".
%
% Anti-duplicados: si ya hay un comando pendiente igual en la cola de
% TalkBack, no se vuelve a encolar.
%
% Cómo se usa: Apps -> MATLAB Analysis -> New -> Custom (no starter
% code) -> pegar este archivo -> rellenar la sección CONFIGURACIÓN ->
% Save and Run. Para que corra solo: Apps -> TimeControl (ver
% cloud/matlab/README.md).
% =====================================================================

%% ------------------------- CONFIGURACIÓN ----------------------------
CHANNEL_ID    = 0;          % Channel ID del canal "Sistema de Seguridad IoT"
READ_KEY      = '';         % Read API Key ('' si el canal es público)
TALKBACK_ID   = 0;          % TalkBack ID
TALKBACK_KEY  = '';         % TalkBack API Key

VENTANA_MIN   = 10;         % minutos de datos que se evalúan
MIN_LECTURAS  = 3;          % lecturas mínimas para decidir

% Mismos umbrales que firmware/config.py
UMBRAL_OSCURO = 30;         % lux  (UMBRAL_LUZ_OSCURO)
UMBRAL_CLARO  = 500;        % lux  (UMBRAL_LUZ_CLARO)

AUTO_ARMAR_DE_NOCHE  = true;    % regla R1
AUTO_DESARMAR_DE_DIA = false;   % regla R2 (opcional)

%% ------------------------- 1. LEER EL CANAL -------------------------
% field1 = Movimiento (0/1), field2 = Luz (lux),
% field3 = Armado (0/1),     field4 = Alarma (0/1)
if isempty(READ_KEY)
    [datos, tiempos] = thingSpeakRead(CHANNEL_ID, 'Fields', [1 2 3 4], ...
        'NumMinutes', VENTANA_MIN);
else
    [datos, tiempos] = thingSpeakRead(CHANNEL_ID, 'Fields', [1 2 3 4], ...
        'NumMinutes', VENTANA_MIN, 'ReadKey', READ_KEY);
end

% Quitar filas incompletas (NaN)
validas  = all(~isnan(datos), 2);
datos    = datos(validas, :);
tiempos  = tiempos(validas);
n        = size(datos, 1);

fprintf('Lecturas válidas en los últimos %d min: %d\n', VENTANA_MIN, n);
if n < MIN_LECTURAS
    fprintf('Sin datos suficientes (¿backend apagado?). No se hace nada.\n');
    return;
end

movimiento = datos(:, 1);
luz        = datos(:, 2);
armado     = datos(:, 3);
alarma     = datos(:, 4);

armadoAhora = armado(end) == 1;
alarmaAhora = alarma(end) == 1;

fprintf('Último dato: %s | luz=%.1f lux | armado=%d | alarma=%d\n', ...
    datestr(tiempos(end)), luz(end), armado(end), alarma(end));
fprintf('Luz en la ventana: mín=%.1f  media=%.1f  máx=%.1f lux\n', ...
    min(luz), mean(luz), max(luz));
fprintf('Detecciones de movimiento en la ventana: %d\n', sum(movimiento));

%% ------------------------- 2. APLICAR REGLAS ------------------------
comando = '';
motivo  = '';

if AUTO_ARMAR_DE_NOCHE && ~armadoAhora && all(luz < UMBRAL_OSCURO)
    comando = 'ARM';
    motivo  = sprintf('R1: oscuro durante %d min (luz máx %.1f < %d lux) y sistema desarmado', ...
        VENTANA_MIN, max(luz), UMBRAL_OSCURO);
elseif AUTO_DESARMAR_DE_DIA && armadoAhora && ~alarmaAhora && all(luz > UMBRAL_CLARO)
    comando = 'DISARM';
    motivo  = sprintf('R2: claro durante %d min (luz mín %.1f > %d lux), armado y sin alarma', ...
        VENTANA_MIN, min(luz), UMBRAL_CLARO);
end

if isempty(comando)
    fprintf('Ninguna regla se cumple. No se encola nada.\n');
    return;
end

%% ------------------------- 3. EVITAR DUPLICADOS ---------------------
urlCola = sprintf('https://api.thingspeak.com/talkbacks/%d/commands.json', TALKBACK_ID);

pendientes = {};
try
    cola = webread(urlCola, 'api_key', TALKBACK_KEY);
    if iscell(cola)                 % webread puede devolver cell o struct
        cola = [cola{:}];
    end
    for k = 1:numel(cola)
        ejecutado = isfield(cola(k), 'executed_at') && ~isempty(cola(k).executed_at);
        if ~ejecutado
            pendientes{end+1} = upper(strtrim(char(cola(k).command_string))); %#ok<SAGROW>
        end
    end
catch err
    fprintf('Aviso: no se pudo leer la cola de TalkBack (%s).\n', err.message);
end

if any(strcmp(pendientes, comando))
    fprintf('"%s" ya está pendiente en TalkBack. No se duplica.\n', comando);
    return;
end

%% ------------------------- 4. ENCOLAR EN TALKBACK -------------------
fprintf('Regla activada -> %s\n', motivo);
respuesta = webwrite(urlCola, 'api_key', TALKBACK_KEY, 'command_string', comando);
if isstruct(respuesta) && isfield(respuesta, 'id')
    fprintf('Comando "%s" encolado en TalkBack (id=%d). El backend lo enviará al ESP32.\n', ...
        comando, respuesta.id);
else
    fprintf('Comando "%s" encolado en TalkBack. El backend lo enviará al ESP32.\n', comando);
end
