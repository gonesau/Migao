"""Global constants and thresholds for Armonía Adaptativa."""

# ── Display ────────────────────────────────────────────────────────────────────
SCREEN_WIDTH  = 1280
SCREEN_HEIGHT = 720
FPS           = 60
LANE_COUNT    = 4

# Key codes for D / F / J / K  (pygame integer constants, no import needed)
LANE_KEYS   = [100, 102, 106, 107]
LANE_LABELS = ["D", "F", "J", "K"]

# ── Emotion engine ─────────────────────────────────────────────────────────────
WINDOW_SIZE = 20
WTOL_MS     = 100.0   # timing-tolerance window in milliseconds
BETA        = 1.4
GAMMA       = 4.0

# ── DDA thresholds ─────────────────────────────────────────────────────────────
FRUSTRATION_ACCW_THRESHOLD = 0.50
FRUSTRATION_PF_THRESHOLD   = 0.70
BOREDOM_ACCW_THRESHOLD     = 0.90
BOREDOM_JITTER_EPSILON     = 0.01
DDA_EVAL_INTERVAL_SEC      = 5.0

# ── Tempo ──────────────────────────────────────────────────────────────────────
BASE_BPM          = 120
TEMPO_FRUSTRATION = 0.85
TEMPO_BOREDOM     = 1.10
TEMPO_FLOW        = 1.00

# ── Gameplay feel ──────────────────────────────────────────────────────────────
FALL_DURATION   = 2.0    # seconds for a note to fall at tempo_multiplier = 1.0
HIT_Y_RATIO     = 0.82   # hit-zone vertical position as fraction of screen height
HIT_ZONE_HEIGHT = 72     # pixel height of the hit-zone bar
NOTE_HEIGHT     = 30
NOTE_MARGIN     = 14     # horizontal padding inside each lane
MISS_GRACE_SEC  = 0.18   # seconds after t_ideal before a note is auto-missed

# ── Accent colors — one per emotional state (used by DDA + renderer) ───────────
COLOR_FLOW = (40, 200, 160)   # teal  – balanced / flow state
COLOR_COLD = (60, 140, 255)   # blue  – frustration
COLOR_WARM = (255, 150, 40)   # amber – boredom

# ── Base background ────────────────────────────────────────────────────────────
COLOR_BG = (10, 10, 20)

# ── UI font sizes (points) ─────────────────────────────────────────────────────
FONT_HUD  = 20
FONT_KEY  = 28
FONT_FEED = 26