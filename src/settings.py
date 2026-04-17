"""Global constants and thresholds for Armonia Adaptativa."""

# -- display ------------------------------------------------------------------
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
LANE_COUNT = 4

LANE_KEYS = [100, 102, 106, 107]  # D / F / J / K
LANE_LABELS = ["D", "F", "J", "K"]

# -- emotion engine -----------------------------------------------------------
WINDOW_SIZE = 20
WTOL_MS = 100.0  # timing-tolerance window in milliseconds
BETA = 1.4
GAMMA = 4.0

# -- emotion engine telemetry -------------------------------------------------
ACCW_EWMA_ALPHA = 0.25           # weight of each new sample on Acc_w EWMA

# -- DDA classification thresholds -------------------------------------------
# Hysteresis band at the classifier level: entering FRUSTRATION is easier than
# exiting, so a player that is just over the edge does not flicker back.
FRUSTRATION_ENTER_ACCW = 0.50
FRUSTRATION_EXIT_ACCW = 0.60
FRUSTRATION_ENTER_PF = 0.70
FRUSTRATION_EXIT_PF = 0.50

# Kept for backward compatibility with existing consumers/tests.
FRUSTRATION_ACCW_THRESHOLD = FRUSTRATION_ENTER_ACCW
FRUSTRATION_PF_THRESHOLD = FRUSTRATION_ENTER_PF

BOREDOM_ACCW_THRESHOLD = 0.90
BOREDOM_JITTER_EPSILON = 0.01
DDA_EVAL_INTERVAL_SEC = 5.0
HUD_SNAPSHOT_INTERVAL_SEC = 0.25  # cache refresh for HUD telemetry display

# -- DDA hysteresis -----------------------------------------------------------
HYSTERESIS_COOLDOWN_SEC = 6.0        # min seconds in a state before allowing transition
TRANSITION_SCORE_THRESHOLD = 2.0     # accumulated evidence needed to transition
TRANSITION_SCORE_DECAY = 0.5         # points subtracted when raw matches current
FAST_RECOVERY_HIT_STREAK = 8         # hits in a row that force exit from FRUSTRATION

# -- tempo ranges -------------------------------------------------------------
BASE_BPM = 120
TEMPO_MIN = 0.70
TEMPO_MAX = 1.35
TEMPO_FRUSTRATION = 0.85
TEMPO_BOREDOM = 1.10
TEMPO_FLOW = 1.00
TEMPO_STEP_LIMIT = 0.05  # max tempo change per DDA evaluation cycle

# -- note density ranges ------------------------------------------------------
DENSITY_MIN = 0.6
DENSITY_MAX = 1.4
DENSITY_FRUSTRATION = 0.8
DENSITY_BOREDOM = 1.2
DENSITY_FLOW = 1.0

# -- gameplay feel ------------------------------------------------------------
FALL_DURATION = 2.0     # seconds for a note to traverse the screen at tempo=1.0
HIT_Y_RATIO = 0.82      # hit-zone vertical position as fraction of screen height
HIT_ZONE_HEIGHT = 72     # pixel height of the hit-zone bar
NOTE_HEIGHT = 30
NOTE_MARGIN = 14         # horizontal padding inside each lane
MISS_GRACE_SEC = 0.18    # seconds after t_ideal before a note is auto-missed

# -- accent colors per emotional state ----------------------------------------
COLOR_FLOW = (40, 200, 160)   # teal
COLOR_COLD = (60, 140, 255)   # blue  (frustration)
COLOR_WARM = (255, 150, 40)   # amber (boredom)
COLOR_BG = (10, 10, 20)

# -- UI font sizes (points) --------------------------------------------------
FONT_HUD = 20
FONT_KEY = 28
FONT_FEED = 26

# -- spawner ------------------------------------------------------------------
SPAWNER_LEAD_TIME_SEC = 2.0   # grace period before first note arrives
SPAWNER_SEED: int | None = None  # set to a fixed int for reproducible runs
