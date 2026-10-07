"""Chaos levels and behavior timings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ChaosLevel:
    percent: int
    title: str
    walk_every: tuple[float, float] | None   # pause between walks, s; None = never walks
    nap_every: tuple[float, float]           # time awake before a nap, s
    prank_every: tuple[float, float] | None = None  # pause between pranks, s
    rare_bsod: bool = False                  # surprise BSOD once every few hours


CHAOS_LEVELS: tuple[ChaosLevel, ...] = (
    ChaosLevel(0, "Sleepy", None, (20, 40)),
    ChaosLevel(25, "Rare jokes", (15, 35), (6 * 60, 12 * 60), prank_every=(8 * 60, 15 * 60)),
    ChaosLevel(50, "Normal", (8, 20), (8 * 60, 15 * 60), prank_every=(3 * 60, 7 * 60)),
    ChaosLevel(100, "Apocalypse", (3, 9), (15 * 60, 25 * 60), prank_every=(45, 120), rare_bsod=True),
)
DEFAULT_CHAOS = 2

WALK_SPEED = 70.0            # px/s
NAP_DURATION = (60, 180)     # regular nap, s
NIGHT_NAP_EVERY = (120, 240)
NIGHT_NAP_DURATION = (300, 600)
NIGHT_HOURS = range(0, 6)
AWAY_SLEEP_AFTER = 300       # user hasn't touched mouse or keyboard: Floppy falls asleep
MANUAL_SLEEP = 15 * 60

RAGE_PER_CLICK = 0.1         # 10 quick clicks = BSOD
RAGE_COOLDOWN_DELAY = 0.8    # seconds without clicks before cooling down starts
RAGE_COOLDOWN_RATE = 0.35    # rage per second
RARE_BSOD_MEAN = 3 * 3600    # mean time between surprise BSODs at 100%
BSOD_TIMEOUT = 6.0

# --- physics (px, seconds) --------------------------------------------------
GRAVITY = 1800.0
AIR_DRAG = 0.25              # fraction of horizontal speed lost per second
BOUNCE_SPEED = 900.0         # hitting the floor faster than this bounces (up to twice)
BOUNCE_KEEP = 0.35
WALL_BOUNCE = 0.6
HARD_LANDING = 1150.0        # "that hurt"
MAX_THROW_SPEED = 3200.0
THROW_MIN_SPEED = 200.0      # slower counts as "just let go"
DROP_CHUTE_HEIGHT = 220.0    # let go higher than this above the floor: opens the parachute
CHUTE_SPEED = 85.0

# --- jumping onto windows ---------------------------------------------------
JUMP_CLEARANCE = 40.0        # arc apex above both start and target
JUMP_MAX_HEIGHT = 450.0
JUMP_MAX_DX = 260.0
JUMP_CHANCE = 0.5            # share of walks that become a jump onto the active window
JUMP_DOWN_CHANCE = 0.35      # while standing on a window: jump down to the floor

# --- pranks -----------------------------------------------------------------
MAX_PRANK_WINDOWS = 6
HYDRA_CHANCE = 0.3           # closed with the X: two mini windows pop out
PERFORMANCE_BSOD_CHANCE = 0.2
TUG_RESISTANCE = 0.25        # share of mouse movement that gets through towards Floppy
TUG_PUSH_SPEED = 30.0        # px/s Floppy pushes the window away from himself
TUG_TIRED_AFTER = 6.0        # s before he gets tired and gives up

# --- reactions to the user's hands ------------------------------------------
SPEECH_COOLDOWN = 1.5        # s between lines
FAST_DRAG_SPEED = 1800.0
SHAKE_SPEED = 400.0          # px/s; direction changes faster than this count as shaking
HELD_LONG = 3.0              # s held still before he starts grumbling
DIZZY_THRESHOLD = 1.0        # 1.0 = two spins in the air or a couple of seconds of shaking
DIZZY_DURATION = 2.6
ANNOY_THROWS = 4             # this many throws...
ANNOY_WINDOW = 60.0          # ...within this many seconds: he gets offended
REVENGE_CHANCE = 0.6         # and takes revenge with an error window
REVENGE_COOLDOWN = 120.0

# --- sneaking up on a frozen cursor ----------------------------------------
MOUSE_FROZEN = 15.0          # s the cursor must stay still before Floppy starts sneaking
CURSOR_STILL_RADIUS = 6.0    # px of jitter that still counts as "still"
SNEAK_SPEED = 26.0           # px/s on tiptoes
SNEAK_STOP_DISTANCE = 70.0   # stops this far from the cursor horizontally
SNEAK_BORED_AFTER = 60.0     # s of stalking before he loses interest
SNEAK_COOLDOWN = 45.0        # s before he may sneak again
SCARE_JERK = 10.0            # cursor moving this far from where it froze = "it's alive!"
SCARE_RADIUS = 450.0         # only panics if the cursor is this close
SCARED_RUN_SPEED = 260.0     # px/s while running for safety

# --- the prank menu ---------------------------------------------------------
# kind: (menu title, weight in random picks, needs the floor under him)
PRANKS: dict[str, tuple[str, float, bool]] = {
    "error": ("Error windows", 0.30, False),
    "progress": ("Fake progress bars", 0.14, False),
    "video": ("Video from behind the screen", 0.12, True),
    "defrag": ("Defragmenter", 0.11, False),
    "mines": ("Minesweeper", 0.11, False),
    "graffiti": ("Graffiti", 0.12, True),
    "clone": ("Clone (Ctrl+V)", 0.10, True),
}

# --- hauling a video window in from behind the screen edge ------------------
HAUL_REACH_TIMEOUT = 12.0    # s of rummaging behind the edge before he gives up
HAUL_MIN_REACH = 1.2         # s he rummages at least, for comedy
HAUL_SPEED = 150.0           # px/s while pulling
VIDEO_W, VIDEO_H = 960, 600  # real browser window size, logical px (capped by the screen)

# --- graffiti ---------------------------------------------------------------
SPRAY_SPEED = 80.0           # px/s along the wall while painting
GRAFFITI_LIFETIME = 150.0    # s before the paint starts to fade
GRAFFITI_FADE = 20.0
GRAFFITI_ABOVE_FLOOR = 76    # px from the floor to the bottom of the letters (nozzle height)

# --- the clone ---------------------------------------------------------------
CLONE_GAP = 130              # px between Floppy and his fresh copy
BIN_SPEED = 420.0            # px/s the Recycle Bin slides in and out

# --- Minesweeper ---------------------------------------------------------------
BLAST_RADIUS = 700           # px: closer than this, the explosion throws Floppy
