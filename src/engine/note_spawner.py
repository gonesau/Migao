"""Generates rhythmic note patterns and inserts them into engine lanes."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from engine.components import Note
from settings import BASE_BPM, FALL_DURATION, LANE_COUNT, SPAWNER_LEAD_TIME_SEC, SPAWNER_SEED

if TYPE_CHECKING:
    from engine.game_engine import GameEngine

_SIMPLE: list[list[int]] = [
    [0], [2], [1], [3], [0], [2], [1], [3],
]
_MEDIUM: list[list[int]] = [
    [0, 2], [1], [3], [0], [1, 3], [2], [0], [2, 3],
]
_DENSE: list[list[int]] = [
    [0, 1], [2, 3], [0, 2], [1, 3], [0], [1, 2, 3], [0, 2], [1],
]
_SYNCOPATED: list[list[int]] = [
    [0], [1, 3], [], [2], [0, 2], [], [3], [1],
]
_SHAPES: tuple[str, ...] = ("diamond", "circle", "hex", "star")


class NoteSpawner:
    def __init__(self, engine: GameEngine, seed: int | None = None) -> None:
        self.engine = engine
        self._seed = seed if seed is not None else SPAWNER_SEED
        self._beat_index = 0
        self._next_t_ideal = SPAWNER_LEAD_TIME_SEC
        self._rng = random.Random(self._seed)

    def reset(self) -> None:
        """Restart rhythmic sequence for a fresh session."""
        self._beat_index = 0
        self._next_t_ideal = SPAWNER_LEAD_TIME_SEC
        self._rng = random.Random(self._seed)

    def update(
        self,
        song_time: float,
        tempo_multiplier: float,
        density: float,
    ) -> None:
        beat_interval = (60.0 / BASE_BPM) / tempo_multiplier
        fall_duration = FALL_DURATION / tempo_multiplier

        while self._next_t_ideal - song_time <= fall_duration:
            self._spawn_beat(
                t_ideal=self._next_t_ideal,
                fall_duration=fall_duration,
                density=density,
            )
            self._next_t_ideal += beat_interval
            self._beat_index += 1

    def _spawn_beat(
        self,
        t_ideal: float,
        fall_duration: float,
        density: float,
    ) -> None:
        pattern = _pick_pattern(density)
        lanes = list(pattern[self._beat_index % len(pattern)])

        if not lanes:
            return

        if density >= 1.1 and self._rng.random() < 0.35:
            candidates = [l for l in range(LANE_COUNT) if l not in lanes]
            if candidates:
                lanes.append(self._rng.choice(candidates))

        spawn_time = max(0.0, t_ideal - fall_duration)
        for lane_id in lanes:
            shape = _pick_shape(self._beat_index, lane_id, density)
            self.engine.lanes[lane_id].add_note(
                Note(
                    lane_id=lane_id,
                    t_ideal=t_ideal,
                    spawn_time=spawn_time,
                    shape=shape,
                ),
            )


def _pick_pattern(density: float) -> list[list[int]]:
    if density < 0.85:
        return _SIMPLE
    if density < 1.05:
        return _MEDIUM
    if density < 1.15:
        return _DENSE
    return _SYNCOPATED


def _pick_shape(beat_index: int, lane_id: int, density: float) -> str:
    density_bucket = int(density * 10.0)
    idx = (beat_index + lane_id * 2 + density_bucket) % len(_SHAPES)
    return _SHAPES[idx]
