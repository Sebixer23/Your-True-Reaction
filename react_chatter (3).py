import math
import random
import time

import pygame


# ------------------------------------------------------------
# settings
# ------------------------------------------------------------
WIDTH, HEIGHT = 900, 900
CENTER = (WIDTH // 2, 440)
DIAMOND_SIZE = 230          # distance from the center to each tip of the big diamond

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
PANEL = (27, 30, 52)        # the diamond while you wait
LINE = (62, 68, 110)
TEXT = (236, 238, 248)
TEXT_DIM = (128, 134, 176)
DARK_TEXT = (20, 18, 30)

GO = (255, 196, 46)         # gold: CLICK this one
DECOY = (255, 134, 46)      # ember: never click this one
FAIL = (238, 70, 110)
DONE = (128, 112, 255)

# states that paint the diamond with a color
STATE_COLORS = {"go": GO, "decoy": DECOY, "fail": FAIL, "done": DONE}


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
# drawing helpers
# ------------------------------------------------------------
def mix(a, b, t):
    """Blend color a toward color b. t=0 gives a, t=1 gives b."""
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def diamond(center, size, angle=0):
    """Corner points of a square rotated by angle (degrees). angle 0 = diamond."""
    cx, cy = center
    points = []
    for i in range(4):
        a = math.radians(angle + 90 * i)
        points.append((cx + size * math.cos(a), cy + size * math.sin(a)))
    return points


def draw_text(screen, font, text, color, center):
    surface = font.render(text, True, color)
    screen.blit(surface, surface.get_rect(center=center))


def make_grid():
    """Faint dot grid, drawn once and reused every frame."""
    grid = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    step = 36
    for x in range(step // 2, WIDTH, step):
        for y in range(step // 2, HEIGHT, step):
            pygame.draw.rect(grid, (255, 255, 255, 20), (x - 1, y - 1, 2, 2))
    return grid.convert_alpha()


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
    for x, color, label in ((WIDTH // 2 - 95, GO, "CLICK"), (WIDTH // 2 + 25, DECOY, "AVOID")):
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
            pygame.draw.polygon(screen, GO, points)
            draw_text(screen, fonts["tiny"], str(round(times[i])), TEXT_DIM, (x, y + 34))
        else:
            pygame.draw.polygon(screen, outline, points, 2)


def draw(screen, game, fonts, grid, now):
    state = game.state
    elapsed = now - game.state_start
    color = STATE_COLORS.get(state)

    # background, tinted a little toward the current color
    bg = mix(BG, color, 0.13) if color else BG
    screen.fill(bg)
    screen.blit(grid, (0, 0))

    accent = mix(LINE, color, 0.6) if color else LINE
    draw_corners(screen, accent)
    draw_header(screen, fonts)

    # two thin squares slowly spinning behind the diamond
    pygame.draw.polygon(screen, mix(bg, accent, 0.75), diamond(CENTER, 270, now * 8), 2)
    pygame.draw.polygon(screen, mix(bg, accent, 0.45), diamond(CENTER, 300, -now * 5), 1)

    # the big diamond
    fill = color if color else PANEL
    edge = mix(fill, (255, 255, 255), 0.3) if color else LINE
    outer = diamond(CENTER, DIAMOND_SIZE)
    pygame.draw.polygon(screen, fill, outer)
    pygame.draw.aalines(screen, edge, True, outer)
    pygame.draw.polygon(screen, edge, diamond(CENTER, DIAMOND_SIZE - 20), 2)

    # what goes inside the diamond
    cx, cy = CENTER
    if state == "countdown":
        number = max(1, COUNTDOWN_SECONDS - int(elapsed))
        draw_text(screen, fonts["small"], "GET READY", TEXT_DIM, (cx, cy - 75))
        draw_text(screen, fonts["huge"], str(number), TEXT, (cx, cy + 8))

    elif state == "wait":
        draw_text(screen, fonts["big"], "Wait...", TEXT, (cx, cy))
        draw_text(screen, fonts["small"], f"{len(game.times) + 1} / {CLICKS_NEEDED}", TEXT_DIM, (cx, cy + 60))

    elif state == "hit":
        draw_text(screen, fonts["huge"], f"{round(game.times[-1])}", GO, (cx, cy - 5))
        draw_text(screen, fonts["small"], "ms", TEXT_DIM, (cx, cy + 62))

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
        hint = "click on GOLD only, EMBER sends you back to 0"
    draw_text(screen, fonts["tiny"], hint, TEXT_DIM, (WIDTH // 2, 862))


# ------------------------------------------------------------
# main loop
# ------------------------------------------------------------
def main():
    pygame.init()
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
    game = Game(time.perf_counter())

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.click(time.perf_counter())

        now = time.perf_counter()
        game.update(now)
        draw(screen, game, fonts, grid, now)
        pygame.display.flip()
        game.frame_shown(time.perf_counter())
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
