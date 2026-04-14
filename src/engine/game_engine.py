"""2D game engine – rendering, hit/miss pipeline and HUD for Armonía Adaptativa."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pygame

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
    WTOL_MS,
)


# ── Data types ────────────────────────────────────────────────────────────────
@dataclass
class GameplayEvent:
    kind:    str
    t_ideal: float
    t_real:  float | None = None


@dataclass
class _Feedback:
    text:       str
    color:      tuple[int, int, int]
    lane_id:    int
    expires_at: float


# ── Color helpers ─────────────────────────────────────────────────────────────
def _blend(c1: tuple, c2: tuple, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ── Engine ────────────────────────────────────────────────────────────────────
class GameEngine:
    def __init__(self) -> None:
        self.lanes            = [
            Lane(lane_id=i, hit_key=LANE_KEYS[i]) for i in range(LANE_COUNT)
        ]
        self.tempo_multiplier: float = 1.0
        self.note_density:     float = 1.0
        self.theme_color:      tuple = COLOR_FLOW
        self.song_time:        float = 0.0

        self._events:   list[GameplayEvent] = []
        self._feedback: list[_Feedback]     = []

        self._font_hud:  pygame.font.Font | None = None
        self._font_key:  pygame.font.Font | None = None
        self._font_feed: pygame.font.Font | None = None

    # ── One-time init (call after pygame.init()) ───────────────────────────────
    def init_fonts(self) -> None:
        self._font_hud  = pygame.font.SysFont("monospace", FONT_HUD)
        self._font_key  = pygame.font.SysFont("monospace", FONT_KEY,  bold=True)
        self._font_feed = pygame.font.SysFont("monospace", FONT_FEED, bold=True)

    # ── DDA setters ───────────────────────────────────────────────────────────
    def set_tempo(self, multiplier: float) -> None:
        self.tempo_multiplier = multiplier

    def set_density(self, density: float) -> None:
        self.note_density = density

    def set_theme(self, color: tuple[int, int, int]) -> None:
        self.theme_color = color

    # ── Game-loop steps ───────────────────────────────────────────────────────
    def tick(self, song_time: float) -> None:
        """Advance internal clock and auto-miss notes past their grace window."""
        self.song_time = song_time
        for lane in self.lanes:
            for note in lane.notes:
                if not note.is_hit and not note.is_missed:
                    if song_time > note.t_ideal + MISS_GRACE_SEC:
                        note.is_missed = True
                        self.emit_miss(note.t_ideal)
                        self._add_feedback("MISS", (220, 60, 60), note.lane_id)

    def process_input(self, events: list[Any], song_time: float) -> None:
        for evt in events:
            if evt.type != pygame.KEYDOWN:
                continue
            for i, lane in enumerate(self.lanes):
                if evt.key == LANE_KEYS[i]:
                    self._handle_lane_press(lane, song_time)

    def update(self, dt: float) -> None:  # noqa: ARG002
        for lane in self.lanes:
            lane.clear_resolved()
        # Expire old feedback
        self._feedback = [
            fb for fb in self._feedback if fb.expires_at > self.song_time
        ]

    # ── Event bus ─────────────────────────────────────────────────────────────
    def emit_hit(self, t_ideal: float, t_real: float) -> None:
        self._events.append(
            GameplayEvent(kind="hit", t_ideal=t_ideal, t_real=t_real)
        )

    def emit_miss(self, t_ideal: float) -> None:
        self._events.append(
            GameplayEvent(kind="miss", t_ideal=t_ideal, t_real=None)
        )

    def pop_events(self) -> list[GameplayEvent]:
        evts, self._events = self._events[:], []
        return evts

    # ── Main render ───────────────────────────────────────────────────────────
    def render(self, surface: pygame.Surface) -> None:
        W, H  = surface.get_size()
        hit_y = int(H * HIT_Y_RATIO)
        lane_w = W // LANE_COUNT

        # Background tinted by emotional state
        surface.fill(_blend(COLOR_BG, self.theme_color, 0.10))

        for i, lane in enumerate(self.lanes):
            x = i * lane_w

            # Alternating lane shade (subtle)
            if i % 2 == 0:
                alt_surf = pygame.Surface((lane_w, H), pygame.SRCALPHA)
                alt_surf.fill((255, 255, 255, 8))
                surface.blit(alt_surf, (x, 0))

            # ── Notes ─────────────────────────────────────────────────────────
            for note in lane.notes:
                self._draw_note(surface, note, x, lane_w, hit_y)

            # ── Hit-zone bar ──────────────────────────────────────────────────
            hz_color  = _blend(self.theme_color, (20, 20, 40), 0.45)
            hz_bright = _blend(self.theme_color, (255, 255, 255), 0.25)
            hz_rect   = pygame.Rect(
                x + NOTE_MARGIN,
                hit_y - HIT_ZONE_HEIGHT // 2,
                lane_w - NOTE_MARGIN * 2,
                HIT_ZONE_HEIGHT,
            )
            pygame.draw.rect(surface, hz_color,  hz_rect, border_radius=8)
            pygame.draw.rect(surface, hz_bright, hz_rect, 2, border_radius=8)

            # Key label centred inside hit zone
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

            # ── Feedback text ─────────────────────────────────────────────────
            for fb in self._feedback:
                if fb.lane_id == i:
                    fade = _clamp((fb.expires_at - self.song_time) / 0.4, 0.0, 1.0)
                    self._draw_feedback(surface, fb, x, lane_w, hit_y, fade)

            # Lane separator
            pygame.draw.line(surface, (35, 35, 55), (x, 0), (x, H), 1)

        # Right border
        pygame.draw.line(surface, (35, 35, 55), (W - 1, 0), (W - 1, H), 1)

    # ── HUD overlay ───────────────────────────────────────────────────────────
    def render_hud(
        self,
        surface:  pygame.Surface,
        snapshot: Any,
        state:    Any,
    ) -> None:
        if not self._font_hud:
            return

        W       = surface.get_width()
        panel_h = 68

        # Semi-transparent background strip
        panel = pygame.Surface((W, panel_h), pygame.SRCALPHA)
        panel.fill((8, 8, 18, 210))
        surface.blit(panel, (0, 0))

        # Thin accent line at bottom of HUD
        pygame.draw.line(
            surface,
            _blend(self.theme_color, (0, 0, 0), 0.3),
            (0, panel_h),
            (W, panel_h),
            1,
        )

        # ── State label ───────────────────────────────────────────────────────
        state_name = state.value.upper() if hasattr(state, "value") else str(state)
        state_color = {
            "flow":        (40, 210, 165),
            "frustration": (80, 145, 255),
            "boredom":     (255, 165, 45),
        }.get(state_name.lower(), (190, 190, 190))

        state_surf = self._font_hud.render(f"● {state_name}", True, state_color)
        surface.blit(state_surf, (16, 8))

        # Dim second-line label
        tag_surf = self._font_hud.render("estado emocional", True, (55, 65, 75))
        surface.blit(tag_surf, (16, 36))

        # ── Acc_w progress bar ────────────────────────────────────────────────
        bx, by, bw, bh = 220, 10, 200, 16
        pygame.draw.rect(surface, (30, 35, 50), (bx, by, bw, bh), border_radius=4)
        fill_w = max(0, int(bw * _clamp(snapshot.accw, 0.0, 1.0)))
        if fill_w > 0:
            bar_col = _blend((210, 55, 55), (40, 200, 145), snapshot.accw)
            pygame.draw.rect(
                surface, bar_col, (bx, by, fill_w, bh), border_radius=4
            )
        pygame.draw.rect(surface, (70, 75, 95), (bx, by, bw, bh), 1, border_radius=4)

        acc_lbl = self._font_hud.render(
            f"Acc_w  {snapshot.accw:.2f}", True, (170, 175, 195)
        )
        surface.blit(acc_lbl, (bx, by + bh + 5))

        # ── Jitter ───────────────────────────────────────────────────────────
        jitter_ms = snapshot.jitter * 1000.0
        jit_col   = (
            (55, 210, 120)  if jitter_ms < 30 else
            (255, 185, 45)  if jitter_ms < 60 else
            (220, 75, 75)
        )
        jit_surf = self._font_hud.render(
            f"Jitter  {jitter_ms:5.1f} ms", True, jit_col
        )
        surface.blit(jit_surf, (460, 8))

        # ── P(F) frustration risk ─────────────────────────────────────────────
        risk      = snapshot.frustration_risk
        risk_col  = (220, 80, 80) if risk > 0.5 else (110, 200, 120)
        risk_surf = self._font_hud.render(
            f"P(F)  {risk:.2f}   racha: {snapshot.miss_streak}",
            True, risk_col,
        )
        surface.blit(risk_surf, (460, 36))

        # ── ESC hint ──────────────────────────────────────────────────────────
        hint = self._font_hud.render("ESC – salir", True, (50, 55, 65))
        surface.blit(hint, (W - hint.get_width() - 16, 26))

    # ── Private helpers ───────────────────────────────────────────────────────
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

        # Accept up to 2× the tolerance window
        if best_err <= (WTOL_MS / 1000.0) * 2.0:
            best.is_hit = True
            self.emit_hit(t_ideal=best.t_ideal, t_real=song_time)

            # Judgment tiers
            tol = WTOL_MS / 1000.0
            if best_err <= tol * 0.25:
                self._add_feedback("PERFECT!", (255, 240, 80),  lane.lane_id)
            elif best_err <= tol * 0.55:
                self._add_feedback("GREAT",   (80, 255, 165),  lane.lane_id)
            elif best_err <= tol:
                self._add_feedback("GOOD",    (155, 210, 255), lane.lane_id)
            else:
                self._add_feedback("OK",      (170, 170, 170), lane.lane_id)

    def _add_feedback(
        self,
        text:    str,
        color:   tuple[int, int, int],
        lane_id: int,
    ) -> None:
        # Replace any existing feedback for this lane
        self._feedback = [fb for fb in self._feedback if fb.lane_id != lane_id]
        self._feedback.append(
            _Feedback(
                text=text,
                color=color,
                lane_id=lane_id,
                expires_at=self.song_time + 0.55,
            )
        )

    def _draw_note(
        self,
        surface: pygame.Surface,
        note:    Note,
        lane_x:  int,
        lane_w:  int,
        hit_y:   int,
    ) -> None:
        if self.song_time < note.spawn_time:
            return

        # Each note uses its own fall window (survives tempo changes mid-flight)
        total_fall = note.t_ideal - note.spawn_time
        if total_fall <= 0:
            return

        progress = (self.song_time - note.spawn_time) / total_fall
        center_y  = int(progress * hit_y)

        if center_y > hit_y + NOTE_HEIGHT * 3:
            return  # well past hit zone, skip

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
            # Glow brighter as note approaches hit zone
            dist    = abs(center_y - hit_y)
            glow    = _clamp(1.0 - dist / (hit_y * 0.45), 0.0, 1.0)
            color   = _blend(self.theme_color, (255, 255, 255), glow * 0.55)
            border  = _blend(self.theme_color, (255, 255, 255), 0.75)

        rect = pygame.Rect(
            lane_x + NOTE_MARGIN,
            center_y - NOTE_HEIGHT // 2,
            lane_w - NOTE_MARGIN * 2,
            NOTE_HEIGHT,
        )
        pygame.draw.rect(surface, color,  rect, border_radius=6)
        pygame.draw.rect(surface, border, rect, 1, border_radius=6)

    def _draw_feedback(
        self,
        surface:  pygame.Surface,
        fb:       _Feedback,
        lane_x:   int,
        lane_w:   int,
        hit_y:    int,
        fade:     float,
    ) -> None:
        if not self._font_feed or fade <= 0.0:
            return
        surf = self._font_feed.render(fb.text, True, fb.color)
        surf.set_alpha(int(255 * fade))
        tx = lane_x + lane_w // 2 - surf.get_width() // 2
        # Float upward as it fades
        ty = hit_y - HIT_ZONE_HEIGHT // 2 - 48 - int((1.0 - fade) * 28)
        surface.blit(surf, (tx, ty))