"""Audio manager with synthesised hit/miss sounds — no audio files required."""

from __future__ import annotations

import numpy as np
import pygame


class AudioManager:
    """Satisfies AudioAdapterPort via duck typing."""

    def __init__(self) -> None:
        self.current_profile: str = "flow"
        self.tempo_multiplier: float = 1.0
        self.is_playing: bool = False

        self._hit_sound: pygame.mixer.Sound | None = None
        self._miss_sound: pygame.mixer.Sound | None = None

    # -- lifecycle ------------------------------------------------------------

    def load_tracks(self) -> None:
        self._hit_sound = _make_beep(freq=880, duration_ms=70, volume=0.45)
        self._miss_sound = _make_beep(freq=200, duration_ms=130, volume=0.35)

    def play(self) -> None:
        self.is_playing = True

    def stop(self) -> None:
        self.is_playing = False

    # -- one-shot SFX ---------------------------------------------------------

    def play_hit(self) -> None:
        if self._hit_sound:
            self._hit_sound.play()

    def play_miss(self) -> None:
        if self._miss_sound:
            self._miss_sound.play()

    # -- port interface -------------------------------------------------------

    def set_profile(self, profile_name: str) -> None:
        self.current_profile = profile_name

    def set_tempo(self, multiplier: float) -> None:
        self.tempo_multiplier = multiplier


def _make_beep(
    freq: float,
    duration_ms: int,
    volume: float = 0.40,
) -> pygame.mixer.Sound:
    sample_rate = pygame.mixer.get_init()[0]
    n = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0.0, duration_ms / 1000.0, n, endpoint=False)

    wave = np.sin(2.0 * np.pi * freq * t) * 0.75
    wave += np.sin(2.0 * np.pi * freq * 2 * t) * 0.18
    wave += np.sin(2.0 * np.pi * freq * 3 * t) * 0.07

    attack = max(1, int(n * 0.04))
    envelope = np.ones(n, dtype=np.float32)
    envelope[:attack] = np.linspace(0.0, 1.0, attack)
    envelope *= np.exp(-6.0 * np.linspace(0.0, 1.0, n))

    wave = np.clip(wave * envelope * volume, -1.0, 1.0)
    pcm = (wave * 32_767).astype(np.int16)

    stereo = np.ascontiguousarray(np.column_stack([pcm, pcm]))
    return pygame.sndarray.make_sound(stereo)
