import json
import math
import os
import random
import time

import pygame


# ------------------------------------------------------------
# settings
# ------------------------------------------------------------
WIDTH, HEIGHT = 900, 900
CENTER = (WIDTH // 2, 440)
DIAMOND_SIZE = 230          # distance from the center to each tip of the big diamond
COG_POS = (836, 64)         # the settings cog, top right corner

CLICKS_NEEDED = 5           # correct clicks needed for one full run
DECOY_CHANCE = 0.25         # same 1 in 4 odds as the old [4, 4, 4, 5] list
WAIT_RANGE = (0.4, 3.9)     # seconds of "Wait..." before a color shows up
DECOY_RANGE = (0.9, 1.5)    # how long the wrong color stays before it goes away
HIT_SHOW_TIME = 0.7         # how long your ms stays on screen after a good click
COUNTDOWN_SECONDS = 3
LOCKOUT = 0.6               # clicks are ignored this long on the fail/result screen
                            # so spam clicking can't skip right past them
FPS = 240


# ------------------------------------------------------------
# palette
# ------------------------------------------------------------
BG = (14, 16, 30)           # night navy
LINE = (62, 68, 110)
TEXT = (236, 238, 248)
TEXT_DIM = (128, 134, 176)
DARK_TEXT = (20, 18, 30)
MENU_BG = (21, 24, 43)
FAIL = (238, 70, 110)
DONE = (128, 112, 255)

# the only colors you can pick from the cog menu
PALETTE = {
    "RED": (238, 64, 64),
    "GREEN": (46, 204, 113),
    "BLUE": (52, 120, 246),
    "YELLOW": (255, 204, 41),
}
STANDBY = (27, 30, 52)          # the diamond while you wait (fixed)

DEFAULT_CHOICE = {"go": "YELLOW", "decoy": "RED"}
choice = dict(DEFAULT_CHOICE)   # which palette color CLICK (go) and AVOID (decoy) use
colors = {}                     # the actual RGB values the drawing code uses


def apply_choice():
    """Turn the picked color names into RGB values for drawing."""
    colors["standby"] = STANDBY
    colors["go"] = PALETTE[choice["go"]]
    colors["decoy"] = PALETTE[choice["decoy"]]


apply_choice()


# ------------------------------------------------------------
# saving your colors between launches
# ------------------------------------------------------------
def settings_path():
    if os.name == "nt":  # Windows: %APPDATA%\ReactChatter\settings.json
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "ReactChatter", "settings.json")
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "react-chatter", "settings.json")


def load_choice():
    try:
        with open(settings_path()) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return  # no file yet, or it's broken: just keep the defaults
    if not isinstance(saved, dict):
        return
    go, decoy = saved.get("go"), saved.get("decoy")
    # only accept two different colors from the palette (older versions saved RGB lists, those get ignored)
    if isinstance(go, str) and isinstance(decoy, str) and go in PALETTE and decoy in PALETTE and go != decoy:
        choice["go"], choice["decoy"] = go, decoy
        apply_choice()


def save_choice():
    try:
        os.makedirs(os.path.dirname(settings_path()), exist_ok=True)
        with open(settings_path(), "w") as f:
            json.dump(choice, f, indent=2)
    except OSError:
        pass  # can't save? the game still works, it just forgets on restart


