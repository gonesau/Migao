"""DDA controller that maps emotion inference to game adaptations."""

from dataclasses import dataclass
from enum import Enum

from audio.audio_manager import AudioManager, AudioProfile
from engine.game_engine import GameEngine
from settings import (
    BOREDOM_ACCW_THRESHOLD,
    BOREDOM_JITTER_EPSILON,
    COLOR_COLD,
    COLOR_FLOW,
    COLOR_WARM,
    FRUSTRATION_ACCW_THRESHOLD,
    FRUSTRATION_PF_THRESHOLD,
    TEMPO_BOREDOM,
    TEMPO_FLOW,
    TEMPO_FRUSTRATION,
)
from telemetry.emotion_engine import EmotionEngine, EmotionSnapshot


class EmotionState(str, Enum):
    FLOW = "flow"
    FRUSTRATION = "frustration"
    BOREDOM = "boredom"


@dataclass
class DDADecision:
    state: EmotionState
    snapshot: EmotionSnapshot


class DDAController:
    def __init__(self, engine: GameEngine, audio: AudioManager, emotion_engine: EmotionEngine) -> None:
        self.engine = engine
        self.audio = audio
        self.emotion_engine = emotion_engine
        self.current_state = EmotionState.FLOW

    def evaluate(self, snapshot: EmotionSnapshot) -> DDADecision:
        state = self._classify(snapshot)
        self._apply(state)
        return DDADecision(state=state, snapshot=snapshot)

    def _classify(self, snapshot: EmotionSnapshot) -> EmotionState:
        if (
            snapshot.accw < FRUSTRATION_ACCW_THRESHOLD
            or snapshot.frustration_risk > FRUSTRATION_PF_THRESHOLD
        ):
            return EmotionState.FRUSTRATION
        if snapshot.accw > BOREDOM_ACCW_THRESHOLD and snapshot.jitter <= BOREDOM_JITTER_EPSILON:
            return EmotionState.BOREDOM
        return EmotionState.FLOW

    def _apply(self, state: EmotionState) -> None:
        self.current_state = state
        if state == EmotionState.FRUSTRATION:
            self.engine.set_tempo(TEMPO_FRUSTRATION)
            self.engine.set_density(0.8)
            self.engine.set_theme(COLOR_COLD)
            self.audio.set_profile(AudioProfile.FRUSTRATION)
            self.audio.set_tempo(TEMPO_FRUSTRATION)
            return
        if state == EmotionState.BOREDOM:
            self.engine.set_tempo(TEMPO_BOREDOM)
            self.engine.set_density(1.2)
            self.engine.set_theme(COLOR_WARM)
            self.audio.set_profile(AudioProfile.BOREDOM)
            self.audio.set_tempo(TEMPO_BOREDOM)
            return
        self.engine.set_tempo(TEMPO_FLOW)
        self.engine.set_density(1.0)
        self.engine.set_theme(COLOR_FLOW)
        self.audio.set_profile(AudioProfile.FLOW)
        self.audio.set_tempo(TEMPO_FLOW)
