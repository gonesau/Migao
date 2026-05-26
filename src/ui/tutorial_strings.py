"""Textos en español para el tutorial interactivo."""

from __future__ import annotations

from domain.models import EmotionState

# Calificaciones de acierto (clave interna del motor -> pantalla)
HIT_LABELS_ES: dict[str, str] = {
    "PERFECT!": "Perfecto",
    "GREAT": "Genial",
    "GOOD": "Bien",
    "OK": "Aceptable",
    "MISS": "Fallo",
}

STATE_LABELS_ES: dict[EmotionState, str] = {
    EmotionState.FLOW: "Flujo",
    EmotionState.FRUSTRATION: "Frustración",
    EmotionState.BOREDOM: "Aburrimiento",
}

ADAPTATION_MESSAGES_ES: dict[EmotionState, str] = {
    EmotionState.FRUSTRATION: (
        "Detectamos dificultad. Bajamos el tempo y reducimos notas para ayudarte."
    ),
    EmotionState.BOREDOM: (
        "Vas muy bien. Subimos el ritmo y la densidad para mantenerte desafiado."
    ),
    EmotionState.FLOW: (
        "Estás en la zona ideal. El juego busca mantener este equilibrio."
    ),
}

MENU_TUTORIAL = "Tutorial"

INTRO_TITLE = "Aprende a jugar"
INTRO_BODY = (
    "Las notas caen por cuatro carriles. Pulsa la tecla cuando cada nota "
    "llegue al centro de su carril."
)
INTRO_KEYS = "Teclas: D (carril 1)  F (carril 2)  J (carril 3)  K (carril 4)"
INTRO_CONTINUE = "Pulsa Enter para comenzar"
INTRO_ESC = "ESC para volver al menú"

STEP_PROGRESS = "Paso {current} de {total}"

STEP1_TITLE = "Tu primera nota"
STEP1_BODY = "Pulsa D cuando la nota llegue al centro del carril."
STEP1_HINT = "Cada carril tiene su tecla. Observa la letra en la zona de impacto."
PRESS_KEY = "Pulsa [{key}]"
PRESS_WINDOW = "Momento de pulsar"

STEP2_TITLE = "Calificación del acierto"
STEP2_BODY = "Cuanto más preciso seas, mejor será tu calificación."
STEP2_HINT = (
    "Perfecto = justo a tiempo; Genial = muy cerca; "
    "Bien = dentro del margen; Aceptable = justo dentro del límite."
)

ADAPT_TITLE = "Adaptación en vivo"
ADAPT_BODY = (
    "Ahora juega libremente. El juego se adaptará a tu rendimiento "
    "según tus aciertos y fallos."
)
ADAPT_ESC = "ESC para salir del tutorial"

DONE_TITLE = "Tutorial completado"
DONE_BODY = "Ya puedes jugar una partida completa."
BTN_PLAY_NOW = "Jugar ahora"
BTN_BACK_MENU = "Volver al menú"

HUD_STATE = "Estado"
HUD_PRECISION = "Precisión"
HUD_RHYTHM_VAR = "Variación rítmica"
HUD_FRUSTRATION_RISK = "Riesgo de frustración"
HUD_MISS_STREAK = "Racha de fallos"
HUD_HIT_STREAK = "Racha de aciertos"
HUD_ESC = "ESC para salir"

TEMPO_LABEL = "Tempo"
DENSITY_LABEL = "Densidad de notas"


def hit_label_es(internal: str) -> str:
    return HIT_LABELS_ES.get(internal, internal)


def state_label_es(state: EmotionState) -> str:
    return STATE_LABELS_ES.get(state, state.value)


def adaptation_message_es(state: EmotionState) -> str:
    return ADAPTATION_MESSAGES_ES.get(
        state,
        "El juego ajustó la dificultad según tu rendimiento.",
    )


def step_progress(current: int, total: int) -> str:
    return STEP_PROGRESS.format(current=current, total=total)
