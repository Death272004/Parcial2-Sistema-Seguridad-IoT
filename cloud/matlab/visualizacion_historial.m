% =====================================================================
% cloud/matlab/visualizacion_historial.m
% ---------------------------------------------------------------------
% MATLAB Visualization de ThingSpeak: historial del sistema de seguridad.
%
% Muestra en una sola figura:
%   (1) Luz ambiente (lux) con el umbral de oscuridad y las franjas en
%       que el sistema estuvo ARMADO.
%   (2) Detecciones de movimiento y alarmas por hora.
%
% Cómo se usa: Apps -> MATLAB Visualizations -> New -> Custom (no
% starter code) -> pegar -> rellenar CONFIGURACIÓN -> Save and Run.
% Luego, en "Display Settings", marcar "Show on channel" para que la
% gráfica aparezca en el dashboard del canal.
% =====================================================================

%% ------------------------- CONFIGURACIÓN ----------------------------
CHANNEL_ID    = 0;     % Channel ID
READ_KEY      = '';    % Read API Key ('' si el canal es público)
HORAS         = 24;    % horas de historial a mostrar
UMBRAL_OSCURO = 30;    % lux (igual que firmware/config.py)

%% ------------------------- LEER EL CANAL ----------------------------
args = {'Fields', [1 2 3 4], 'NumMinutes', HORAS * 60, ...
        'OutputFormat', 'timetable'};
if ~isempty(READ_KEY)
    args = [args, {'ReadKey', READ_KEY}];
end
tt = thingSpeakRead(CHANNEL_ID, args{:});

if isempty(tt)
    figure; axis off;
    text(0.5, 0.5, sprintf('Sin datos en las últimas %d h', HORAS), ...
        'HorizontalAlignment', 'center', 'FontSize', 14);
    return;
end

% Los nombres de las columnas dependen del nombre de cada campo; se
% leen por posición para no depender de ellos.
t          = tt.Properties.RowTimes;
movimiento = tt{:, 1};
luz        = tt{:, 2};
armado     = tt{:, 3};
alarma     = tt{:, 4};

%% ------------------------- GRÁFICA 1: LUZ + ARMADO ------------------
figure;
subplot(2, 1, 1);
hold on;
yMax = max([luz; UMBRAL_OSCURO * 2]);
% Franjas sombreadas cuando el sistema estuvo armado
area(t, (armado == 1) * yMax, 'FaceColor', [0.85 0.95 0.85], ...
    'EdgeColor', 'none', 'DisplayName', 'Armado');
plot(t, luz, 'b-', 'LineWidth', 1.2, 'DisplayName', 'Luz (lux)');
yline(UMBRAL_OSCURO, 'k--', 'Oscuro', 'DisplayName', 'Umbral oscuro');
hold off;
ylabel('lux');
title(sprintf('Luz ambiente y estado ARMADO (últimas %d h)', HORAS));
legend('Location', 'northwest');
grid on;

%% ------------------------- GRÁFICA 2: EVENTOS POR HORA --------------
subplot(2, 1, 2);
horas = dateshift(t, 'start', 'hour');
[grupos, ~, idx] = unique(horas);
movPorHora   = accumarray(idx, movimiento == 1);
alarmPorHora = accumarray(idx, alarma == 1);

bar(grupos, [movPorHora, alarmPorHora], 'grouped');
legend({'Movimiento', 'Alarma'}, 'Location', 'northwest');
ylabel('lecturas');
title(sprintf('Movimiento y alarmas por hora (total: %d mov., %d alarma)', ...
    sum(movimiento == 1), sum(alarma == 1)));
grid on;
