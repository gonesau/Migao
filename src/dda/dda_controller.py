"""DDA controller — classifies emotional state and applies adaptations via ports."""

from __future__ import annotations

from domain.models import DDADecision, EmotionSnapshot, EmotionState
from domain.ports import AudioAdapterPort, GameAdapterPort
from settings import (
    BOREDOM_ACCW_THRESHOLD,
    BOREDOM_JITTER_EPSILON,
    COLOR_COLD,
    COLOR_FLOW,
    COLOR_WARM,
    DENSITY_BOREDOM,
    DENSITY_FLOW,
    DENSITY_FRUSTRATION,
    FRUSTRATION_ACCW_THRESHOLD,
    FRUSTRATION_PF_THRESHOLD,
    HYSTERESIS_CONFIRMATIONS,
    HYSTERESIS_COOLDOWN_SEC,
    TEMPO_BOREDOM,
    TEMPO_FLOW,
    TEMPO_FRUSTRATION,
    TEMPO_STEP_LIMIT,
)

_STATE_PARAMS: dict[EmotionState, dict] = {
    EmotionState.FRUSTRATION: {
        "tempo": TEMPO_FRUSTRATION,
        "density": DENSITY_FRUSTRATION,
        "color": COLOR_COLD,
        "profile": EmotionState.FRUSTRATION.value,
    },
    EmotionState.BOREDOM: {
        "tempo": TEMPO_BOREDOM,
        "density": DENSITY_BOREDOM,
        "color": COLOR_WARM,
        "profile": EmotionState.BOREDOM.value,
    },
    EmotionState.FLOW: {
        "tempo": TEMPO_FLOW,
        "density": DENSITY_FLOW,
        "color": COLOR_FLOW,
        "profile": EmotionState.FLOW.value,
    },
}


class DDAController:
    def __init__(
        self,
        engine: GameAdapterPort,
        audio: AudioAdapterPort,
    ) -> None:
        self._engine = engine
        self._audio = audio

        self.current_state: EmotionState = EmotionState.FLOW

        self._pending_state: EmotionState = EmotionState.FLOW
        self._confirmation_count: int = 0
        self._time_in_state: float = 0.0

        self._current_tempo: float = TEMPO_FLOW
        self._current_density: float = DENSITY_FLOW

    def evaluate(self, snapshot: EmotionSnapshot, dt_since_last: float) -> DDADecision:
        self._time_in_state += dt_since_last

        raw_state = self._classify(snapshot)
        previous = self.current_state
        was_transition = False

        if raw_state != self.current_state:
            if raw_state == self._pending_state:
                self._confirmation_count += 1
            else:
                self._pending_state = raw_state
                self._confirmation_count = 1

            cooldown_met = self._time_in_state >= HYSTERESIS_COOLDOWN_SEC
            confirmations_met = self._confirmation_count >= HYSTERESIS_CONFIRMATIONS

            if cooldown_met and confirmations_met:
                self.current_state = raw_state
                self._time_in_state = 0.0
                self._confirmation_count = 0
                was_transition = True
        else:
            self._pending_state = self.current_state
            self._confirmation_count = 0

        self._apply(self.current_state)

        return DDADecision(
            previous_state=previous,
            new_state=self.current_state,
            snapshot=snapshot,
            was_transition=was_transition,
        )

    def _classify(self, snapshot: EmotionSnapshot) -> EmotionState:
        is_frustrated = (
            snapshot.accw < FRUSTRATION_ACCW_THRESHOLD
            or snapshot.frustration_risk > FRUSTRATION_PF_THRESHOLD
        )
        if is_frustrated:
            return EmotionState.FRUSTRATION

        is_bored = (
            snapshot.accw > BOREDOM_ACCW_THRESHOLD
            and snapshot.jitter <= BOREDOM_JITTER_EPSILON
        )
        if is_bored:
            return EmotionState.BOREDOM

        return EmotionState.FLOW

    def _apply(self, state: EmotionState) -> None:
        params = _STATE_PARAMS[state]

        target_tempo = params["tempo"]
        self._current_tempo = _step_toward(
            self._current_tempo, target_tempo, TEMPO_STEP_LIMIT,
        )

        target_density = params["density"]
        self._current_density = _step_toward(
            self._current_density, target_density, TEMPO_STEP_LIMIT,
        )

        self._engine.set_tempo(self._current_tempo)
        self._engine.set_density(self._current_density)
        self._engine.set_theme(params["color"])

        self._audio.set_profile(params["profile"])
        self._audio.set_tempo(self._current_tempo)


def _step_toward(current: float, target: float, max_step: float) -> float:
    diff = target - current
    if abs(diff) <= max_step:
        return target
    return current + max_step * (1.0 if diff > 0 else -1.0)
