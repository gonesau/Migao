"""Audio manager with synthesised SFX and procedural backing loop — no assets required."""

from __future__ import annotations

import numpy as np
import pygame

from settings import BASE_BPM

_PROFILE_FLOW = "flow"
_PROFILE_FRUSTRATION = "frustration"
_PROFILE_BOREDOM = "boredom"

_TEMPO_REGEN_EPSILON = 0.02


class AudioManager:
    """Satisfies AudioAdapterPort via duck typing."""

    def __init__(self) -> None:
        self.current_profile: str = _PROFILE_FLOW
        self.tempo_multiplier: float = 1.0
        self.is_playing: bool = False

        self._hit_sound: pygame.mixer.Sound | None = None
        self._miss_sound: pygame.mixer.Sound | None = None

        self._loop_sound: pygame.mixer.Sound | None = None
        self._loop_channel: pygame.mixer.Channel | None = None
        self._loop_profile: str | None = None
        self._loop_tempo: float = 0.0

    # -- lifecycle ------------------------------------------------------------

    def load_tracks(self) -> None:
        self._hit_sound = _make_beep(freq=880, duration_ms=70, volume=0.45)
        self._miss_sound = _make_beep(freq=200, duration_ms=130, volume=0.35)
        self._refresh_loop()

    def play(self) -> None:
        self.is_playing = True
        self._ensure_loop_playing()

    def stop(self) -> None:
        self.is_playing = False
        if self._loop_channel is not None:
            self._loop_channel.stop()

    # -- one-shot SFX ---------------------------------------------------------

    def play_hit(self) -> None:
        if self._hit_sound:
            self._hit_sound.play()

    def play_miss(self) -> None:
        if self._miss_sound:
            self._miss_sound.play()

    # -- port interface -------------------------------------------------------

    def set_profile(self, profile_name: str) -> None:
        if profile_name == self.current_profile:
            return
        self.current_profile = profile_name
        self._refresh_loop()

    def set_tempo(self, multiplier: float) -> None:
        if abs(multiplier - self.tempo_multiplier) < _TEMPO_REGEN_EPSILON:
            self.tempo_multiplier = multiplier
            return
        self.tempo_multiplier = multiplier
        self._refresh_loop()

    # -- internal -------------------------------------------------------------

    def _ensure_loop_playing(self) -> None:
        if not self.is_playing or self._loop_sound is None:
            return
        if self._loop_channel is None or not self._loop_channel.get_busy():
            self._loop_channel = self._loop_sound.play(loops=-1)

    def _refresh_loop(self) -> None:
        if pygame.mixer.get_init() is None:
            return
        effective_bpm = BASE_BPM * max(0.1, self.tempo_multiplier)
        self._loop_sound = _make_backing_loop(
            profile=self.current_profile, bpm=effective_bpm,
        )
        self._loop_profile = self.current_profile
        self._loop_tempo = self.tempo_multiplier
        if self._loop_channel is not None:
            self._loop_channel.stop()
            self._loop_channel = None
        self._ensure_loop_playing()


# -- synthesis helpers --------------------------------------------------------

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


