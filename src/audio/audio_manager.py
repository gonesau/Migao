"""Audio manager interface for base and syncopated layers."""

from enum import Enum


class AudioProfile(str, Enum):
    FLOW = "flow"
    FRUSTRATION = "frustration"
    BOREDOM = "boredom"


class AudioManager:
    def __init__(self) -> None:
        self.current_profile = AudioProfile.FLOW
        self.tempo_multiplier = 1.0
        self.is_playing = False

    def load_tracks(self) -> None:
        # Future pygame.mixer loading logic.
        return None

    def play(self) -> None:
        self.is_playing = True

    def stop(self) -> None:
        self.is_playing = False

    def set_profile(self, profile: AudioProfile) -> None:
        self.current_profile = profile

    def set_tempo(self, multiplier: float) -> None:
        self.tempo_multiplier = multiplier
