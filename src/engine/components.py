"""Gameplay components: Note and Lane."""

from dataclasses import dataclass, field


@dataclass
class Note:
    lane_id: int
    t_ideal: float
    spawn_time: float
    shape: str = "rect"
    is_hit: bool = False
    is_missed: bool = False


@dataclass
class Lane:
    lane_id: int
    hit_key: int
    notes: list[Note] = field(default_factory=list)

    def add_note(self, note: Note) -> None:
        self.notes.append(note)

    def clear_resolved(self) -> None:
        self.notes = [note for note in self.notes if not (note.is_hit or note.is_missed)]