_PROFILE_PATTERNS: dict[str, dict] = {
    # Each pattern is 16 sixteenth-note slots per bar.
    _PROFILE_FLOW: {
        "kick":  [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        "hat":   [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
        "bass_freq": 55.0,
        "master_gain": 0.55,
    },
    _PROFILE_FRUSTRATION: {
        "kick":  [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        "hat":   [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        "bass_freq": 49.0,
        "master_gain": 0.40,
    },
    _PROFILE_BOREDOM: {
        "kick":  [1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1],
        "hat":   [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        "bass_freq": 65.0,
        "master_gain": 0.60,
    },
}


def _synth_kick(sample_rate: int, dur: float) -> np.ndarray:
    n = int(sample_rate * dur)
    t = np.linspace(0.0, dur, n, endpoint=False)
    pitch = 120.0 * np.exp(-t * 18.0) + 45.0
    phase = 2.0 * np.pi * np.cumsum(pitch) / sample_rate
    wave = np.sin(phase)
    env = np.exp(-t * 9.0)
    return (wave * env).astype(np.float32)


def _synth_snare(sample_rate: int, dur: float) -> np.ndarray:
    n = int(sample_rate * dur)
    t = np.linspace(0.0, dur, n, endpoint=False)
    rng = np.random.default_rng(seed=7)
    noise = rng.uniform(-1.0, 1.0, size=n)
    tone = np.sin(2.0 * np.pi * 220.0 * t) * 0.35
    env = np.exp(-t * 22.0)
    return ((noise + tone) * env * 0.8).astype(np.float32)


def _synth_hat(sample_rate: int, dur: float) -> np.ndarray:
    n = int(sample_rate * dur)
    t = np.linspace(0.0, dur, n, endpoint=False)
    rng = np.random.default_rng(seed=13)
    noise = rng.uniform(-1.0, 1.0, size=n)
    env = np.exp(-t * 60.0)
    return (noise * env * 0.45).astype(np.float32)


def _synth_bass_note(sample_rate: int, dur: float, freq: float) -> np.ndarray:
    n = int(sample_rate * dur)
    t = np.linspace(0.0, dur, n, endpoint=False)
    wave = np.sin(2.0 * np.pi * freq * t) * 0.7
    wave += np.sin(2.0 * np.pi * freq * 2.0 * t) * 0.15
    attack = max(1, int(n * 0.03))
    env = np.ones(n, dtype=np.float32)
    env[:attack] = np.linspace(0.0, 1.0, attack)
    env *= np.exp(-t * 3.5)
    return (wave * env).astype(np.float32)


def _mix_into(dest: np.ndarray, source: np.ndarray, offset: int, gain: float) -> None:
    end = min(offset + len(source), len(dest))
    if end <= offset:
        return
    take = end - offset
    dest[offset:end] += source[:take] * gain


def _make_backing_loop(profile: str, bpm: float) -> pygame.mixer.Sound:
    sample_rate = pygame.mixer.get_init()[0]
    pattern = _PROFILE_PATTERNS.get(profile, _PROFILE_PATTERNS[_PROFILE_FLOW])

    beat_sec = 60.0 / bpm
    bar_sec = beat_sec * 4.0
    total_samples = int(sample_rate * bar_sec)

    buf = np.zeros(total_samples, dtype=np.float32)

    kick = _synth_kick(sample_rate, dur=min(0.28, beat_sec))
    snare = _synth_snare(sample_rate, dur=min(0.20, beat_sec))
    hat = _synth_hat(sample_rate, dur=min(0.09, beat_sec * 0.5))
    bass = _synth_bass_note(
        sample_rate, dur=min(0.55, beat_sec * 1.5), freq=pattern["bass_freq"],
    )

    slot_sec = bar_sec / 16.0
    for slot in range(16):
        offset = int(slot * slot_sec * sample_rate)
        if pattern["kick"][slot]:
            _mix_into(buf, kick, offset, gain=0.95)
            if slot % 4 == 0:
                _mix_into(buf, bass, offset, gain=0.35)
        if pattern["snare"][slot]:
            _mix_into(buf, snare, offset, gain=0.55)
        if pattern["hat"][slot]:
            _mix_into(buf, hat, offset, gain=0.40)

    buf *= pattern["master_gain"]

    peak = float(np.max(np.abs(buf)))
    if peak > 1.0:
        buf /= peak

    fade = max(1, int(sample_rate * 0.008))
    buf[:fade] *= np.linspace(0.0, 1.0, fade)
    buf[-fade:] *= np.linspace(1.0, 0.0, fade)

    pcm = np.clip(buf, -1.0, 1.0)
    pcm16 = (pcm * 32_767).astype(np.int16)
    stereo = np.ascontiguousarray(np.column_stack([pcm16, pcm16]))
    return pygame.sndarray.make_sound(stereo)
