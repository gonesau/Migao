"""DDA controller — classifies emotional state and applies adaptations via ports.

Hysteresis is implemented at two levels:

* Classifier-level band: entering FRUSTRATION is easier than exiting. Once in
  FRUSTRATION the classifier demands a cleaner recovery (higher Acc_w, lower
  P(F)) before it stops returning FRUSTRATION as the raw state. This prevents
  the player from flickering back as soon as Acc_w dips a hair below the
  entry threshold.
* Transition score: instead of requiring a strict streak of identical raw
  classifications, evidence is accumulated as a float. An opposite reading
  decays the score by `TRANSITION_SCORE_DECAY` instead of wiping it, so a
  single bad sample during recovery does not cancel all progress. On top of
  that, a sustained hit streak provides a fast-recovery override to leave
  FRUSTRATION without waiting for the full score to build up.
"""

from __future__ import annotations

from domain.models import DDADecision, EmotionSnapshot, EmotionState
from domain.ports import AudioAdapterPort, GameAdapterPort
from settings import (
    COLOR_COLD,
    COLOR_FLOW,
    COLOR_WARM,
    DENSITY_BOREDOM,
    DENSITY_FLOW,
    DENSITY_FRUSTRATION,
    DENSITY_MAX,
    DENSITY_MIN,
    FAST_RECOVERY_HIT_STREAK,
    FRUSTRATION_ENTER_ACCW,
    FRUSTRATION_ENTER_PF,
    FRUSTRATION_EXIT_ACCW,
    FRUSTRATION_EXIT_PF,
    HYSTERESIS_COOLDOWN_SEC,
    TEMPO_BOREDOM,
    TEMPO_FLOW,
    TEMPO_FRUSTRATION,
    TEMPO_MAX,
    TEMPO_MIN,
    TEMPO_STEP_LIMIT,
    TRANSITION_SCORE_DECAY,
    TRANSITION_SCORE_THRESHOLD,
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
        tempo_offset: float = 0.0,
        density_offset: float = 0.0,
        boredom_accw_threshold: float = 0.86,
        boredom_jitter_epsilon: float = 0.025,
    ) -> None:
        self._engine = engine
        self._audio = audio
        self._tempo_offset = tempo_offset
        self._density_offset = density_offset
        self._boredom_accw_threshold = boredom_accw_threshold
        self._boredom_jitter_epsilon = boredom_jitter_epsilon

        self.current_state: EmotionState = EmotionState.FLOW
        self._pending_state: EmotionState = EmotionState.FLOW
        self._transition_score: float = 0.0
        self._time_in_state: float = 0.0

        self._current_tempo: float = _clamp_tempo(TEMPO_FLOW + self._tempo_offset)
        self._current_density: float = _clamp_density(DENSITY_FLOW + self._density_offset)

    def reset(self) -> None:
        """Restore controller to its initial FLOW state for a new session."""
        self.current_state = EmotionState.FLOW
        self._pending_state = EmotionState.FLOW
        self._transition_score = 0.0
        self._time_in_state = 0.0
        self._current_tempo = _clamp_tempo(TEMPO_FLOW + self._tempo_offset)
        self._current_density = _clamp_density(DENSITY_FLOW + self._density_offset)
        self._apply(EmotionState.FLOW)

    def evaluate(self, snapshot: EmotionSnapshot, dt_since_last: float) -> DDADecision:
        self._time_in_state += dt_since_last
        previous = self.current_state

        if self._should_fast_recover(snapshot):
            return self._commit_transition(EmotionState.FLOW, previous, snapshot)

        raw_state = self._classify(snapshot)
        self._update_transition_score(raw_state)

        if self._can_commit_transition():
            return self._commit_transition(self._pending_state, previous, snapshot)

        self._apply(self.current_state)
        return DDADecision(
            previous_state=previous,
            new_state=self.current_state,
            snapshot=snapshot,
            was_transition=False,
        )

    # -- hysteresis state machine --------------------------------------------

    def _update_transition_score(self, raw_state: EmotionState) -> None:
        if raw_state != self._pending_state:
            # Direction of evidence changed — start a fresh accumulation so
            # a brief excursion into a third state does not linger forever.
            self._pending_state = raw_state
            self._transition_score = 0.0

        if raw_state != self.current_state:
            self._transition_score += 1.0
        else:
            self._transition_score = max(
                0.0, self._transition_score - TRANSITION_SCORE_DECAY,
            )

    def _can_commit_transition(self) -> bool:
        if self._pending_state == self.current_state:
            return False
        if self._time_in_state < HYSTERESIS_COOLDOWN_SEC:
            return False
        return self._transition_score >= TRANSITION_SCORE_THRESHOLD

    def _commit_transition(
        self,
        target: EmotionState,
        previous: EmotionState,
        snapshot: EmotionSnapshot,
    ) -> DDADecision:
        self.current_state = target
        self._pending_state = target
        self._transition_score = 0.0
        self._time_in_state = 0.0
        self._apply(target)
        return DDADecision(
            previous_state=previous,
            new_state=target,
            snapshot=snapshot,
            was_transition=True,
        )

    def _should_fast_recover(self, snapshot: EmotionSnapshot) -> bool:
        # A sustained hit streak with no recent misses is the clearest signal
        # that the player has recovered. Respect the minimum cooldown so the
        # adaptation parameters still get a chance to settle audibly.
        return (
            self.current_state == EmotionState.FRUSTRATION
            and self._time_in_state >= HYSTERESIS_COOLDOWN_SEC
            and snapshot.miss_streak == 0
            and snapshot.hit_streak >= FAST_RECOVERY_HIT_STREAK
        )

    # -- classification -------------------------------------------------------

    def _classify(self, snapshot: EmotionSnapshot) -> EmotionState:
        if self.current_state == EmotionState.FRUSTRATION:
            # To leave frustration, BOTH metrics must clear the exit band.
            still_frustrated = (
                snapshot.accw < FRUSTRATION_EXIT_ACCW
                or snapshot.frustration_risk > FRUSTRATION_EXIT_PF
            )
            if still_frustrated:
                return EmotionState.FRUSTRATION
        else:
            is_frustrated = (
                snapshot.accw < FRUSTRATION_ENTER_ACCW
                or snapshot.frustration_risk > FRUSTRATION_ENTER_PF
            )
            if is_frustrated:
                return EmotionState.FRUSTRATION

        is_bored = (
            snapshot.accw > self._boredom_accw_threshold
            and snapshot.jitter <= self._boredom_jitter_epsilon
        )
        if is_bored:
            return EmotionState.BOREDOM

        return EmotionState.FLOW

    # -- adaptation application ----------------------------------------------

    def _apply(self, state: EmotionState) -> None:
        params = _STATE_PARAMS[state]

        target_tempo = _clamp_tempo(params["tempo"] + self._tempo_offset)
        self._current_tempo = _step_toward(
            self._current_tempo, target_tempo, TEMPO_STEP_LIMIT,
        )

        target_density = _clamp_density(params["density"] + self._density_offset)
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


def _clamp_tempo(value: float) -> float:
    return max(TEMPO_MIN, min(TEMPO_MAX, value))


def _clamp_density(value: float) -> float:
    return max(DENSITY_MIN, min(DENSITY_MAX, value))
