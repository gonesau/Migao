"""2D game engine skeleton with hit/miss event pipeline."""

from dataclasses import dataclass
from typing import Any

from engine.components import Lane
from settings import COLOR_FLOW, LANE_COUNT


@dataclass
class GameplayEvent:
    kind: str
    t_ideal: float
    t_real: float | None = None


class GameEngine:
    def __init__(self) -> None:
        self.lanes = [Lane(lane_id=i, hit_key=i) for i in range(LANE_COUNT)]
        self.tempo_multiplier = 1.0
        self.note_density = 1.0
        self.theme_color = COLOR_FLOW
        self._events: list[GameplayEvent] = []

    def process_input(self, events: list[Any], song_time: float) -> None:
        _ = (events, song_time)

    def update(self, dt: float) -> None:
        _ = dt
        for lane in self.lanes:
            lane.clear_resolved()

    def render(self, surface: Any) -> None:
        _ = surface

    def set_tempo(self, multiplier: float) -> None:
        self.tempo_multiplier = multiplier

    def set_density(self, density: float) -> None:
        self.note_density = density

    def set_theme(self, color: tuple[int, int, int]) -> None:
        self.theme_color = color

    def emit_hit(self, t_ideal: float, t_real: float) -> None:
        self._events.append(GameplayEvent(kind="hit", t_ideal=t_ideal, t_real=t_real))

    def emit_miss(self, t_ideal: float) -> None:
        self._events.append(GameplayEvent(kind="miss", t_ideal=t_ideal, t_real=None))

    def pop_events(self) -> list[GameplayEvent]:
        events = self._events[:]
        self._events.clear()
        return events
