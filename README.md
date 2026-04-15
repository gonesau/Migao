# Armonia Adaptativa

Videojuego de ritmo 2D con ajuste dinamico de dificultad (DDA) e inferencia emocional implicita.
El sistema analiza la precision y estabilidad ritmica del jugador en tiempo real para mantenerlo
en la zona de flujo (flow) descrita por Csikszentmihalyi, adaptando velocidad, densidad de notas,
patrones ritmicos y paleta de colores sin intervencion manual.

## Requisitos

- Python 3.11 o superior
- `uv` como gestor de dependencias

## Instalacion

```bash
uv sync
```

Para instalar tambien las dependencias de desarrollo (pytest):

```bash
uv sync --all-extras
```

## Ejecucion

```bash
uv run python src/main.py
```

## Controles

| Tecla | Carril |
|-------|--------|
| D     | 1      |
| F     | 2      |
| J     | 3      |
| K     | 4      |
| ESC   | Salir  |

## Estructura del proyecto

```
src/
  main.py                  # Punto de entrada y loop principal
  settings.py              # Constantes y umbrales centralizados
  domain/
    models.py              # Modelos de dominio puros (sin dependencia de framework)
    ports.py               # Puertos hexagonales (Protocol)
  engine/
    game_engine.py         # Motor 2D: render, input, hit/miss, HUD, resumen
    note_spawner.py        # Generador de patrones ritmicos por densidad
    components.py          # Note y Lane
  telemetry/
    emotion_engine.py      # Ventana deslizante: Acc_w, Jitter, P(F)
  dda/
    dda_controller.py      # Clasificacion emocional + histeresis + adaptacion
  audio/
    audio_manager.py       # SFX sintetizados (sin archivos de audio)
tests/
  test_emotion_engine.py   # Tests unitarios de telemetria
  test_dda_controller.py   # Tests unitarios de clasificacion y histeresis DDA
```

## Calibracion de umbrales

Los parametros clave se encuentran en `src/settings.py`:

| Parametro                    | Descripcion                                                |
|------------------------------|------------------------------------------------------------|
| `FRUSTRATION_ACCW_THRESHOLD` | Acc_w por debajo del cual se detecta frustracion           |
| `FRUSTRATION_PF_THRESHOLD`   | P(F) por encima del cual se detecta frustracion            |
| `BOREDOM_ACCW_THRESHOLD`     | Acc_w por encima del cual se detecta aburrimiento          |
| `BOREDOM_JITTER_EPSILON`     | Jitter por debajo del cual se confirma aburrimiento        |
| `HYSTERESIS_COOLDOWN_SEC`    | Segundos minimos en un estado antes de permitir transicion |
| `HYSTERESIS_CONFIRMATIONS`   | Evaluaciones consecutivas necesarias para cambiar estado   |
| `TEMPO_STEP_LIMIT`           | Cambio maximo de tempo por ciclo DDA                       |
| `DDA_EVAL_INTERVAL_SEC`      | Intervalo en segundos entre evaluaciones DDA               |
| `SPAWNER_SEED`               | Semilla fija para ejecuciones reproducibles (None = aleatorio) |

## Tests

```bash
uv run pytest
```
