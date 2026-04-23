"""Screen controllers: Menu, Playing session and Summary with retry flow."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import Enum

import pygame

from audio.audio_manager import AudioManager
from dda.dda_controller import DDAController
from domain.difficulty import GameDifficulty, profile_for
from domain.models import EmotionSnapshot, EmotionState
from engine.game_engine import GameEngine, SessionStats
from engine.note_spawner import NoteSpawner
from settings import (
    BETA,
    COLOR_BG,
    COLOR_COLD,
    COLOR_FLOW,
    COLOR_WARM,
    DDA_EVAL_INTERVAL_SEC,
    FPS,
    GAMMA,
    HUD_SNAPSHOT_INTERVAL_SEC,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WINDOW_SIZE,
)
from telemetry.emotion_engine import EmotionEngine
from ui.widgets import (
    Button,
    draw_animated_backdrop,
    draw_button,
    draw_fade_overlay,
)

SONG_DURATION_SEC = 90.0


class Intent(str, Enum):
    NONE = "none"
    QUIT = "quit"
    PLAY = "play"
    MENU = "menu"
    SUMMARY = "summary"


@dataclass
class _Fonts:
    title: pygame.font.Font
    subtitle: pygame.font.Font
    button: pygame.font.Font
    body: pygame.font.Font
    small: pygame.font.Font


def build_fonts() -> _Fonts:
    return _Fonts(
        title=pygame.font.SysFont("arial black,arial", 56, bold=True),
        subtitle=pygame.font.SysFont("arial", 19),
        button=pygame.font.SysFont("arial", 24, bold=True),
        body=pygame.font.SysFont("consolas,monospace", 20),
        small=pygame.font.SysFont("consolas,monospace", 15),
    )


# -- Menu ---------------------------------------------------------------------

class MenuScreen:
    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        fonts: _Fonts,
        initial_difficulty: GameDifficulty = GameDifficulty.MEDIUM,
    ) -> None:
        self.screen = screen
        self.clock = clock
        self.fonts = fonts
        self._elapsed = 0.0
        self._fade_in = 1.0  # 1.0 -> 0.0 as we appear
        self._selected = initial_difficulty

        cx = SCREEN_WIDTH // 2
        bw, bh, gap = 150, 44, 14
        row_w = bw * 3 + gap * 2
        x0 = cx - row_w // 2
        y_diff = 306
        self._diff_specs: list[tuple[GameDifficulty, Button]] = [
            (
                GameDifficulty.EASY,
                Button(label="Fácil", rect=pygame.Rect(x0, y_diff, bw, bh)),
            ),
            (
                GameDifficulty.MEDIUM,
                Button(
                    label="Medio",
                    rect=pygame.Rect(x0 + bw + gap, y_diff, bw, bh),
                ),
            ),
            (
                GameDifficulty.HARD,
                Button(
                    label="Difícil",
                    rect=pygame.Rect(x0 + 2 * (bw + gap), y_diff, bw, bh),
                ),
            ),
        ]
        self._play_btn = Button(
            label="JUGAR",
            rect=pygame.Rect(cx - 150, 382, 300, 58),
            primary=True,
            hot_key=pygame.K_RETURN,
        )
        self._quit_btn = Button(
            label="Salir",
            rect=pygame.Rect(cx - 90, 456, 180, 46),
            hot_key=pygame.K_ESCAPE,
        )

    def run(self) -> tuple[Intent, GameDifficulty | None]:
        leaving: Intent | None = None
        fade_out = 0.0

        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self._elapsed += dt
            self._fade_in = max(0.0, self._fade_in - dt * 1.8)

            mouse_pos = pygame.mouse.get_pos()
            for evt in pygame.event.get():
                if evt.type == pygame.QUIT:
                    return Intent.QUIT, None
                if leaving is not None:
                    continue
                if evt.type == pygame.KEYDOWN:
                    if evt.key in (pygame.K_ESCAPE,):
                        leaving = Intent.QUIT
                    elif evt.key in (pygame.K_RETURN, pygame.K_SPACE):
                        leaving = Intent.PLAY
                    elif evt.key == pygame.K_1:
                        self._selected = GameDifficulty.EASY
                    elif evt.key == pygame.K_2:
                        self._selected = GameDifficulty.MEDIUM
                    elif evt.key == pygame.K_3:
                        self._selected = GameDifficulty.HARD
                    elif evt.key == pygame.K_LEFT:
                        self._cycle_difficulty(-1)
                    elif evt.key == pygame.K_RIGHT:
                        self._cycle_difficulty(1)
                elif evt.type == pygame.MOUSEBUTTONDOWN and evt.button == 1:
                    for diff, btn in self._diff_specs:
                        if btn.contains(evt.pos):
                            self._selected = diff
                    if self._play_btn.contains(evt.pos):
                        leaving = Intent.PLAY
                    elif self._quit_btn.contains(evt.pos):
                        leaving = Intent.QUIT

            self._draw(mouse_pos)

            if leaving is not None:
                fade_out = min(1.0, fade_out + dt * 2.2)
                draw_fade_overlay(self.screen, int(255 * fade_out))
                pygame.display.flip()
                if fade_out >= 1.0:
                    if leaving is Intent.QUIT:
                        return Intent.QUIT, None
                    return Intent.PLAY, self._selected
                continue

            draw_fade_overlay(self.screen, int(255 * self._fade_in))
            pygame.display.flip()

    def _cycle_difficulty(self, delta: int) -> None:
        order = (
            GameDifficulty.EASY,
            GameDifficulty.MEDIUM,
            GameDifficulty.HARD,
        )
        idx = order.index(self._selected)
        self._selected = order[(idx + delta) % len(order)]

    def _draw(self, mouse_pos: tuple[int, int]) -> None:
        draw_animated_backdrop(
            self.screen,
            base_color=(30, 70, 120),
            accent_color=COLOR_FLOW,
            time_sec=self._elapsed,
        )

        title = self.fonts.title.render("MIGAO", True, (240, 245, 255))
        subtitle = self.fonts.subtitle.render(
            "Ritmo adaptativo",
            True, (180, 190, 210),
        )

        title_y = 126 + int(math.sin(self._elapsed * 1.5) * 4)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, title_y))
        self.screen.blit(
            subtitle,
            (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, title_y + 82),
        )

        niv = self.fonts.small.render("Dificultad", True, (150, 160, 180))
        self.screen.blit(niv, (SCREEN_WIDTH // 2 - niv.get_width() // 2, 278))

        for diff, btn in self._diff_specs:
            draw_button(
                self.screen,
                Button(
                    label=btn.label,
                    rect=btn.rect,
                    primary=diff is self._selected,
                ),
                self.fonts.button,
                accent=COLOR_FLOW,
                hover=btn.contains(mouse_pos),
                time_sec=self._elapsed,
            )

        # Buttons
        draw_button(
            self.screen, self._play_btn, self.fonts.button,
            accent=COLOR_FLOW,
            hover=self._play_btn.contains(mouse_pos),
            time_sec=self._elapsed,
        )
        draw_button(
            self.screen, self._quit_btn, self.fonts.button,
            accent=(170, 180, 200),
            hover=self._quit_btn.contains(mouse_pos),
            time_sec=self._elapsed,
        )

        hint = self.fonts.small.render(
            "1-3 o flechas para cambiar dificultad",
            True, (120, 130, 150),
        )
        self.screen.blit(
            hint,
            (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 52),
        )


# -- Playing ------------------------------------------------------------------

_STATE_COLORS = {
    EmotionState.FLOW: COLOR_FLOW,
    EmotionState.FRUSTRATION: COLOR_COLD,
    EmotionState.BOREDOM: COLOR_WARM,
}


class PlayingScreen:
    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        fonts: _Fonts,
        engine: GameEngine,
        audio: AudioManager,
        difficulty: GameDifficulty,
    ) -> None:
        self.screen = screen
        self.clock = clock
        self.fonts = fonts
        self.engine = engine
        self.audio = audio
        self.difficulty = difficulty

        self._scene = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

    def run(self) -> tuple[Intent, SessionStats]:
        self.engine.reset_session()
        profile = profile_for(self.difficulty)
        self.engine.configure_session_timing(
            profile.wtol_ms,
            profile.miss_grace_sec,
        )
        emotion_engine = EmotionEngine(window_size=WINDOW_SIZE)
        dda = DDAController(
            engine=self.engine,
            audio=self.audio,
            tempo_offset=profile.tempo_offset,
            density_offset=profile.density_offset,
            boredom_accw_threshold=profile.boredom_accw_threshold,
            boredom_jitter_epsilon=profile.boredom_jitter_epsilon,
        )
        dda.reset()
        spawner = NoteSpawner(engine=self.engine)

        self.audio.load_tracks()
        self.audio.play()

        start = time.perf_counter()
        time_since_dda_eval = 0.0
        last_snap_time = -1.0
        cached_snap = emotion_engine.snapshot(
            wtol_ms=profile.wtol_ms, beta=BETA, gamma=GAMMA,
        )

        fade_in = 1.0
        exiting: Intent | None = None
        fade_out = 0.0

        playing = True
        while playing or exiting is not None:
            dt = self.clock.tick(FPS) / 1000.0
            song_time = time.perf_counter() - start
            fade_in = max(0.0, fade_in - dt * 2.0)

            events = pygame.event.get()
            for evt in events:
                if evt.type == pygame.QUIT:
                    return Intent.QUIT, self.engine.stats
                if exiting is None and evt.type == pygame.KEYDOWN and evt.key == pygame.K_ESCAPE:
                    exiting = Intent.SUMMARY

            if song_time >= SONG_DURATION_SEC and exiting is None:
                exiting = Intent.SUMMARY

            if exiting is None:
                spawner.update(song_time, self.engine.tempo_multiplier, self.engine.note_density)
                self.engine.tick(song_time)
                self.engine.process_input(events, song_time)
                self.engine.update(dt)

                for game_evt in self.engine.pop_events():
                    if game_evt.kind == "hit" and game_evt.t_real is not None:
                        emotion_engine.record_hit(
                            t_ideal=game_evt.t_ideal, t_real=game_evt.t_real,
                        )
                        self.audio.play_hit()
                    elif game_evt.kind == "miss":
                        emotion_engine.record_miss(
                            t_ideal=game_evt.t_ideal,
                            miss_grace_sec=profile.miss_grace_sec,
                        )
                        self.audio.play_miss()

                time_since_dda_eval += dt
                self.engine.accumulate_state_time(dda.current_state, dt)

                if time_since_dda_eval >= DDA_EVAL_INTERVAL_SEC:
                    snap = emotion_engine.snapshot(
                        wtol_ms=profile.wtol_ms, beta=BETA, gamma=GAMMA,
                    )
                    dda.evaluate(snap, dt_since_last=time_since_dda_eval)
                    time_since_dda_eval = 0.0

                if song_time - last_snap_time >= HUD_SNAPSHOT_INTERVAL_SEC:
                    cached_snap = emotion_engine.snapshot(
                        wtol_ms=profile.wtol_ms, beta=BETA, gamma=GAMMA,
                    )
                    last_snap_time = song_time
            else:
                self.engine.update(dt)

            self._render(cached_snap, dda.current_state, song_time)

            if fade_in > 0.0:
                draw_fade_overlay(self.screen, int(255 * fade_in))
            if exiting is not None:
                fade_out = min(1.0, fade_out + dt * 2.5)
                draw_fade_overlay(self.screen, int(255 * fade_out))
            pygame.display.flip()

            if exiting is not None and fade_out >= 1.0:
                self.audio.stop()
                return exiting, self.engine.stats

    def _render(
        self,
        snapshot: EmotionSnapshot,
        state: EmotionState,
        song_time: float,
    ) -> None:
        self._scene.fill(COLOR_BG)
        self.engine.render(self._scene)
        self.engine.render_hud(self._scene, snapshot, state)

        ox, oy = self.engine.shake_offset
        self.screen.fill(COLOR_BG)
        self.screen.blit(self._scene, (ox, oy))

        remaining = max(0.0, SONG_DURATION_SEC - song_time)
        timer = self.fonts.small.render(
            f"{int(remaining):02d} s restantes", True, (160, 170, 190),
        )
        self.screen.blit(
            timer,
            (SCREEN_WIDTH - timer.get_width() - 18, SCREEN_HEIGHT - timer.get_height() - 12),
        )


# -- Summary ------------------------------------------------------------------

class SummaryScreen:
    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        fonts: _Fonts,
        stats: SessionStats,
    ) -> None:
        self.screen = screen
        self.clock = clock
        self.fonts = fonts
        self.stats = stats
        self._elapsed = 0.0

        cx = SCREEN_WIDTH // 2
        self._retry_btn = Button(
            label="OTRA PARTIDA",
            rect=pygame.Rect(cx - 250, SCREEN_HEIGHT - 86, 230, 50),
            primary=True,
            hot_key=pygame.K_RETURN,
        )
        self._menu_btn = Button(
            label="Menu principal",
            rect=pygame.Rect(cx + 20, SCREEN_HEIGHT - 86, 230, 50),
            hot_key=pygame.K_ESCAPE,
        )

    def run(self) -> Intent:
        leaving: Intent | None = None
        fade_in = 1.0
        fade_out = 0.0

        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self._elapsed += dt
            fade_in = max(0.0, fade_in - dt * 2.0)

            mouse_pos = pygame.mouse.get_pos()
            for evt in pygame.event.get():
                if evt.type == pygame.QUIT:
                    return Intent.QUIT
                if leaving is not None:
                    continue
                if evt.type == pygame.KEYDOWN:
                    if evt.key in (pygame.K_RETURN, pygame.K_SPACE):
                        leaving = Intent.PLAY
                    elif evt.key == pygame.K_ESCAPE:
                        leaving = Intent.MENU
                elif evt.type == pygame.MOUSEBUTTONDOWN and evt.button == 1:
                    if self._retry_btn.contains(evt.pos):
                        leaving = Intent.PLAY
                    elif self._menu_btn.contains(evt.pos):
                        leaving = Intent.MENU

            self._draw(mouse_pos)

            if fade_in > 0.0:
                draw_fade_overlay(self.screen, int(255 * fade_in))
            if leaving is not None:
                fade_out = min(1.0, fade_out + dt * 2.5)
                draw_fade_overlay(self.screen, int(255 * fade_out))

            pygame.display.flip()

            if leaving is not None and fade_out >= 1.0:
                return leaving

    def _draw(self, mouse_pos: tuple[int, int]) -> None:
        draw_animated_backdrop(
            self.screen,
            base_color=(40, 50, 80),
            accent_color=self._dominant_accent(),
            time_sec=self._elapsed,
        )

        header = self.fonts.button.render("Sesion completada", True, (230, 235, 250))
        y = 44
        self.screen.blit(header, (SCREEN_WIDTH // 2 - header.get_width() // 2, y))

        card_rect = pygame.Rect(0, 0, 720, 356)
        card_rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 2)
        self._draw_stats_card(card_rect)

        draw_button(
            self.screen, self._retry_btn, self.fonts.button,
            accent=COLOR_FLOW,
            hover=self._retry_btn.contains(mouse_pos),
            time_sec=self._elapsed,
        )
        draw_button(
            self.screen, self._menu_btn, self.fonts.button,
            accent=(170, 180, 200),
            hover=self._menu_btn.contains(mouse_pos),
            time_sec=self._elapsed,
        )

    def _dominant_accent(self) -> tuple[int, int, int]:
        times = self.stats.time_in_state
        if not times:
            return COLOR_FLOW
        key = max(times, key=lambda k: times[k])
        return {
            "flow": COLOR_FLOW,
            "frustration": COLOR_COLD,
            "boredom": COLOR_WARM,
        }.get(key, COLOR_FLOW)

    def _draw_stats_card(self, rect: pygame.Rect) -> None:
        card = pygame.Surface(rect.size, pygame.SRCALPHA)
        card.fill((16, 20, 32, 210))
        pygame.draw.rect(
            card, (60, 70, 95, 255), card.get_rect(), 2, border_radius=14,
        )
        self.screen.blit(card, rect.topleft)

        total = self.stats.total_hits + self.stats.total_misses
        accuracy = (self.stats.total_hits / total * 100) if total > 0 else 0.0

        left = rect.x + 48
        right = rect.x + rect.width - 48
        top = rect.y + 24
        line_h = 30

        def render_row(y: int, label: str, value: str, color: tuple[int, int, int]) -> None:
            lbl = self.fonts.body.render(label, True, (160, 170, 190))
            val = self.fonts.body.render(value, True, color)
            self.screen.blit(lbl, (left, y))
            self.screen.blit(val, (right - val.get_width(), y))

        render_row(top + line_h * 0, "Notas totales", f"{total}", (220, 225, 240))
        render_row(top + line_h * 1, "Aciertos", f"{self.stats.total_hits}", (80, 220, 165))
        render_row(top + line_h * 2, "Fallos", f"{self.stats.total_misses}", (220, 100, 100))
        acc_color = (80, 220, 165) if accuracy >= 70 else (245, 200, 90) if accuracy >= 45 else (220, 95, 95)
        render_row(top + line_h * 3, "Precision", f"{accuracy:.1f}%", acc_color)

        sep_y = top + line_h * 4 + 6
        pygame.draw.line(
            self.screen, (60, 70, 95),
            (left, sep_y), (right, sep_y), 1,
        )

        render_row(sep_y + 12 + line_h * 0, "PERFECT", f"{self.stats.perfects}", (255, 240, 80))
        render_row(sep_y + 12 + line_h * 1, "GREAT", f"{self.stats.greats}", (80, 220, 165))
        render_row(sep_y + 12 + line_h * 2, "GOOD", f"{self.stats.goods}", (155, 210, 255))
        render_row(sep_y + 12 + line_h * 3, "OK", f"{self.stats.oks}", (170, 170, 170))

        y = sep_y + 12 + line_h * 4 + 8
        self._draw_state_breakdown(left, right, y)

    def _draw_state_breakdown(self, left: int, right: int, y: int) -> None:
        total = sum(self.stats.time_in_state.values()) or 1.0
        labels = {
            "flow": ("Flujo", COLOR_FLOW),
            "frustration": ("Frustracion", COLOR_COLD),
            "boredom": ("Aburrimiento", COLOR_WARM),
        }
        bar_w = right - left
        bar_h = 14
        x = left
        for key in ("flow", "frustration", "boredom"):
            secs = self.stats.time_in_state.get(key, 0.0)
            frac = secs / total
            seg_w = int(bar_w * frac)
            pygame.draw.rect(
                self.screen, labels[key][1], (x, y, seg_w, bar_h),
                border_radius=4,
            )
            x += seg_w

        ly = y + bar_h + 10
        for key in ("flow", "frustration", "boredom"):
            name, color = labels[key]
            secs = self.stats.time_in_state.get(key, 0.0)
            dot = pygame.Rect(left, ly + 5, 10, 10)
            pygame.draw.rect(self.screen, color, dot, border_radius=2)
            txt = self.fonts.small.render(
                f"{name}  {secs:.1f}s", True, (170, 180, 200),
            )
            self.screen.blit(txt, (left + 18, ly))
            left += 200  # advance column
