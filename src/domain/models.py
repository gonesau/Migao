"""Pure domain models shared across layers — no framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EmotionState(str, Enum):
    FLOW = "flow"
    FRUSTRATION = "frustration"
    BOREDOM = "boredom"


@dataclass(frozen=True)
class TelemetrySample:
    t_ideal: float
    t_real: float
    is_miss: bool
    absolute_error: float


@dataclass(frozen=True)
class EmotionSnapshot:
    accw: float
    jitter: float
    frustration_risk: float
    miss_streak: int
    hit_streak: int
    sample_count: int


@dataclass(frozen=True)
class DDADecision:
    previous_state: EmotionState
    new_state: EmotionState
    snapshot: EmotionSnapshot
    was_transition: bool


@dataclass(frozen=True)
class DDAParams:
    tempo_multiplier: float
    note_density: float
    theme_color: tuple[int, int, int]
    audio_profile: str


@dataclass(frozen=True)
class GameplayEvent:
    kind: str
    t_ideal: float
    t_real: float | None = None