# ------------------------------------------------------------
# game logic (no drawing in here)
# ------------------------------------------------------------
class Game:
    """
    The game is always in exactly one state:
      countdown -> wait -> go    -> hit -> wait ... (5 hits) -> done
                         -> decoy -> (ignored) -> wait
                         -> decoy -> (clicked) -> fail
               wait -> (clicked too early)     -> fail
    """

    def __init__(self, now):
        self.times = []         # reaction times in ms for this run
        self.lost = 0           # how many hits you lost on the last fail
        self.fail_reason = ""
        self.go_start = None
        self.wait_time = 0
        self.decoy_time = 0
        self.start_countdown(now)

    def set_state(self, state, now):
        self.state = state
        self.state_start = now

    def start_countdown(self, now):
        self.times = []
        self.set_state("countdown", now)

    def start_wait(self, now):
        self.wait_time = random.uniform(*WAIT_RANGE)
        self.set_state("wait", now)

    def fail(self, reason, now):
        self.fail_reason = reason
        self.lost = len(self.times)
        self.times = []
        self.set_state("fail", now)

    def update(self, now):
        """Move to the next state when the current one has run its time."""
        elapsed = now - self.state_start

        if self.state == "countdown" and elapsed >= COUNTDOWN_SECONDS:
            self.start_wait(now)

        elif self.state == "wait" and elapsed >= self.wait_time:
            if random.random() < DECOY_CHANCE:
                self.decoy_time = random.uniform(*DECOY_RANGE)
                self.set_state("decoy", now)
            else:
                self.go_start = None    # set in frame_shown(), once gold is really on screen
                self.set_state("go", now)

        elif self.state == "decoy" and elapsed >= self.decoy_time:
            self.start_wait(now)        # you held off, back to waiting

        elif self.state == "hit" and elapsed >= HIT_SHOW_TIME:
            if len(self.times) == CLICKS_NEEDED:
                self.set_state("done", now)
            else:
                self.start_wait(now)

    def frame_shown(self, now):
        """Called right after the screen updates. Starts the timer on the first gold frame."""
        if self.state == "go" and self.go_start is None:
            self.go_start = now

    def click(self, now):
        elapsed = now - self.state_start

        if self.state == "go" and self.go_start is not None:
            self.times.append((now - self.go_start) * 1000)
            self.set_state("hit", now)
        elif self.state == "decoy":
            self.fail("WRONG COLOR", now)
        elif self.state == "wait":
            self.fail("TOO EARLY", now)
        elif self.state in ("fail", "done") and elapsed >= LOCKOUT:
            self.start_countdown(now)
        # clicks during countdown and hit are ignored on purpose


