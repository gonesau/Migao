"""Pantalla de tutorial interactivo con demo pausable y adaptación DDA en español."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass

import pygame

from audio.audio_manager import AudioManager
from dda.dda_controller import DDAController
from domain.difficulty import GameDifficulty, profile_for
from domain.models import EmotionSnapshot, EmotionState
from engine.components import Note
from engine.game_engine import GameEngine
from engine.note_spawner import NoteSpawner
from settings import (
    BETA,
    FALL_DURATION,
    FPS,
    GAMMA,
    LANE_KEYS,
    LANE_LABELS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WINDOW_SIZE,
)
from telemetry.emotion_engine import EmotionEngine
from ui import tutorial_strings as ts
from ui.screens import Intent, _Fonts
from ui.widgets import (
    Button,
    draw_animated_backdrop,
    draw_animated_button,
    draw_fade_overlay,
    draw_glass_panel,
    draw_neon_minimal_background,
)
from ui.theme import THEME

TUTORIAL_TOTAL_STEPS = 4
PRESS_WINDOW_SEC = 3.0
ADAPTATION_DURATION_SEC = 28.0
ADAPTATION_MESSAGE_SEC = 4.5
TUTORIAL_DDA_EVAL_SEC = 1.5
TUTORIAL_DDA_COOLDOWN = 2.0
TUTORIAL_DDA_THRESHOLD = 1.0
TUTORIAL_SPAWNER_SEED = 42


class _Phase(enum.Enum):
    INTRO = "intro"
    STEP1_RUN = "step1_run"
    STEP1_FROZEN = "step1_frozen"
    STEP1_WRAP = "step1_wrap"
    STEP2_RUN = "step2_run"
    STEP2_FROZEN = "step2_frozen"
    STEP2_WRAP = "step2_wrap"
    ADAPT_INTRO = "adapt_intro"
    ADAPTATION = "adaptation"
    ADAPT_MESSAGE = "adapt_message"
    DONE = "done"


@dataclass
class _ScriptedNote:
    lane_id: int
    t_ideal: float
    spawned: bool = False
    resolved: bool = False


class TutorialScreen:
    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        fonts: _Fonts,
        engine: GameEngine,
        audio: AudioManager,
    ) -> None:
        self.screen = screen
        self.clock = clock
        self.fonts = fonts
        self.engine = engine
        self.audio = audio
        self._scene = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._phase = _Phase.INTRO
        self._song_time = 0.0
        self._frozen_time = 0.0
        self._pause_started = 0.0
        self._step_note: _ScriptedNote | None = None
        self._overlay_title = ""
        self._overlay_body = ""
        self._overlay_hint = ""
        self._show_press_prompt = False
        self._press_key_label = ""
        self._press_window_remaining = 1.0
        self._adapt_message = ""
        self._adapt_message_until = 0.0
        self._adapt_intro_until = 0.0
        self._emotion_engine: EmotionEngine | None = None
        self._dda: DDAController | None = None
        self._spawner: NoteSpawner | None = None
        self._profile = profile_for(GameDifficulty.EASY)
        self._cached_snap: EmotionSnapshot | None = None
        self._time_since_dda = 0.0
        self._fade_in = 1.0
        self._elapsed = 0.0

        cx = SCREEN_WIDTH // 2
        self._play_btn = Button(
            label=ts.BTN_PLAY_NOW,
            rect=pygame.Rect(cx - 250, SCREEN_HEIGHT - 100, 230, 50),
            primary=True,
            hot_key=pygame.K_RETURN,
        )
        self._menu_btn = Button(
            label=ts.BTN_BACK_MENU,
            rect=pygame.Rect(cx + 20, SCREEN_HEIGHT - 100, 230, 50),
            hot_key=pygame.K_ESCAPE,
        )

    def run(self) -> Intent:
        self._setup_session()
        leaving: Intent | None = None
        fade_out = 0.0

        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self._elapsed += dt
            self._fade_in = max(0.0, self._fade_in - dt * 2.0)

            events = pygame.event.get()
            for evt in events:
                if evt.type == pygame.QUIT:
                    self._teardown()
                    return Intent.QUIT
                if leaving is not None:
                    continue
                if evt.type == pygame.KEYDOWN and evt.key == pygame.K_ESCAPE:
                    if self._phase is _Phase.DONE:
                        leaving = Intent.MENU
                    elif self._phase is _Phase.INTRO:
                        leaving = Intent.MENU
                    else:
                        leaving = Intent.MENU

            if leaving is None:
                leaving = self._handle_phase_input(events, dt)
                if leaving is None:
                    self._update_phase(dt, events)

            self._render()

            if leaving is not None:
                fade_out = min(1.0, fade_out + dt * 2.5)
                draw_fade_overlay(self.screen, int(255 * fade_out))
            elif self._fade_in > 0.0:
                draw_fade_overlay(self.screen, int(255 * self._fade_in))
            pygame.display.flip()

            if leaving is not None and fade_out >= 1.0:
                self._teardown()
                return leaving

    def _setup_session(self) -> None:
        self.engine.reset_session()
        self.engine.set_spanish_labels(True)
        self.engine.configure_session_timing(
            self._profile.wtol_ms,
            self._profile.miss_grace_sec,
        )
        self.engine.set_screen_shake_enabled(False)
        self.engine.set_auto_miss_enabled(True)
        self._emotion_engine = EmotionEngine(window_size=WINDOW_SIZE)
        self._dda = DDAController(
            engine=self.engine,
            audio=self.audio,
            tempo_offset=self._profile.tempo_offset,
            density_offset=self._profile.density_offset,
            boredom_accw_threshold=self._profile.boredom_accw_threshold,
            boredom_jitter_epsilon=self._profile.boredom_jitter_epsilon,
            hysteresis_cooldown_sec=TUTORIAL_DDA_COOLDOWN,
            transition_score_threshold=TUTORIAL_DDA_THRESHOLD,
            transition_score_decay=0.35,
            fast_recovery_hit_streak=5,
        )
        self._dda.reset()
        self._spawner = NoteSpawner(engine=self.engine, seed=TUTORIAL_SPAWNER_SEED)
        self._cached_snap = self._emotion_engine.snapshot(
            wtol_ms=self._profile.wtol_ms, beta=BETA, gamma=GAMMA,
        )
        self.audio.load_tracks()
        self.audio.play()

    def _teardown(self) -> None:
        self.engine.set_spanish_labels(False)
        self.engine.set_auto_miss_enabled(True)
        self.engine.set_screen_shake_enabled(True)
        self.audio.stop()

    def _clear_step_visuals(self) -> None:
        self.engine.clear_visual_feedback()

    def _leave_frozen_phase(self) -> None:
        self.engine.set_auto_miss_enabled(True)

    def _handle_phase_input(
        self,
        events: list[pygame.event.Event],
        dt: float,
    ) -> Intent | None:
        if self._phase is _Phase.INTRO:
            for evt in events:
                if evt.type == pygame.KEYDOWN and evt.key in (
                    pygame.K_RETURN,
                    pygame.K_SPACE,
                ):
                    self._start_step1()
            return None

        if self._phase is _Phase.DONE:
            mouse_pos = pygame.mouse.get_pos()
            for evt in events:
                if evt.type == pygame.KEYDOWN:
                    if evt.key in (pygame.K_RETURN, pygame.K_SPACE):
                        return Intent.PLAY
                    if evt.key == pygame.K_ESCAPE:
                        return Intent.MENU
                elif evt.type == pygame.MOUSEBUTTONDOWN and evt.button == 1:
                    if self._play_btn.contains(evt.pos):
                        return Intent.PLAY
                    if self._menu_btn.contains(evt.pos):
                        return Intent.MENU
            return None

        if self._phase in (_Phase.STEP1_FROZEN, _Phase.STEP2_FROZEN):
            self._handle_frozen_input(events)
            return None

        if self._phase is _Phase.ADAPT_INTRO:
            for evt in events:
                if evt.type == pygame.KEYDOWN and evt.key in (
                    pygame.K_RETURN,
                    pygame.K_SPACE,
                ):
                    self._clear_step_visuals()
                    self._phase = _Phase.ADAPTATION
                    self._overlay_title = ts.ADAPT_TITLE
                    self._overlay_body = ts.ADAPT_BODY
            return None

        if self._phase is _Phase.ADAPTATION:
            self.engine.process_input(events, self._song_time)

        return None

    def _handle_frozen_input(self, events: list[pygame.event.Event]) -> None:
        if self._step_note is None:
            return
        lane_id = self._step_note.lane_id
        for evt in events:
            if evt.type != pygame.KEYDOWN:
                continue
            if evt.key != LANE_KEYS[lane_id]:
                continue
            press_time = self._step_note.t_ideal
            self.engine.process_input([evt], press_time)
            self._drain_gameplay_events()
            self._show_press_prompt = False
            if self._note_is_resolved(self._step_note):
                self._step_note.resolved = True
                self._leave_frozen_phase()
                self._clear_step_visuals()
                self._advance_scripted_step_from_frozen()
            return

    def _start_step1(self) -> None:
        self._clear_step_visuals()
        self._phase = _Phase.STEP1_RUN
        self._song_time = 0.0
        fall = FALL_DURATION / self.engine.tempo_multiplier
        t_ideal = self._song_time + fall + 0.6
        self._step_note = _ScriptedNote(lane_id=0, t_ideal=t_ideal)
        self._overlay_title = ts.STEP1_TITLE
        self._overlay_body = ts.STEP1_BODY
        self._overlay_hint = ts.STEP1_HINT

    def _start_step2(self) -> None:
        self._clear_step_visuals()
        self._phase = _Phase.STEP2_RUN
        self._song_time = 0.0
        for lane in self.engine.lanes:
            lane.notes = []
        fall = FALL_DURATION / self.engine.tempo_multiplier
        t_ideal = self._song_time + fall + 0.6
        self._step_note = _ScriptedNote(lane_id=1, t_ideal=t_ideal)
        self._overlay_title = ts.STEP2_TITLE
        self._overlay_body = ts.STEP2_BODY
        self._overlay_hint = ts.STEP2_HINT

    def _start_adaptation(self) -> None:
        self._clear_step_visuals()
        self._phase = _Phase.ADAPT_INTRO
        self._adapt_intro_until = time.perf_counter() + 999.0
        self._song_time = 0.0
        for lane in self.engine.lanes:
            lane.notes = []
        self._spawner = NoteSpawner(engine=self.engine, seed=TUTORIAL_SPAWNER_SEED)
        self._overlay_title = ts.ADAPT_TITLE
        self._overlay_body = ts.ADAPT_BODY
        self._overlay_hint = ts.ADAPT_ESC

    def _spawn_scripted_note(self, scripted: _ScriptedNote) -> None:
        if scripted.spawned:
            return
        fall = FALL_DURATION / max(0.1, self.engine.tempo_multiplier)
        spawn_time = max(0.0, scripted.t_ideal - fall)
        self.engine.lanes[scripted.lane_id].add_note(
            Note(
                lane_id=scripted.lane_id,
                t_ideal=scripted.t_ideal,
                spawn_time=spawn_time,
                shape="circle",
            ),
        )
        scripted.spawned = True

    def _note_is_resolved(self, scripted: _ScriptedNote) -> bool:
        if scripted.resolved:
            return True
        for note in self.engine.lanes[scripted.lane_id].notes:
            if note.t_ideal == scripted.t_ideal:
                return note.is_hit or note.is_missed
        return False

    def _enter_scripted_wrap(self) -> None:
        self._phase = (
            _Phase.STEP1_WRAP
            if self._phase in (_Phase.STEP1_FROZEN, _Phase.STEP1_RUN)
            else _Phase.STEP2_WRAP
        )

    def _advance_scripted_step(self) -> None:
        if self._phase is _Phase.STEP1_WRAP:
            self._start_step2()
        elif self._phase is _Phase.STEP2_WRAP:
            self._start_adaptation()

    def _advance_scripted_step_from_frozen(self) -> None:
        if self._phase is _Phase.STEP1_FROZEN:
            self._start_step2()
        elif self._phase is _Phase.STEP2_FROZEN:
            self._start_adaptation()

    def _enter_frozen_phase(self) -> None:
        if self._step_note is None:
            return
        self._frozen_time = self._step_note.t_ideal
        self._song_time = self._frozen_time
        self.engine.set_auto_miss_enabled(False)
        self.engine.tick(self._frozen_time)
        self._pause_started = time.perf_counter()
        self._press_key_label = LANE_LABELS[self._step_note.lane_id]
        self._show_press_prompt = True
        self._press_window_remaining = 1.0
        self._phase = (
            _Phase.STEP1_FROZEN
            if self._phase is _Phase.STEP1_RUN
            else _Phase.STEP2_FROZEN
        )

    def _update_phase(
        self,
        dt: float,
        events: list[pygame.event.Event],
    ) -> None:
        if self._phase is _Phase.INTRO:
            return

        if self._phase is _Phase.DONE:
            return

        if self._phase in (_Phase.STEP1_RUN, _Phase.STEP2_RUN):
            self._update_scripted_run(dt)
            return

        if self._phase in (_Phase.STEP1_FROZEN, _Phase.STEP2_FROZEN):
            self._update_frozen(dt)
            return

        if self._phase in (_Phase.STEP1_WRAP, _Phase.STEP2_WRAP):
            if self._step_note and self._step_note.resolved:
                self._advance_scripted_step()
                return
            self._song_time += dt
            self.engine.tick(self._song_time)
            if self._step_note and self._note_is_resolved(self._step_note):
                self._step_note.resolved = True
                self.engine.update(dt)
                self._drain_gameplay_events()
                self._advance_scripted_step()
                return
            self.engine.update(dt)
            self._drain_gameplay_events()
            if self._step_note and self._note_is_resolved(self._step_note):
                self._step_note.resolved = True
                self._advance_scripted_step()
            return

        if self._phase is _Phase.ADAPT_INTRO:
            return

        if self._phase is _Phase.ADAPT_MESSAGE:
            if time.perf_counter() >= self._adapt_message_until:
                self._phase = _Phase.ADAPTATION
                self._overlay_body = ts.ADAPT_BODY
            return

        if self._phase is _Phase.ADAPTATION:
            self._update_adaptation(dt, events)

    def _update_scripted_run(self, dt: float) -> None:
        if self._step_note is None:
            return
        self._spawn_scripted_note(self._step_note)
        self._song_time += dt
        self.engine.tick(self._song_time)
        self.engine.update(dt)

        if self._song_time >= self._step_note.t_ideal:
            self._enter_frozen_phase()

    def _update_frozen(self, dt: float) -> None:
        if self._step_note is None:
            return
        elapsed_pause = time.perf_counter() - self._pause_started
        self._press_window_remaining = max(
            0.0,
            1.0 - elapsed_pause / PRESS_WINDOW_SEC,
        )
        self.engine.tick(self._frozen_time)
        self.engine.update(dt)

        if elapsed_pause >= PRESS_WINDOW_SEC:
            grace = self._profile.miss_grace_sec
            self._leave_frozen_phase()
            self._song_time = self._step_note.t_ideal + grace + 0.05
            self.engine.tick(self._song_time)
            self._drain_gameplay_events()
            self._show_press_prompt = False
            self._step_note.resolved = True
            self._clear_step_visuals()
            self._advance_scripted_step_from_frozen()

    def _update_adaptation(
        self,
        dt: float,
        events: list[pygame.event.Event],
    ) -> None:
        assert self._emotion_engine is not None
        assert self._dda is not None
        assert self._spawner is not None

        self._song_time += dt
        self._spawner.update(
            self._song_time,
            self.engine.tempo_multiplier,
            self.engine.note_density,
        )
        self.engine.tick(self._song_time)
        self.engine.update(dt)
        self._drain_gameplay_events()

        self._time_since_dda += dt
        self.engine.accumulate_state_time(self._dda.current_state, dt)

        if self._time_since_dda >= TUTORIAL_DDA_EVAL_SEC:
            snap = self._emotion_engine.snapshot(
                wtol_ms=self._profile.wtol_ms, beta=BETA, gamma=GAMMA,
            )
            decision = self._dda.evaluate(snap, dt_since_last=self._time_since_dda)
            self._time_since_dda = 0.0
            self._cached_snap = snap
            if decision.was_transition:
                self._phase = _Phase.ADAPT_MESSAGE
                self._adapt_message = ts.adaptation_message_es(decision.new_state)
                self._adapt_message_until = time.perf_counter() + ADAPTATION_MESSAGE_SEC
                self._overlay_title = ts.state_label_es(decision.new_state)
                self._overlay_body = self._adapt_message
                self._overlay_hint = (
                    f"{ts.TEMPO_LABEL}: {self.engine.tempo_multiplier:.2f}  |  "
                    f"{ts.DENSITY_LABEL}: {self.engine.note_density:.2f}"
                )
                return

        self._cached_snap = self._emotion_engine.snapshot(
            wtol_ms=self._profile.wtol_ms, beta=BETA, gamma=GAMMA,
        )

        if self._song_time >= ADAPTATION_DURATION_SEC:
            self._phase = _Phase.DONE
            self._overlay_title = ts.DONE_TITLE
            self._overlay_body = ts.DONE_BODY
            self._overlay_hint = ""

    def _drain_gameplay_events(self) -> None:
        if self._emotion_engine is None:
            return
        for game_evt in self.engine.pop_events():
            if game_evt.kind == "hit" and game_evt.t_real is not None:
                self._emotion_engine.record_hit(
                    t_ideal=game_evt.t_ideal,
                    t_real=game_evt.t_real,
                )
                self.audio.play_hit()
            elif game_evt.kind == "miss":
                self._emotion_engine.record_miss(
                    t_ideal=game_evt.t_ideal,
                    miss_grace_sec=self._profile.miss_grace_sec,
                )
                self.audio.play_miss()

    def _render(self) -> None:
        if self._phase is _Phase.INTRO:
            self._render_intro()
            return

        if self._phase is _Phase.DONE:
            self._render_done()
            return

        draw_neon_minimal_background(self.screen, self._elapsed, overlay_alpha=82)
        draw_animated_backdrop(
            self._scene,
            base_color=(28, 12, 48),
            accent_color=(140, 70, 255),
            time_sec=self._song_time,
        )
        self.engine.render(self._scene)

        if self._cached_snap is not None and self._dda is not None:
            self.engine.render_hud_tutorial(
                self._scene,
                self._cached_snap,
                self._dda.current_state,
            )

        ox, oy = self.engine.shake_offset
        self.screen.blit(self._scene, (ox, oy))
        self._draw_tutorial_overlay()

    def _render_intro(self) -> None:
        draw_neon_minimal_background(self.screen, self._elapsed)
        draw_glass_panel(self.screen, pygame.Rect(220, 120, 840, 420), alpha=118)

        title = self.fonts.title.render(ts.INTRO_TITLE, True, (240, 245, 255))
        self.screen.blit(
            title,
            (SCREEN_WIDTH // 2 - title.get_width() // 2, 160),
        )
        y = 250
        for line in (ts.INTRO_BODY, ts.INTRO_KEYS):
            surf = self.fonts.body.render(line, True, (180, 190, 210))
            self.screen.blit(
                surf,
                (SCREEN_WIDTH // 2 - surf.get_width() // 2, y),
            )
            y += 36

        cont = self.fonts.small.render(ts.INTRO_CONTINUE, True, (120, 200, 255))
        esc = self.fonts.small.render(ts.INTRO_ESC, True, (120, 130, 150))
        self.screen.blit(
            cont,
            (SCREEN_WIDTH // 2 - cont.get_width() // 2, SCREEN_HEIGHT - 90),
        )
        self.screen.blit(
            esc,
            (SCREEN_WIDTH // 2 - esc.get_width() // 2, SCREEN_HEIGHT - 62),
        )

    def _render_done(self) -> None:
        mouse_pos = pygame.mouse.get_pos()
        draw_neon_minimal_background(self.screen, self._elapsed)
        draw_glass_panel(self.screen, pygame.Rect(220, 140, 840, 380), alpha=118)

        title = self.fonts.title.render(ts.DONE_TITLE, True, (240, 245, 255))
        body = self.fonts.body.render(ts.DONE_BODY, True, (180, 190, 210))
        self.screen.blit(
            title,
            (SCREEN_WIDTH // 2 - title.get_width() // 2, 200),
        )
        self.screen.blit(
            body,
            (SCREEN_WIDTH // 2 - body.get_width() // 2, 290),
        )
        draw_animated_button(
            self.screen,
            self._play_btn,
            self.fonts.button,
            accent=THEME.accent,
            hover=self._play_btn.contains(mouse_pos),
            time_sec=self._elapsed,
        )
        draw_animated_button(
            self.screen,
            self._menu_btn,
            self.fonts.button,
            accent=(170, 180, 200),
            hover=self._menu_btn.contains(mouse_pos),
            time_sec=self._elapsed,
        )

    def _draw_tutorial_overlay(self) -> None:
        step_num = {
            _Phase.STEP1_RUN: 1,
            _Phase.STEP1_FROZEN: 1,
            _Phase.STEP1_WRAP: 1,
            _Phase.STEP2_RUN: 2,
            _Phase.STEP2_FROZEN: 2,
            _Phase.STEP2_WRAP: 2,
            _Phase.ADAPT_INTRO: 3,
            _Phase.ADAPTATION: 3,
            _Phase.ADAPT_MESSAGE: 3,
        }.get(self._phase, 0)

        if step_num > 0:
            prog = self.fonts.small.render(
                ts.step_progress(step_num, TUTORIAL_TOTAL_STEPS),
                True,
                (150, 160, 180),
            )
            self.screen.blit(prog, (24, SCREEN_HEIGHT - 36))

        if not self._overlay_title:
            return

        panel = pygame.Rect(80, SCREEN_HEIGHT - 200, SCREEN_WIDTH - 160, 150)
        draw_glass_panel(self.screen, panel, alpha=140)

        title_surf = self.fonts.button.render(
            self._overlay_title, True, (230, 235, 250),
        )
        self.screen.blit(title_surf, (panel.x + 20, panel.y + 14))

        body_surf = self.fonts.body.render(
            self._overlay_body, True, (180, 190, 210),
        )
        self.screen.blit(body_surf, (panel.x + 20, panel.y + 48))

        if self._overlay_hint:
            hint_surf = self.fonts.small.render(
                self._overlay_hint, True, (130, 140, 160),
            )
            self.screen.blit(hint_surf, (panel.x + 20, panel.y + 78))

        if self._show_press_prompt:
            press = self.fonts.button.render(
                ts.PRESS_KEY.format(key=self._press_key_label),
                True,
                (70, 205, 255),
            )
            self.screen.blit(
                press,
                (SCREEN_WIDTH // 2 - press.get_width() // 2, panel.y - 52),
            )
            bar_w = 220
            bar_x = SCREEN_WIDTH // 2 - bar_w // 2
            bar_y = panel.y - 18
            pygame.draw.rect(
                self.screen, (40, 45, 60), (bar_x, bar_y, bar_w, 10), border_radius=4,
            )
            fill = int(bar_w * self._press_window_remaining)
            if fill > 0:
                pygame.draw.rect(
                    self.screen,
                    (70, 205, 255),
                    (bar_x, bar_y, fill, 10),
                    border_radius=4,
                )
            win_lbl = self.fonts.small.render(ts.PRESS_WINDOW, True, (150, 160, 180))
            self.screen.blit(
                win_lbl,
                (SCREEN_WIDTH // 2 - win_lbl.get_width() // 2, bar_y - 22),
            )
