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

| Tecla         | Accion                                         |
|---------------|------------------------------------------------|
| D / F / J / K | Pulsar carriles 1 a 4                          |
| Enter / Espacio | Jugar (en menu) / reintentar (en resumen)    |
| ESC           | Volver a menu / salir                          |

## Estructura del proyecto

```
src/
  main.py                  # Punto de entrada: orquesta el flujo Menu/Juego/Resumen
  settings.py              # Constantes y umbrales centralizados
  domain/
    models.py              # Modelos de dominio puros (sin dependencia de framework)
    ports.py               # Puertos hexagonales (Protocol)
  engine/
    game_engine.py         # Motor 2D: render, input, hit/miss, HUD, particulas, shake
    note_spawner.py        # Generador de patrones ritmicos por densidad
    components.py          # Note y Lane
  telemetry/
    emotion_engine.py      # Ventana deslizante: Acc_w, Jitter, P(F)
  dda/
    dda_controller.py      # Clasificacion emocional + histeresis + adaptacion
  audio/
    audio_manager.py       # SFX y bucle procedural generado con numpy
  ui/
    screens.py             # MenuScreen, PlayingScreen, SummaryScreen
    widgets.py             # Botones, gradientes y helpers visuales
tests/
  test_emotion_engine.py   # Tests unitarios de telemetria
  test_dda_controller.py   # Tests unitarios de clasificacion y histeresis DDA
```

## Integracion EmotionEngine + DDA

La telemetria y el controlador adaptativo son piezas independientes que se cablean
en el loop de juego. `DDAController` recibe solo los puertos hexagonales (motor de
juego y audio); el `EmotionEngine` vive en el loop principal y alimenta al DDA a
traves de instantaneas:

```python
emotion_engine = EmotionEngine(window_size=WINDOW_SIZE)
dda = DDAController(engine=game_engine, audio=audio_manager)

# En cada evento de juego:
emotion_engine.record_hit(t_ideal=..., t_real=...)   # o record_miss(...)

# Cada DDA_EVAL_INTERVAL_SEC:
snapshot = emotion_engine.snapshot(wtol_ms=WTOL_MS, beta=BETA, gamma=GAMMA)
dda.evaluate(snapshot, dt_since_last=...)
```

Entre partidas, la sesion se reinicia llamando a `GameEngine.reset_session()`,
`NoteSpawner.reset()` y creando un `EmotionEngine` y `DDAController` nuevos (o
usando sus metodos `clear()` / `reset()` respectivamente).

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