# ------------------------------------------------------------
# color helpers
# ------------------------------------------------------------
def mix(a, b, t):
    """Blend color a toward color b. t=0 gives a, t=1 gives b."""
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def brightness(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def text_on(c):
    """Dark text on light colors, light text on dark colors."""
    return DARK_TEXT if brightness(c) > 140 else TEXT


def edge_for(c):
    """A thin outline color that shows up on top of c."""
    return mix(c, (0, 0, 0), 0.3) if brightness(c) > 140 else mix(c, (255, 255, 255), 0.25)


# ------------------------------------------------------------
# shape and text helpers
# ------------------------------------------------------------
def diamond(center, size, angle=0):
    """Corner points of a square rotated by angle (degrees). angle 0 = diamond."""
    cx, cy = center
    points = []
    for i in range(4):
        a = math.radians(angle + 90 * i)
        points.append((cx + size * math.cos(a), cy + size * math.sin(a)))
    return points


def chamfer(rect, cut):
    """A rectangle with its 4 corners cut off at 45 degrees."""
    x, y, w, h = rect
    return [(x + cut, y), (x + w - cut, y), (x + w, y + cut), (x + w, y + h - cut),
            (x + w - cut, y + h), (x + cut, y + h), (x, y + h - cut), (x, y + cut)]


def draw_text(screen, font, text, color, center):
    surface = font.render(text, True, color)
    screen.blit(surface, surface.get_rect(center=center))


def make_window_icon():
    """Small gold diamond on navy for the window/taskbar icon."""
    icon = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.rect(icon, BG, (0, 0, 64, 64), border_radius=12)
    pygame.draw.polygon(icon, LINE, diamond((32, 32), 27, 20), 2)
    pygame.draw.polygon(icon, PALETTE[DEFAULT_CHOICE["go"]], diamond((32, 32), 22))
    return icon


def make_grid():
    """Faint dot grid, drawn once and reused every frame."""
    grid = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    step = 36
    for x in range(step // 2, WIDTH, step):
        for y in range(step // 2, HEIGHT, step):
            pygame.draw.rect(grid, (255, 255, 255, 20), (x - 1, y - 1, 2, 2))
    return grid.convert_alpha()


# ------------------------------------------------------------
# the cog
# ------------------------------------------------------------
def over_cog(pos):
    return math.dist(pos, COG_POS) <= 26


def draw_cog(screen, now):
    hovered = over_cog(pygame.mouse.get_pos())
    color = TEXT if hovered else TEXT_DIM
    angle = now * 60 if hovered else 0    # spins while you hover it
    cx, cy = COG_POS

    points = []
    teeth = 8
    for i in range(teeth):
        a = angle + i * 360 / teeth
        for offset, radius in ((-13, 15), (-8, 21), (8, 21), (13, 15)):
            rad = math.radians(a + offset)
            points.append((cx + radius * math.cos(rad), cy + radius * math.sin(rad)))
    pygame.draw.polygon(screen, color, points)
    pygame.draw.circle(screen, color, COG_POS, 16)
    pygame.draw.circle(screen, BG, COG_POS, 7)


# ------------------------------------------------------------
# game screen
# ------------------------------------------------------------
def draw_corners(screen, color):
    margin, arm = 28, 46
    corners = (
        (margin, margin, 1, 1),
        (WIDTH - margin, margin, -1, 1),
        (margin, HEIGHT - margin, 1, -1),
        (WIDTH - margin, HEIGHT - margin, -1, -1),
    )
    for x, y, dx, dy in corners:
        pygame.draw.line(screen, color, (x, y), (x + arm * dx, y), 2)
        pygame.draw.line(screen, color, (x, y), (x, y + arm * dy), 2)


def draw_header(screen, fonts):
    draw_text(screen, fonts["small"], "R E A C T   C H A T T E R", TEXT_DIM, (WIDTH // 2, 60))

    # legend: which color to click and which to avoid
    y = 102
    for x, color, label in ((WIDTH // 2 - 95, colors["go"], "CLICK"), (WIDTH // 2 + 25, colors["decoy"], "AVOID")):
        pygame.draw.polygon(screen, color, diamond((x, y), 9))
        label_surface = fonts["tiny"].render(label, True, TEXT_DIM)
        screen.blit(label_surface, label_surface.get_rect(midleft=(x + 18, y + 1)))


def draw_pips(screen, fonts, times, outline):
    """5 small diamonds under the big one, filled in as you score hits."""
    gap = 100
    first_x = WIDTH // 2 - gap * (CLICKS_NEEDED - 1) / 2
    y = 785
    for i in range(CLICKS_NEEDED):
        x = first_x + gap * i
        points = diamond((x, y), 14)
        if i < len(times):
            pygame.draw.polygon(screen, colors["go"], points)
            draw_text(screen, fonts["tiny"], str(round(times[i])), TEXT_DIM, (x, y + 34))
        else:
            pygame.draw.polygon(screen, outline, points, 2)


def draw(screen, game, fonts, grid, now):
    state = game.state
    elapsed = now - game.state_start
    standby = colors["standby"]
    state_colors = {"go": colors["go"], "decoy": colors["decoy"], "fail": FAIL, "done": DONE}
    color = state_colors.get(state)

    # background, tinted a little toward the current color
    bg = mix(BG, color, 0.13) if color else mix(BG, standby, 0.10)
    screen.fill(bg)
    screen.blit(grid, (0, 0))

    accent = mix(LINE, color, 0.6) if color else LINE
    draw_corners(screen, accent)
    draw_header(screen, fonts)

    # two thin squares slowly spinning behind the diamond
    pygame.draw.polygon(screen, mix(bg, accent, 0.75), diamond(CENTER, 270, now * 8), 2)
    pygame.draw.polygon(screen, mix(bg, accent, 0.45), diamond(CENTER, 300, -now * 5), 1)

    # the big diamond
    fill = color if color else standby
    edge = mix(fill, (255, 255, 255), 0.3) if color else edge_for(standby)
    outer = diamond(CENTER, DIAMOND_SIZE)
    pygame.draw.polygon(screen, fill, outer)
    pygame.draw.aalines(screen, edge, True, outer)
    pygame.draw.polygon(screen, edge, diamond(CENTER, DIAMOND_SIZE - 20), 2)

    # text colors that stay readable on whatever standby color you picked
    on_standby = text_on(standby)
    dim_on_standby = mix(on_standby, standby, 0.45)

    # what goes inside the diamond
    cx, cy = CENTER
    if state == "countdown":
        number = max(1, COUNTDOWN_SECONDS - int(elapsed))
        draw_text(screen, fonts["small"], "GET READY", dim_on_standby, (cx, cy - 75))
        draw_text(screen, fonts["huge"], str(number), on_standby, (cx, cy + 8))

    elif state == "wait":
        draw_text(screen, fonts["big"], "Wait...", on_standby, (cx, cy))
        draw_text(screen, fonts["small"], f"{len(game.times) + 1} / {CLICKS_NEEDED}", dim_on_standby, (cx, cy + 60))

    elif state == "hit":
        # show the ms in the click color, unless that color is too close to standby to read
        readable = abs(brightness(colors["go"]) - brightness(standby)) > 60
        draw_text(screen, fonts["huge"], f"{round(game.times[-1])}", colors["go"] if readable else on_standby, (cx, cy - 5))
        draw_text(screen, fonts["small"], "ms", dim_on_standby, (cx, cy + 62))

    elif state == "fail":
        draw_text(screen, fonts["huge"], "FAIL!", DARK_TEXT, (cx, cy - 20))
        draw_text(screen, fonts["mid"], game.fail_reason, DARK_TEXT, (cx, cy + 55))
        if game.lost:
            draw_text(screen, fonts["small"], f"lost {game.lost} / {CLICKS_NEEDED}", DARK_TEXT, (cx, cy + 100))

    elif state == "done":
        average = sum(game.times) / len(game.times)
        draw_text(screen, fonts["small"], "AVERAGE", DARK_TEXT, (cx, cy - 85))
        draw_text(screen, fonts["huge"], f"{round(average)}", DARK_TEXT, (cx, cy - 10))
        draw_text(screen, fonts["small"], "ms", DARK_TEXT, (cx, cy + 50))
        best, worst = round(min(game.times)), round(max(game.times))
        draw_text(screen, fonts["small"], f"best {best}   worst {worst}", DARK_TEXT, (cx, cy + 95))

    # go and decoy show nothing inside: the color alone has to tell you

    draw_pips(screen, fonts, game.times, FAIL if state == "fail" else accent)

    # hint at the bottom
    if state in ("fail", "done"):
        hint = ""
        if elapsed >= LOCKOUT:
            hint = "click to start over" if state == "fail" else "click to play again"
    else:
        hint = f"only click {choice['go']}, {choice['decoy']} sends you back to 0"
    draw_text(screen, fonts["tiny"], hint, TEXT_DIM, (WIDTH // 2, 862))


# ------------------------------------------------------------
# color menu
# ------------------------------------------------------------
MENU_RECT = pygame.Rect(100, 140, 700, 590)
ROWS = (("go", "CLICK", 270), ("decoy", "AVOID", 400))     # slot, label, y position
SWATCH_X = (350, 460, 570, 680)                            # one per palette color
SWATCH_SIZE = 30
PREVIEW_RECT = pygame.Rect(250, 485, 400, 125)
DEFAULTS_BUTTON = pygame.Rect(230, 650, 200, 48)
DONE_BUTTON = pygame.Rect(470, 650, 200, 48)


def other_slot(slot):
    return "decoy" if slot == "go" else "go"


def swatch_at(pos):
    """Which (slot, color name) diamond is under pos, or None."""
    for slot, _, y in ROWS:
        for name, x in zip(PALETTE, SWATCH_X):
            if abs(pos[0] - x) + abs(pos[1] - y) <= SWATCH_SIZE + 6:   # inside the diamond
                return slot, name
    return None


class Menu:
    def __init__(self):
        self.is_open = False

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False
        save_choice()

    def handle(self, event):
        """Returns "close" when the menu should close."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "close"

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if over_cog(pos) or DONE_BUTTON.collidepoint(pos):
                return "close"
            if DEFAULTS_BUTTON.collidepoint(pos):
                choice.update(DEFAULT_CHOICE)
                apply_choice()
                return None
            hit = swatch_at(pos)
            if hit:
                slot, name = hit
                if choice[other_slot(slot)] != name:    # can't use the same color for both
                    choice[slot] = name
                    apply_choice()
        return None


def draw_button(screen, font, rect, label, mouse):
    hovered = rect.collidepoint(mouse)
    points = chamfer(rect, 10)
    pygame.draw.polygon(screen, mix(MENU_BG, LINE, 0.55 if hovered else 0.2), points)
    pygame.draw.polygon(screen, TEXT_DIM if hovered else LINE, points, 2)
    draw_text(screen, font, label, TEXT, rect.center)


def draw_menu(screen, fonts, menu):
    mouse = pygame.mouse.get_pos()
    hovered = swatch_at(mouse)

    # dim the game behind the menu
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((*BG, 225))
    screen.blit(overlay, (0, 0))

    panel = chamfer(MENU_RECT, 30)
    pygame.draw.polygon(screen, MENU_BG, panel)
    pygame.draw.polygon(screen, LINE, panel, 2)
    draw_text(screen, fonts["small"], "C O L O R S", TEXT_DIM, (WIDTH // 2, 185))

    # one row of 4 colors for CLICK, one for AVOID
    for slot, label, y in ROWS:
        row_label = fonts["small"].render(label, True, TEXT)
        screen.blit(row_label, row_label.get_rect(midleft=(170, y)))
        taken = choice[other_slot(slot)]

        for name, x in zip(PALETTE, SWATCH_X):
            color = PALETTE[name]
            points = diamond((x, y), SWATCH_SIZE)
            ring = diamond((x, y), SWATCH_SIZE + 14, 45)

            if name == taken:
                # the other row is using this one: dimmed and crossed out, can't be picked
                pygame.draw.polygon(screen, mix(MENU_BG, color, 0.25), points)
                pygame.draw.line(screen, mix(MENU_BG, TEXT_DIM, 0.6), (x - 20, y + 20), (x + 20, y - 20), 3)
                name_color = mix(MENU_BG, TEXT_DIM, 0.45)
            elif name == choice[slot]:
                pygame.draw.polygon(screen, color, points)
                pygame.draw.polygon(screen, TEXT, ring, 2)
                name_color = TEXT
            else:
                pygame.draw.polygon(screen, color, points)
                if hovered == (slot, name):
                    pygame.draw.polygon(screen, TEXT_DIM, ring, 1)
                name_color = TEXT_DIM

            draw_text(screen, fonts["tiny"], name, name_color, (x, y + 52))

    # preview: click and avoid side by side on the standby color
    standby = colors["standby"]
    pygame.draw.polygon(screen, standby, chamfer(PREVIEW_RECT, 14))
    pygame.draw.polygon(screen, edge_for(standby), chamfer(PREVIEW_RECT, 14), 2)
    label_color = mix(text_on(standby), standby, 0.3)
    for x, key, label in ((WIDTH // 2 - 70, "go", "CLICK"), (WIDTH // 2 + 70, "decoy", "AVOID")):
        pygame.draw.polygon(screen, colors[key], diamond((x, PREVIEW_RECT.top + 50), 32))
        draw_text(screen, fonts["tiny"], label, label_color, (x, PREVIEW_RECT.top + 104))

    draw_button(screen, fonts["small"], DEFAULTS_BUTTON, "DEFAULTS", mouse)
    draw_button(screen, fonts["small"], DONE_BUTTON, "DONE", mouse)


# ------------------------------------------------------------
# main loop
# ------------------------------------------------------------
def main():
    pygame.init()
    pygame.display.set_icon(make_window_icon())
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("React Chatter")
    clock = pygame.time.Clock()

    fonts = {
        "huge": pygame.font.Font(None, 140),
        "big": pygame.font.Font(None, 72),
        "mid": pygame.font.Font(None, 44),
        "small": pygame.font.Font(None, 30),
        "tiny": pygame.font.Font(None, 24),
    }
    grid = make_grid()
    load_choice()
    game = Game(time.perf_counter())
    menu = Menu()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif menu.is_open:
                if menu.handle(event) == "close":
                    menu.close()
                    game.start_countdown(time.perf_counter())   # fresh run with the new colors
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if over_cog(event.pos):
                    menu.open()
                    game.start_countdown(time.perf_counter())   # opening the menu ends the current run
                else:
                    game.click(time.perf_counter())

        now = time.perf_counter()
        if not menu.is_open:
            game.update(now)
        draw(screen, game, fonts, grid, now)
        if menu.is_open:
            draw_menu(screen, fonts, menu)
        draw_cog(screen, now)
        pygame.display.flip()
        if not menu.is_open:
            game.frame_shown(time.perf_counter())
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
