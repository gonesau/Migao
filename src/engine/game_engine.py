"""2D game engine — rendering, hit/miss pipeline and HUD for Armonia Adaptativa."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

import pygame

from domain.models import EmotionSnapshot, EmotionState, GameplayEvent
from engine.components import Lane, Note
from settings import (
    COLOR_BG,
    COLOR_FLOW,
    FALL_DURATION,
    FONT_FEED,
    FONT_HUD,
    FONT_KEY,
    HIT_Y_RATIO,
    HIT_ZONE_HEIGHT,
    LANE_COUNT,
    LANE_KEYS,
    LANE_LABELS,
    MISS_GRACE_SEC,
    NOTE_HEIGHT,
    NOTE_MARGIN,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WTOL_MS,
)


@dataclass
class _Feedback:
    text: str
    color: tuple[int, int, int]
    lane_id: int
    expires_at: float


@dataclass
class _Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: tuple[int, int, int]
    life: float
    max_life: float
    radius: float


@dataclass
class SessionStats:
    total_hits: int = 0
    total_misses: int = 0
    perfects: int = 0
    greats: int = 0
    goods: int = 0
    oks: int = 0
    time_in_state: dict[str, float] = field(default_factory=lambda: {
        "flow": 0.0, "frustration": 0.0, "boredom": 0.0,
    })


def _blend(c1: tuple, c2: tuple, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class GameEngine:
    """Satisfies GameAdapterPort via duck typing."""

    def __init__(self) -> None:
        self.lanes = [
            Lane(lane_id=i, hit_key=LANE_KEYS[i]) for i in range(LANE_COUNT)
        ]
        self.tempo_multiplier: float = 1.0
        self.note_density: float = 1.0
        self.theme_color: tuple = COLOR_FLOW
        self.song_time: float = 0.0

        self._events: list[GameplayEvent] = []
        self._feedback: list[_Feedback] = []
        self._particles: list[_Particle] = []
        self._shake_amp: float = 0.0
        self.stats = SessionStats()

        self._font_hud: pygame.font.Font | None = None
        self._font_key: pygame.font.Font | None = None
        self._font_feed: pygame.font.Font | None = None

    # -- one-time init (call after pygame.init()) -----------------------------

    def init_fonts(self) -> None:
        self._font_hud = pygame.font.SysFont("monospace", FONT_HUD)
        self._font_key = pygame.font.SysFont("monospace", FONT_KEY, bold=True)
        self._font_feed = pygame.font.SysFont("monospace", FONT_FEED, bold=True)

    # -- session lifecycle ----------------------------------------------------

    def reset_session(self) -> None:
        """Clear lanes, feedback, events and stats for a new play session."""
        for lane in self.lanes:
            lane.notes = []
        self.tempo_multiplier = 1.0
        self.note_density = 1.0
        self.theme_color = COLOR_FLOW
        self.song_time = 0.0
        self._events = []
        self._feedback = []
        self._particles = []
        self._shake_amp = 0.0
        self.stats = SessionStats()

    @property
    def shake_offset(self) -> tuple[int, int]:
        if self._shake_amp <= 0.1:
            return (0, 0)
        amp = self._shake_amp
        return (
            int(random.uniform(-amp, amp)),
            int(random.uniform(-amp, amp)),
        )

    # -- port interface (GameAdapterPort) -------------------------------------

    def set_tempo(self, multiplier: float) -> None:
        self.tempo_multiplier = multiplier

    def set_density(self, density: float) -> None:
        self.note_density = density

    def set_theme(self, color: tuple[int, int, int]) -> None:
        self.theme_color = color

    # -- game-loop steps ------------------------------------------------------

    def tick(self, song_time: float) -> None:
        self.song_time = song_time
        for lane in self.lanes:
            for note in lane.notes:
                if note.is_hit or note.is_missed:
                    continue
                if song_time > note.t_ideal + MISS_GRACE_SEC:
                    note.is_missed = True
                    self._emit_miss(note.t_ideal)
                    self._add_feedback("MISS", (220, 60, 60), note.lane_id)

    def process_input(self, events: list[Any], song_time: float) -> None:
        for evt in events:
            if evt.type != pygame.KEYDOWN:
                continue
            for i, lane in enumerate(self.lanes):
                if evt.key == LANE_KEYS[i]:
                    self._handle_lane_press(lane, song_time)

    def update(self, dt: float) -> None:
        for lane in self.lanes:
            lane.clear_resolved()
        self._feedback = [
            fb for fb in self._feedback if fb.expires_at > self.song_time
        ]
        for p in self._particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += 180.0 * dt
            p.life -= dt
        self._particles = [p for p in self._particles if p.life > 0.0]
        if self._shake_amp > 0.0:
            self._shake_amp = max(0.0, self._shake_amp - dt * 28.0)

    # -- event bus ------------------------------------------------------------

    def pop_events(self) -> list[GameplayEvent]:
        evts, self._events = self._events[:], []
        return evts

    # -- main render ----------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        hit_y = int(h * HIT_Y_RATIO)
        lane_w = w // LANE_COUNT

        surface.fill(_blend(COLOR_BG, self.theme_color, 0.10))

        for i, lane in enumerate(self.lanes):
            x = i * lane_w

            if i % 2 == 0:
                alt_surf = pygame.Surface((lane_w, h), pygame.SRCALPHA)
                alt_surf.fill((255, 255, 255, 8))
                surface.blit(alt_surf, (x, 0))

            for note in lane.notes:
                self._draw_note(surface, note, x, lane_w, hit_y)

            hz_color = _blend(self.theme_color, (20, 20, 40), 0.45)
            hz_bright = _blend(self.theme_color, (255, 255, 255), 0.25)
            hz_rect = pygame.Rect(
                x + NOTE_MARGIN,
                hit_y - HIT_ZONE_HEIGHT // 2,
                lane_w - NOTE_MARGIN * 2,
                HIT_ZONE_HEIGHT,
            )
            pygame.draw.rect(surface, hz_color, hz_rect, border_radius=8)
            pygame.draw.rect(surface, hz_bright, hz_rect, 2, border_radius=8)

            if self._font_key:
                key_color = _blend(self.theme_color, (255, 255, 255), 0.6)
                lbl = self._font_key.render(LANE_LABELS[i], True, key_color)
                surface.blit(
                    lbl,
                    (
                        x + lane_w // 2 - lbl.get_width() // 2,
                        hit_y - lbl.get_height() // 2,
                    ),
                )

            for fb in self._feedback:
                if fb.lane_id == i:
                    fade = _clamp(
                        (fb.expires_at - self.song_time) / 0.4, 0.0, 1.0,
                    )
                    self._draw_feedback(surface, fb, x, lane_w, hit_y, fade)

            pygame.draw.line(surface, (35, 35, 55), (x, 0), (x, h), 1)

        pygame.draw.line(surface, (35, 35, 55), (w - 1, 0), (w - 1, h), 1)

        self._draw_particles(surface)

    # -- HUD overlay ----------------------------------------------------------

    def render_hud(
        self,
        surface: pygame.Surface,
        snapshot: EmotionSnapshot,
        state: EmotionState,
    ) -> None:
        if not self._font_hud:
            return

        w = surface.get_width()
        panel_h = 68

        panel = pygame.Surface((w, panel_h), pygame.SRCALPHA)
        panel.fill((8, 8, 18, 210))
        surface.blit(panel, (0, 0))

        pulse = 0.5 + 0.5 * math.sin(self.song_time * 2.4)
        border_col = _blend(
            _blend(self.theme_color, (0, 0, 0), 0.45),
            self.theme_color,
            pulse,
        )
        pygame.draw.line(surface, border_col, (0, panel_h), (w, panel_h), 2)

        state_name = state.value.upper()
        state_color = {
            "flow": (40, 210, 165),
            "frustration": (80, 145, 255),
            "boredom": (255, 165, 45),
        }.get(state.value, (190, 190, 190))

        state_surf = self._font_hud.render(f"  {state_name}", True, state_color)
        surface.blit(state_surf, (16, 8))

        tag_surf = self._font_hud.render("estado emocional", True, (55, 65, 75))
        surface.blit(tag_surf, (16, 36))

        bx, by, bw, bh = 220, 10, 200, 16
        pygame.draw.rect(surface, (30, 35, 50), (bx, by, bw, bh), border_radius=4)
        fill_w = max(0, int(bw * _clamp(snapshot.accw, 0.0, 1.0)))
        if fill_w > 0:
            bar_col = _blend((210, 55, 55), (40, 200, 145), snapshot.accw)
            pygame.draw.rect(
                surface, bar_col, (bx, by, fill_w, bh), border_radius=4,
            )
        pygame.draw.rect(
            surface, (70, 75, 95), (bx, by, bw, bh), 1, border_radius=4,
        )

        acc_lbl = self._font_hud.render(
            f"Acc_w  {snapshot.accw:.2f}", True, (170, 175, 195),
        )
        surface.blit(acc_lbl, (bx, by + bh + 5))

        jitter_ms = snapshot.jitter * 1000.0
        jit_col = (
            (55, 210, 120) if jitter_ms < 30 else
            (255, 185, 45) if jitter_ms < 60 else
            (220, 75, 75)
        )
        jit_surf = self._font_hud.render(
            f"Jitter  {jitter_ms:5.1f} ms", True, jit_col,
        )
        surface.blit(jit_surf, (460, 8))

        risk = snapshot.frustration_risk
        risk_col = (220, 80, 80) if risk > 0.5 else (110, 200, 120)
        risk_surf = self._font_hud.render(
            f"P(F)  {risk:.2f}   racha: {snapshot.miss_streak}",
            True,
            risk_col,
        )
        surface.blit(risk_surf, (460, 36))

        hint = self._font_hud.render("ESC - salir", True, (50, 55, 65))
        surface.blit(hint, (w - hint.get_width() - 16, 26))

    # -- private helpers ------------------------------------------------------

    def _handle_lane_press(self, lane: Lane, song_time: float) -> None:
        best, best_err = None, float("inf")
        for note in lane.notes:
            if note.is_hit or note.is_missed:
                continue
            err = abs(song_time - note.t_ideal)
            if err < best_err:
                best, best_err = note, err

        if best is None:
            return

        tol = WTOL_MS / 1000.0
        if best_err > tol * 2.0:
            return

        best.is_hit = True
        self._emit_hit(t_ideal=best.t_ideal, t_real=song_time)
        self.stats.total_hits += 1
        self._spawn_hit_particles(lane.lane_id, best_err)

        if best_err <= tol * 0.25:
            self._add_feedback("PERFECT!", (255, 240, 80), lane.lane_id)
            self.stats.perfects += 1
        elif best_err <= tol * 0.55:
            self._add_feedback("GREAT", (80, 255, 165), lane.lane_id)
            self.stats.greats += 1
        elif best_err <= tol:
            self._add_feedback("GOOD", (155, 210, 255), lane.lane_id)
            self.stats.goods += 1
        else:
            self._add_feedback("OK", (170, 170, 170), lane.lane_id)
            self.stats.oks += 1

    def _emit_hit(self, t_ideal: float, t_real: float) -> None:
        self._events.append(
            GameplayEvent(kind="hit", t_ideal=t_ideal, t_real=t_real),
        )

    def _emit_miss(self, t_ideal: float) -> None:
        self._events.append(
            GameplayEvent(kind="miss", t_ideal=t_ideal, t_real=None),
        )
        self.stats.total_misses += 1
        self._shake_amp = min(12.0, self._shake_amp + 6.5)

    def _add_feedback(
        self,
        text: str,
        color: tuple[int, int, int],
        lane_id: int,
    ) -> None:
        self._feedback = [fb for fb in self._feedback if fb.lane_id != lane_id]
        self._feedback.append(
            _Feedback(
                text=text,
                color=color,
                lane_id=lane_id,
                expires_at=self.song_time + 0.55,
            ),
        )

    def _spawn_hit_particles(self, lane_id: int, timing_err: float) -> None:
        w = SCREEN_WIDTH
        lane_w = w // LANE_COUNT
        cx = lane_id * lane_w + lane_w // 2
        cy = int(SCREEN_HEIGHT * HIT_Y_RATIO)
        base_color = _blend(self.theme_color, (255, 255, 255), 0.4)
        count = 14 if timing_err < (WTOL_MS / 1000.0) * 0.5 else 8
        for _ in range(count):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(90.0, 240.0)
            vx = speed * math.cos(angle)
            vy = speed * math.sin(angle) - 60.0
            life = random.uniform(0.35, 0.65)
            self._particles.append(
                _Particle(
                    x=float(cx), y=float(cy), vx=vx, vy=vy,
                    color=base_color, life=life, max_life=life,
                    radius=random.uniform(2.2, 3.8),
                )
            )

    def _draw_particles(self, surface: pygame.Surface) -> None:
        def _ch(v: float) -> int:
            return min(255, int(v))

        for p in self._particles:
            if p.max_life <= 0.0:
                continue
            alpha = max(0.0, min(1.0, p.life / p.max_life))
            r = max(1, int(p.radius * (0.6 + 0.4 * alpha)))
            col = (
                _ch(p.color[0] * alpha + 10),
                _ch(p.color[1] * alpha + 10),
                _ch(p.color[2] * alpha + 10),
            )
            pygame.draw.circle(surface, col, (int(p.x), int(p.y)), r)

    def _draw_note(
        self,
        surface: pygame.Surface,
        note: Note,
        lane_x: int,
        lane_w: int,
        hit_y: int,
    ) -> None:
        if self.song_time < note.spawn_time:
            return

        total_fall = note.t_ideal - note.spawn_time
        if total_fall <= 0:
            return

        progress = (self.song_time - note.spawn_time) / total_fall
        center_y = int(progress * hit_y)

        if center_y > hit_y + NOTE_HEIGHT * 3:
            return

        if note.is_hit:
            if self.song_time - note.t_ideal < 0.18:
                color, border = (80, 255, 145), (210, 255, 225)
            else:
                return
        elif note.is_missed:
            if self.song_time - note.t_ideal < 0.22:
                color, border = (195, 50, 50), (255, 100, 100)
            else:
                return
        else:
            dist = abs(center_y - hit_y)
            glow = _clamp(1.0 - dist / (hit_y * 0.45), 0.0, 1.0)
            color = _blend(self.theme_color, (255, 255, 255), glow * 0.55)
            border = _blend(self.theme_color, (255, 255, 255), 0.75)

        rect = pygame.Rect(
            lane_x + NOTE_MARGIN,
            center_y - NOTE_HEIGHT // 2,
            lane_w - NOTE_MARGIN * 2,
            NOTE_HEIGHT,
        )
        pygame.draw.rect(surface, color, rect, border_radius=6)
        pygame.draw.rect(surface, border, rect, 1, border_radius=6)

    def accumulate_state_time(self, state: EmotionState, dt: float) -> None:
        self.stats.time_in_state[state.value] += dt

    def render_summary(self, surface: pygame.Surface) -> None:
        if not self._font_hud:
            return

        surface.fill(COLOR_BG)
        cx = SCREEN_WIDTH // 2
        y = 100

        title_font = pygame.font.SysFont("monospace", 36, bold=True)
        title = title_font.render("Resumen de sesion", True, (220, 225, 240))
        surface.blit(title, (cx - title.get_width() // 2, y))
        y += 70

        total = self.stats.total_hits + self.stats.total_misses
        accuracy = (self.stats.total_hits / total * 100) if total > 0 else 0.0

        lines = [
            (f"Notas totales:  {total}", (180, 185, 200)),
            (f"Aciertos:  {self.stats.total_hits}   |   Fallos:  {self.stats.total_misses}", (180, 185, 200)),
            (f"Precision global:  {accuracy:.1f}%", (40, 210, 165) if accuracy >= 70 else (220, 80, 80)),
            ("", (0, 0, 0)),
            (f"PERFECT:  {self.stats.perfects}", (255, 240, 80)),
            (f"GREAT:    {self.stats.greats}", (80, 255, 165)),
            (f"GOOD:     {self.stats.goods}", (155, 210, 255)),
            (f"OK:       {self.stats.oks}", (170, 170, 170)),
            ("", (0, 0, 0)),
        ]

        for text, color in lines:
            if not text:
                y += 15
                continue
            surf = self._font_hud.render(text, True, color)
            surface.blit(surf, (cx - surf.get_width() // 2, y))
            y += 32

        y += 10
        state_colors = {
            "flow": (40, 210, 165),
            "frustration": (80, 145, 255),
            "boredom": (255, 165, 45),
        }
        state_labels = {
            "flow": "Flujo",
            "frustration": "Frustracion",
            "boredom": "Aburrimiento",
        }
        for key in ("flow", "frustration", "boredom"):
            secs = self.stats.time_in_state.get(key, 0.0)
            label = state_labels[key]
            color = state_colors[key]
            surf = self._font_hud.render(f"{label}:  {secs:.1f}s", True, color)
            surface.blit(surf, (cx - surf.get_width() // 2, y))
            y += 30

        y += 30
        hint = self._font_hud.render(
            "Pulsa ESC o cierra la ventana para salir", True, (90, 95, 110),
        )
        surface.blit(hint, (cx - hint.get_width() // 2, y))

    def _draw_feedback(
        self,
        surface: pygame.Surface,
        fb: _Feedback,
        lane_x: int,
        lane_w: int,
        hit_y: int,
        fade: float,
    ) -> None:
        if not self._font_feed or fade <= 0.0:
            return
        surf = self._font_feed.render(fb.text, True, fb.color)
        surf.set_alpha(int(255 * fade))
        tx = lane_x + lane_w // 2 - surf.get_width() // 2
        ty = hit_y - HIT_ZONE_HEIGHT // 2 - 48 - int((1.0 - fade) * 28)
        surface.blit(surf, (tx, ty))
