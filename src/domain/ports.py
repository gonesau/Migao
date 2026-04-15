"""Hexagonal ports — contracts that infrastructure adapters must satisfy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from domain.models import EmotionSnapshot


@runtime_checkable
class GameAdapterPort(Protocol):
    """What the DDA layer needs from the game engine."""

    def set_tempo(self, multiplier: float) -> None: ...
    def set_density(self, density: float) -> None: ...
    def set_theme(self, color: tuple[int, int, int]) -> None: ...


@runtime_checkable
class AudioAdapterPort(Protocol):
    """What the DDA layer needs from the audio subsystem."""

    def set_profile(self, profile_name: str) -> None: ...
    def set_tempo(self, multiplier: float) -> None: ...


@runtime_checkable
class TelemetryPort(Protocol):
    """What the main loop needs from the telemetry engine."""

    def record_hit(self, t_ideal: float, t_real: float) -> None: ...
    def record_miss(self, t_ideal: float) -> None: ...
    def snapshot(self, wtol_ms: float, beta: float, gamma: float) -> EmotionSnapshot: ...
