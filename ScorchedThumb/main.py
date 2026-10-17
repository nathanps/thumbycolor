# Scorched Thumb - a Scorched Earth style artillery game for the Thumby Color
import engine_main

import engine
import engine_io
import engine_draw
import engine_audio
import engine_save
from engine_resources import WaveSoundResource, ToneSoundResource

import array
import math
import random

# ---------------------------------------------------------------------------
# World layout
# ---------------------------------------------------------------------------
SW = const(128)         # Screen width
W = const(256)          # World width (the camera scrolls across it)
H = const(128)          # World height
HUD_H = const(17)       # Rows covered by the HUD at the top of the screen
BEDROCK = const(126)    # Rows from here down can't be destroyed
TOP_MIN = const(40)     # Highest the generated ground can reach

# Terrain values (one byte per world pixel)
T_AIR = const(0)
T_DIRT = const(1)
T_SPECK = const(2)      # Darker dirt for texture
T_SCORCH = const(3)     # Burnt dirt around craters
T_CRUST = const(4)      # Lighter top layer of the original ground

# Physics, in pixels per frame
SUB = const(4)          # Shot sub-steps per frame so fast shots can't skip through thin ground
GRAVITY = 0.05
V_MAX = 4.4             # Launch speed at full power
WIND_K = 0.0008         # Sideways acceleration per point of wind
MAX_WIND = const(15)

# Weapons: (name, blast radius, damage, kind, price, bundle size, shop description)
K_MISSILE = const(0)
K_MIRV = const(1)       # Splits into five warheads at the top of its arc
K_DIRT = const(2)       # Adds a ball of dirt instead of blowing a hole
K_ROLLER = const(3)     # Rolls downhill after landing until it stops or hits a tank
K_FUNKY = const(4)      # Bursts into bomblets that scatter in all directions
K_TRACER = const(5)     # No explosion, just shows the path
K_NAPALM = const(6)     # Splashes burning fuel that runs downhill

WEAPONS = (
    ("BABY MISSILE", 6, 35, K_MISSILE, 0, 0, "SMALL BUT NEVER RUNS OUT"),
    ("MISSILE", 9, 55, K_MISSILE, 1500, 5, "A BIGGER BLAST"),
    ("BIG BOMB", 15, 80, K_MISSILE, 4000, 2, "A HUGE BLAST"),
    ("MIRV", 7, 40, K_MIRV, 6000, 2, "SPLITS INTO 5 AT THE TOP"),
    ("FUNKY BOMB", 10, 45, K_FUNKY, 7000, 2, "BURSTS INTO MINI BOMBS"),
    ("ROLLER", 9, 55, K_ROLLER, 3000, 3, "ROLLS DOWNHILL INTO TANKS"),
    ("DIRT BOMB", 13, 0, K_DIRT, 2000, 3, "BURIES THINGS IN DIRT"),
    ("TRACER", 0, 0, K_TRACER, 300, 10, "SHOWS THE PATH, NO DAMAGE"),
    ("NAPALM", 4, 10, K_NAPALM, 5000, 2, "FIRE THAT FLOWS DOWNHILL"),
)
START_INV = (-1, 0, 0, 0, 0, 0, 0, 5, 0)    # -1 means unlimited
FUNKY_BITS = const(6)
NAPALM_DROPS = const(36)   # Burning drops one napalm splashes out
FIRE_TICK = const(15)      # Frames between fire damage checks

# Items: (name, price, bundle size, shop description)
IT_CHUTE = const(0)     # Opens automatically when a tank falls, so no fall damage
IT_SHIELD = const(1)    # One is switched on at the start of each round
IT_FUEL = const(2)      # Spent driving with LB/RB
ITEMS = (
    ("PARACHUTE", 1500, 3, "NO DAMAGE FROM FALLING"),
    ("SHIELD", 3000, 2, "SOAKS UP 60 DAMAGE A ROUND"),
    ("FUEL", 500, 25, "DRIVE AROUND WITH LB/RB"),
)
START_ITEMS = (0, 0, 30)
SHIELD_HP = const(60)
MAX_DEBRIS = const(80)

START_MONEY = const(5000)
MONEY_PER_HP = const(30)
KILL_BONUS = const(1500)
ROUND_BONUS = const(2500)  # For the winner
ROUND_PAY = const(1000)    # For everyone, so the losers can buy something too

# What the shop sells: (0, weapon index) or (1, item index)
STORE = tuple([(0, i) for i in range(1, len(WEAPONS))] + [(1, i) for i in range(len(ITEMS))])
# What the CPU likes to buy (repeats make it more likely)
CPU_WISH = ((0, 1), (0, 1), (0, 2), (0, 3), (0, 4), (0, 8), (1, IT_SHIELD), (1, IT_CHUTE))
SHOP_ROWS = const(9)       # Rows that fit on the shop screen

FALL_SAFE = const(3)    # Pixels a tank can drop without getting hurt

ROUND_OPTS = (1, 3, 5, 10)
NAMES = ("NATHAN", "HELEN", "KAYLEE", "LUKE", "MOCHI",
         "BLASTO", "BOOMER", "ZAPPY", "TANKY", "DUSTY")
TYPE_LABELS = ("HUMAN", "CPU:E", "CPU:M", "CPU:H")

# How sloppy each CPU level's first shot at a target is: (angle error, power error,
# how much the error shrinks each turn it keeps shooting at the same target,
# chance of a special weapon)
CPU_SKILL = ((0, 0, 1, 0), (9, 130, 0.8, 0.2), (4, 50, 0.65, 0.5), (1, 12, 0.5, 0.7))

# Game states
ST_TITLE = const(0)
ST_SETUP = const(1)
ST_TURN = const(2)      # "NAME'S TURN" banner while the camera pans over
ST_AIM = const(3)
ST_FLY = const(4)
ST_BOOM = const(5)      # Explosions playing out
ST_SETTLE = const(6)    # Loose dirt and tanks falling
ST_ROUND_END = const(7)
ST_GAME_END = const(8)
ST_SHOP = const(9)


def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def lerp3(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


C_BLACK = const(0)
C_WHITE = const(0xFFFF)
C_GREY = rgb(140, 140, 150)
C_DARK = rgb(50, 50, 60)
C_HUD = rgb(16, 16, 28)
C_MAP = rgb(32, 32, 48)
C_TREAD = rgb(40, 40, 45)
C_WHEEL = rgb(110, 110, 120)
C_BARREL = rgb(210, 210, 220)
C_WRECK = rgb(55, 50, 45)
C_HP_BG = rgb(90, 20, 20)
C_HP = rgb(60, 230, 80)
C_HP_LOW = rgb(250, 200, 40)
C_GOLD = rgb(255, 200, 40)
C_ORANGE = rgb(255, 120, 30)
C_SEL = rgb(40, 50, 110)
C_SETUP_BG = rgb(10, 12, 30)
C_SHIELD = rgb(120, 230, 255)
C_RED = rgb(240, 70, 60)

PLAYER_COLORS = (rgb(255, 70, 60), rgb(70, 160, 255),
                 rgb(255, 215, 40), rgb(220, 90, 255))

FIRE_COLORS = (C_WHITE, rgb(255, 240, 120), rgb(255, 170, 40),
               rgb(240, 80, 20), rgb(150, 30, 10))
DIRT_COLORS = (rgb(200, 160, 100), rgb(160, 120, 70), rgb(120, 85, 50),
               rgb(90, 60, 35), rgb(60, 40, 25))

# Sky top, sky bottom, ground top, ground bottom
THEMES = (
    ((60, 120, 220), (170, 215, 255), (100, 180, 60), (70, 45, 25)),       # Day
    ((25, 15, 60), (245, 130, 70), (150, 105, 60), (55, 30, 20)),          # Dusk
    ((5, 5, 25), (35, 45, 100), (90, 95, 125), (25, 25, 40)),              # Night
    ((235, 175, 100), (255, 235, 190), (225, 180, 100), (140, 80, 35)),    # Desert
    ((50, 15, 20), (200, 95, 55), (185, 75, 40), (70, 25, 15)),            # Mars
    ((150, 200, 235), (235, 245, 255), (235, 240, 250), (110, 130, 160)),  # Snow
)

# ---------------------------------------------------------------------------
# Buffers
# ---------------------------------------------------------------------------
terrain = bytearray(W * H)          # One terrain value per world pixel
heights = bytearray(W)              # Surface height per column, used while generating
palette = bytearray(5 * 128 * 2)    # RGB565 colour for each terrain value on each row
rng = bytearray(4)                  # Random state for the viper functions
sim_ax = array.array("i", [0])      # Wind for sim_shot, in 16.16 fixed point
MAX_TRAIL = const(700)
trail_x = array.array("H", [0] * MAX_TRAIL)   # Shot path points, x + 8
trail_y = array.array("H", [0] * MAX_TRAIL)   # and y + 512, so they stay positive

_seed = random.getrandbits(30)
for _i in range(4):
    rng[_i] = (_seed >> (8 * _i)) & 0xFF

# 3x5 pixel font. Each glyph is five rows, each row a digit whose 3 bits are the pixels
_GLYPHS = {
    ' ': "00000", '0': "75557", '1': "26227", '2': "71747", '3': "71317",
    '4': "55711", '5': "74717", '6': "74757", '7': "71122", '8': "75757",
    '9': "75717", 'A': "25755", 'B': "65656", 'C': "34443", 'D': "65556",
    'E': "74647", 'F': "74644", 'G': "34553", 'H': "55755", 'I': "72227",
    'J': "11152", 'K': "55655", 'L': "44447", 'M': "57755", 'N': "65555",
    'O': "25552", 'P': "65644", 'Q': "25563", 'R': "65655", 'S': "34216",
    'T': "72222", 'U': "55557", 'V': "55552", 'W': "55775", 'X': "55255",
    'Y': "55222", 'Z': "71247", '-': "00700", '+': "02720", '$': "36236",
    '<': "12421", '>': "42124", ':': "02020", '.': "00002", ',': "00024",
    '!': "22202", '?': "61202", '/': "11244", '%': "51245", "'": "22000",
    '(': "12221", ')': "42224", '=': "07070", '*': "05250", '#': "57575",
    '^': "25000",
}
FONT = bytearray(96 * 5)
for _ch, _rows in _GLYPHS.items():
    for _k in range(5):
        FONT[(ord(_ch) - 32) * 5 + _k] = ord(_rows[_k]) - 48
del _GLYPHS


# ---------------------------------------------------------------------------
# Fast terrain functions
# ---------------------------------------------------------------------------
@micropython.viper
def render_world(cam: int, oy: int):
    """Draw the 128 world columns starting at cam. oy shifts the picture for screen shake."""
    buf = ptr16(engine_draw.back_fb_data())
    t = ptr8(terrain)
    pal = ptr16(palette)
    sy = 0
    while sy < 128:
        wy = sy + oy
        if wy < 0:
            wy = 0
        if wy > 127:
            wy = 127
        row = wy * 256 + cam
        o = sy * 128
        sx = 0
        while sx < 128:
            buf[o + sx] = pal[(t[row + sx] << 7) + wy]
            sx += 1
        sy += 1


@micropython.viper
def fill_terrain():
    """Fill the world from the heights array, with speckles for texture."""
    t = ptr8(terrain)
    h = ptr8(heights)
    rs = ptr32(rng)
    s = rs[0]
    x = 0
    while x < 256:
        top = h[x]
        y = 0
        while y < 128:
            v = 0
            if y >= top or y >= 126:
                s = (s * 1664525 + 1013904223) & 0x3fffffff
                v = 1
                if y < top + 2:
                    v = 4
                elif ((s >> 16) & 7) == 0:
                    v = 2
            t[y * 256 + x] = v
            y += 1
        x += 1
    rs[0] = s


@micropython.viper
def blast_terrain(cx: int, cy: int, r: int, mode: int):
    """mode 0 blows a crater with a scorched rim, mode 1 adds a ball of dirt."""
    t = ptr8(terrain)
    rs = ptr32(rng)
    s = rs[0]
    edge = r + 2
    x0 = cx - edge
    if x0 < 0:
        x0 = 0
    x1 = cx + edge
    if x1 > 255:
        x1 = 255
    y0 = cy - edge
    if y0 < 0:
        y0 = 0
    y1 = cy + edge
    if y1 > 125:
        y1 = 125
    rr = r * r
    ee = edge * edge
    y = y0
    while y <= y1:
        dy = y - cy
        x = x0
        while x <= x1:
            dx = x - cx
            d2 = dx * dx + dy * dy
            i = y * 256 + x
            s = (s * 1664525 + 1013904223) & 0x3fffffff
            j = (s >> 16) & 7
            if mode == 0:
                # Jitter the edge so craters aren't perfect circles
                if d2 <= rr - j:
                    t[i] = 0
                elif d2 <= ee:
                    if t[i] != 0:
                        t[i] = 3
            else:
                if d2 <= rr and t[i] == 0:
                    if j == 0:
                        t[i] = 2
                    else:
                        t[i] = 1
            x += 1
        y += 1
    rs[0] = s


@micropython.viper
def settle_dirt(x0: int, x1: int) -> int:
    """Drop every unsupported dirt pixel in columns x0..x1 by one row. Returns how many moved."""
    t = ptr8(terrain)
    if x0 < 0:
        x0 = 0
    if x1 > 255:
        x1 = 255
    moved = 0
    x = x0
    while x <= x1:
        # Bottom up, so a floating chunk falls together
        y = 124
        while y >= 0:
            i = y * 256 + x
            v = t[i]
            if v != 0 and t[i + 256] == 0:
                t[i + 256] = v
                t[i] = 0
                moved += 1
            y -= 1
        x += 1
    return moved


@micropython.viper
def ground_below(x: int, y: int) -> int:
    """First solid row at or below y in column x (128 if none, or off the world)."""
    if x < 0 or x > 255:
        return 128
    t = ptr8(terrain)
    if y < 0:
        y = 0
    while y < 128:
        if t[y * 256 + x] != 0:
            return y
        y += 1
    return 128


@micropython.viper
def draw_trail(n: int, cam: int, oy: int, color: int):
    """Plot the first n points of the shot trail."""
    buf = ptr16(engine_draw.back_fb_data())
    tx = ptr16(trail_x)
    ty = ptr16(trail_y)
    i = 0
    while i < n:
        x = tx[i] - 8 - cam
        y = ty[i] - 512 - oy
        if x >= 0 and x < 128 and y >= 0 and y < 128:
            buf[y * 128 + x] = color
        i += 1


@micropython.viper
def dim_screen():
    """Halve the brightness of the whole screen, for overlays."""
    buf = ptr16(engine_draw.back_fb_data())
    i = 0
    while i < 16384:
        buf[i] = (buf[i] >> 1) & 0x7BEF
        i += 1


@micropython.viper
def _tiny(s, x: int, y: int, color: int):
    buf = ptr16(engine_draw.back_fb_data())
    f = ptr8(FONT)
    p = ptr8(s)
    n = int(len(s))
    i = 0
    while i < n:
        c = p[i] - 32
        if c >= 0 and c < 96:
            g = c * 5
            ry = 0
            while ry < 5:
                py = y + ry
                if py >= 0 and py < 128:
                    bits = f[g + ry]
                    rx = 0
                    while rx < 3:
                        px = x + rx
                        if (bits >> (2 - rx)) & 1 and px >= 0 and px < 128:
                            buf[py * 128 + px] = color
                        rx += 1
                ry += 1
        x += 4
        i += 1


def tiny(s, x, y, color):
    """Draw text in the small 3x5 font."""
    _tiny(str(s).upper().encode(), x, y, color)


def tiny_center(s, y, color):
    s = str(s)
    tiny(s, (SW - len(s) * 4 + 1) // 2, y, color)


def text_center(fb, s, y, color):
    """Draw text in the 8x8 font with a drop shadow, centered."""
    x = (SW - len(s) * 8) // 2
    fb.text(s, x + 1, y + 1, C_BLACK)
    fb.text(s, x, y, color)


def big_text(fb, s, x, y, color, scale):
    """The 3x5 font blown up into chunky blocks, for titles."""
    for ch in s:
        c = ord(ch) - 32
        if 0 <= c < 96:
            g = c * 5
            for ry in range(5):
                bits = FONT[g + ry]
                for rx in range(3):
                    if (bits >> (2 - rx)) & 1:
                        fb.fill_rect(x + rx * scale, y + ry * scale, scale, scale, color)
        x += 4 * scale


def big_center(fb, s, y, color, shadow, scale):
    x = (SW - len(s) * 4 * scale + scale) // 2
    big_text(fb, s, x + 1, y + 1, shadow, scale)
    big_text(fb, s, x, y, color, scale)


# ---------------------------------------------------------------------------
# Terrain generation
# ---------------------------------------------------------------------------
def build_palette(theme):
    sky_top, sky_bot, dirt_top, dirt_bot = theme
    for y in range(128):
        sky = lerp3(sky_top, sky_bot, y / 127)
        f = (y - TOP_MIN) / (BEDROCK - TOP_MIN)
        f = 0 if f < 0 else (1 if f > 1 else f)
        dirt = lerp3(dirt_top, dirt_bot, f)
        speck = (dirt[0] * 4 // 5, dirt[1] * 4 // 5, dirt[2] * 4 // 5)
        scorch = lerp3(dirt, (25, 18, 12), 0.7)
        crust = lerp3(dirt, (255, 255, 230), 0.3)
        for v, c in ((T_AIR, sky), (T_DIRT, dirt), (T_SPECK, speck), (T_SCORCH, scorch),
                     (T_CRUST, crust)):
            col = rgb(c[0], c[1], c[2])
            i = (v * 128 + y) * 2
            palette[i] = col & 0xFF
            palette[i + 1] = col >> 8


# Wave sets per landscape style: (amplitude, min cycles, max cycles) across the world
STYLES = (
    ((16, 0.8, 1.6), (6, 2, 4), (2, 6, 10)),      # Rolling hills
    ((26, 1, 2), (12, 2.5, 4), (4, 6, 9)),        # Mountains
    ((6, 0.5, 1.5), (3, 2, 4), (1.5, 6, 10)),     # Plains
)


def gen_heights():
    style = STYLES[random.randrange(len(STYLES))]
    base = random.randint(72, 96)
    waves = []
    for amp, lo, hi in style:
        freq = random.uniform(lo, hi) * 2 * math.pi / W
        waves.append((amp, freq, random.uniform(0, 2 * math.pi)))
    noise = 0
    for x in range(W):
        noise = noise * 0.95 + random.uniform(-0.6, 0.6)
        h = base + noise
        for amp, freq, phase in waves:
            h += amp * math.sin(freq * x + phase)
        h = int(h)
        heights[x] = TOP_MIN if h < TOP_MIN else (BEDROCK - 6 if h > BEDROCK - 6 else h)


def new_landscape(players):
    """Make fresh terrain for a round and drop the tanks onto flat pads."""
    build_palette(THEMES[random.randrange(len(THEMES))])
    gen_heights()
    n = len(players)
    if n:
        slots = []
        for i in range(n):
            x = int((i + 0.5) * W / n) + random.randint(-14, 14)
            slots.append(8 if x < 8 else (W - 9 if x > W - 9 else x))
        # Shuffle so nobody always starts on the same side
        for i in range(n - 1, 0, -1):
            j = random.randrange(i + 1)
            slots[i], slots[j] = slots[j], slots[i]
        for i, p in enumerate(players):
            p.x = slots[i]
            h = heights[p.x]
            for c in range(p.x - 4, p.x + 5):
                if 0 <= c < W:
                    heights[c] = h
    fill_terrain()
    for p in players:
        p.y = heights[p.x]
        p.angle = 60 if p.x < W // 2 else 120


# ---------------------------------------------------------------------------
# Sound
# ---------------------------------------------------------------------------
class Sound:
    # Setting a tone's frequency fades it out and back in (about 9ms), and a tone's
    # clock only resets when it's created. So the whistle is retuned only now and
    # then, and every blip or whistle gets a fresh tone.
    def __init__(self):
        self.boom = None
        self.whistle_tone = None
        self.whistling = False
        self.whistle_hz = 0
        self.whistle_wait = 0
        self.blip_frames = 0
        try:
            self.boom = WaveSoundResource("boom.wav")
        except Exception:
            pass

    def explode(self):
        if self.boom is not None:
            try:
                engine_audio.play(self.boom, 0, False)
            except Exception:
                pass

    def tone(self, freq, channel, gain):
        try:
            engine_audio.stop(channel)
            t = ToneSoundResource()
            t.frequency = freq
            ch = engine_audio.play(t, channel, True)
            ch.gain = gain
            return t
        except Exception:
            return None

    def whistle(self, freq):
        """Falling-shell whistle that follows the shot."""
        if not self.whistling:
            self.whistle_tone = self.tone(freq, 1, 0.12)
            self.whistling = True
            self.whistle_hz = freq
            self.whistle_wait = 5
            return
        self.whistle_wait -= 1
        if self.whistle_wait <= 0 and abs(freq - self.whistle_hz) >= 40 and self.whistle_tone:
            try:
                self.whistle_tone.frequency = freq
            except Exception:
                pass
            self.whistle_hz = freq
            self.whistle_wait = 5

    def whistle_stop(self):
        if self.whistling:
            self.whistling = False
            self.whistle_tone = None
            try:
                engine_audio.stop(1)
            except Exception:
                pass

    def blip(self, freq, frames=3):
        self.tone(freq, 2, 0.2)
        self.blip_frames = frames

    def tick(self):
        if self.blip_frames > 0:
            self.blip_frames -= 1
            if self.blip_frames == 0:
                try:
                    engine_audio.stop(2)
                except Exception:
                    pass


sound = Sound()


# ---------------------------------------------------------------------------
# Players, shots and explosions
# ---------------------------------------------------------------------------
class Player:
    def __init__(self, slot, name, ctype):
        self.slot = slot
        self.name = name
        self.ctype = ctype          # 0 human, 1-3 CPU easy/medium/hard
        self.color = PLAYER_COLORS[slot]
        self.wins = 0
        self.money = START_MONEY
        self.kills = 0
        self.x = 0
        self.y = 0                  # Row of the ground the tank sits on
        self.angle = 60             # Degrees: 0 points right, 90 up, 180 left
        self.power = 500            # 0-1000, capped lower as the tank gets damaged
        self.hp = 100
        self.alive = True
        self.fall = 0
        self.flash = 0
        self.inv = list(START_INV)
        self.items = list(START_ITEMS)
        self.shield = 0             # Shield strength left this round
        self.chute = False          # Parachute open while falling
        self.wsel = 0
        self.ai_angle = 60
        self.ai_power = 500
        self.ai_target = None       # Who the CPU shot at last turn
        self.ai_streak = 0          # Turns in a row it has aimed at them

    def is_cpu(self):
        return self.ctype > 0

    def max_power(self):
        # Damage weakens the gun a little, but never so much it can't reach across the map
        if G.sudden:
            return 1000
        return 1000 - (100 - self.hp) * 3

    def new_round(self):
        self.hp = 100
        self.alive = True
        self.fall = 0
        self.flash = 0
        self.chute = False
        self.shield = 0
        if self.items[IT_SHIELD] > 0:
            self.items[IT_SHIELD] -= 1
            self.shield = SHIELD_HP
        if self.inv[self.wsel] == 0:
            self.wsel = 0
        self.ai_target = None
        self.ai_streak = 0

    def next_weapon(self):
        i = self.wsel
        for _ in range(len(WEAPONS)):
            i = (i + 1) % len(WEAPONS)
            if self.inv[i] != 0:
                self.wsel = i
                return

    def barrel_tip(self, angle, length):
        a = math.radians(angle)
        return self.x + math.cos(a) * length, self.y - 5 - math.sin(a) * length


class Shot:
    def __init__(self, x, y, vx, vy, owner, weapon):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.owner = owner
        self.weapon = weapon
        w = WEAPONS[weapon]
        self.radius = w[1]
        self.damage = w[2]
        self.kind = w[3]
        self.age = 0
        self.split = False          # MIRV warheads that already split (or are children)
        self.rolling = False
        self.rdir = 1
        self.speed = 0
        self.rtime = 0


class Blast:
    def __init__(self, x, y, r, dirt):
        self.x = x
        self.y = y
        self.r = r
        self.dirt = dirt
        self.t = 0
        self.dur = 14 + r

    def draw(self, fb, cam, oy):
        f = self.t / self.dur
        if f < 0.35:
            rad = self.r * f / 0.35
        elif f > 0.7:
            rad = self.r * (1 - f) / 0.3
        else:
            rad = self.r
        rad = int(rad + 0.5)
        if rad < 1:
            return
        colors = DIRT_COLORS if self.dirt else FIRE_COLORS
        ci = int(f * 5)
        ci = 4 if ci > 4 else ci
        x = self.x - cam
        y = self.y - oy
        fb.ellipse(x, y, rad, rad, colors[ci], True)
        if rad > 3 and ci < 4:
            fb.ellipse(x, y, rad * 2 // 3, rad * 2 // 3, colors[ci - 1 if ci else 0], True)


class Game:
    def __init__(self):
        self.state = ST_TITLE
        self.timer = 0
        self.frame = 0
        self.players = []
        self.turn = 0
        self.round_no = 0
        self.rounds = 1
        self.wind = 0
        self.cam = 64.0
        self.pan = 0
        self.shake = 0
        self.shots = []
        self.blasts = []
        self.dying = []             # Tanks waiting to blow up
        self.popups = []            # Floating damage numbers: [x, y, text, frames]
        self.debris = []            # Flying bits from explosions: [x, y, vx, vy, frames, color]
        self.fire = []              # Burning napalm drops: [x, y, frames left]
        self.fire_owner = None
        self.fire_t = 0
        self.trail_n = 0            # Points in trail_x/trail_y from this turn's shots
        self.trail_color = C_WHITE
        self.dx0 = W                # Columns where dirt may need to fall
        self.dx1 = -1
        self.quiet = 0
        self.ai = None
        self.ai_peek = 60
        self.ai_wait = 0
        self.paused = False
        self.winner = None
        self.panned = False
        self.b_armed = False
        self.turn_count = 0         # Turns taken so far this round
        self.calm = 0               # Turns in a row where nobody got hurt
        self.sudden = False         # Sudden death: full power for everyone to end a stalemate
        self.held = [0] * 4         # Frames LEFT, RIGHT, UP, DOWN have been held
        self.drive_t = 0
        self.sel = 0                # Setup or shop menu row
        self.shop_top = 0           # First shop row on screen
        self.shop_queue = []        # Human players still to shop
        self.shop_msg = 0           # Frames to show "not enough money"


G = Game()

settings = {"n": 2, "r": 1, "aim": 1, "names": [0, 1, 2, 3], "types": [0, 2, 2, 2]}

engine_save._init_saves_dir("Saves/Games/ScorchedThumb")
engine_save.set_location("save")


def load_settings():
    try:
        settings["n"] = int(engine_save.load("n", 2))
        settings["r"] = int(engine_save.load("r", 1))
        settings["aim"] = int(engine_save.load("aim", 1))
        for i in range(4):
            settings["names"][i] = int(engine_save.load("nm" + str(i), i))
            settings["types"][i] = int(engine_save.load("ty" + str(i), 0 if i == 0 else 2))
    except Exception:
        pass
    settings["n"] = min(4, max(2, settings["n"]))
    settings["r"] = min(len(ROUND_OPTS) - 1, max(0, settings["r"]))
    settings["aim"] = 1 if settings["aim"] else 0
    for i in range(4):
        settings["names"][i] %= len(NAMES)
        settings["types"][i] %= len(TYPE_LABELS)


def save_settings():
    try:
        engine_save.save("n", settings["n"])
        engine_save.save("r", settings["r"])
        engine_save.save("aim", settings["aim"])
        for i in range(4):
            engine_save.save("nm" + str(i), settings["names"][i])
            engine_save.save("ty" + str(i), settings["types"][i])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Game rules
# ---------------------------------------------------------------------------
def supported(p):
    if p.y >= BEDROCK:
        return True
    base = p.y * W
    for c in range(p.x - 3, p.x + 4):
        if 0 <= c < W and terrain[base + c]:
            return True
    return False


def popup(x, y, text, color):
    G.popups.append([x, y, text, 50, color, None, 0])


def damage_popup(p, amount, color):
    """Show "-N" over a tank, adding to its last number if that's still fresh."""
    for pu in G.popups:
        if pu[5] is p and pu[4] == color and pu[3] > 25:
            pu[6] += amount
            pu[2] = "-" + str(pu[6])
            return
    G.popups.append([p.x, p.y - 12, "-" + str(amount), 50, color, p, amount])


def hurt(p, amount, owner, blast=True):
    if amount <= 0 or not p.alive:
        return
    if blast and p.shield > 0:
        soak = min(amount, p.shield)
        p.shield -= soak
        amount -= soak
        if p.shield == 0:
            popup(p.x, p.y - 18, "SHIELD DOWN", C_SHIELD)
        if amount <= 0:
            damage_popup(p, soak, C_SHIELD)
            p.flash = 12
            return
    if amount > p.hp:
        amount = p.hp
    p.hp -= amount
    p.flash = 20
    G.calm = 0
    if p.power > p.max_power():
        p.power = p.max_power()
    damage_popup(p, amount, C_WHITE)
    if owner is not None and owner is not p:
        owner.money += amount * MONEY_PER_HP
    if p.hp <= 0:
        p.alive = False
        G.dying.append(p)
        if owner is not None and owner is not p:
            owner.kills += 1
            owner.money += KILL_BONUS


def throw_debris(x, y, r, dirt):
    colors = DIRT_COLORS if dirt else FIRE_COLORS
    for _ in range(min(12, r + 2)):
        if len(G.debris) >= MAX_DEBRIS:
            break
        a = random.uniform(0.2, math.pi - 0.2)
        sp = random.uniform(0.6, 1.4 + r * 0.06)
        G.debris.append([x, y, math.cos(a) * sp, -math.sin(a) * sp,
                         random.randint(20, 45), colors[random.randrange(1, 5)]])


def update_debris():
    keep = []
    for d in G.debris:
        d[3] += 0.08
        d[0] += d[2]
        d[1] += d[3]
        d[4] -= 1
        ix = int(d[0])
        iy = int(d[1])
        if d[4] <= 0 or ix < 0 or ix >= W or iy >= BEDROCK:
            continue
        if iy >= 0 and terrain[iy * W + ix] and d[3] > 0:
            continue                # Landed
        keep.append(d)
    G.debris = keep


def boom(x, y, r, dmg, owner, dirt):
    G.blasts.append(Blast(x, y, r, dirt))
    throw_debris(x, y, r, dirt)
    blast_terrain(x, y, r, 1 if dirt else 0)
    if x - r - 3 < G.dx0:
        G.dx0 = x - r - 3
    if x + r + 3 > G.dx1:
        G.dx1 = x + r + 3
    if dirt:
        return
    G.shake = max(G.shake, min(10, r // 2 + 2))
    sound.explode()
    reach = r + 4
    for p in G.players:
        if p.alive:
            dx = p.x - x
            dy = p.y - 3 - y
            d = math.sqrt(dx * dx + dy * dy)
            if d < reach:
                hurt(p, int(dmg * (reach - d) / reach + 0.5), owner)


def hit_tank(ix, iy, s):
    for p in G.players:
        if p.alive and (p is not s.owner or s.age > 8):
            if -3 <= ix - p.x <= 3 and p.y - 6 <= iy < p.y:
                return p
    return None


def fire_free(x, y, occ):
    """Can a burning drop move into this pixel?"""
    if x < 0 or x >= W or y >= BEDROCK:
        return False
    if y >= 0 and terrain[y * W + x]:
        return False
    return (x | (y << 9)) not in occ


def splash_napalm(x, y, owner):
    G.fire_owner = owner
    G.fire_t = 0
    for _ in range(NAPALM_DROPS):
        G.fire.append([x + random.randint(-4, 4), y - random.randint(0, 4),
                       random.randint(150, 240)])
    sound.blip(220, 8)


def update_fire():
    """Burning drops flow like a liquid: down, then diagonally, then sideways."""
    occ = set()
    for d in G.fire:
        occ.add(d[0] | (d[1] << 9))
    keep = []
    for d in G.fire:
        x = d[0]
        y = d[1]
        occ.discard(x | (y << 9))
        d[2] -= 1
        if d[2] <= 0 or x < 0 or x >= W or y >= BEDROCK:
            # Burnt out: leave a scorch mark on the ground below
            if 0 <= x < W and 0 <= y + 1 < BEDROCK and terrain[(y + 1) * W + x]:
                terrain[(y + 1) * W + x] = T_SCORCH
            continue
        if fire_free(x, y + 1, occ):
            y += 1
        else:
            dx = 1 if random.getrandbits(1) else -1
            if fire_free(x + dx, y + 1, occ):
                x += dx
                y += 1
            elif fire_free(x - dx, y + 1, occ):
                x -= dx
                y += 1
            elif random.getrandbits(1):
                if fire_free(x + dx, y, occ):
                    x += dx
                elif fire_free(x - dx, y, occ):
                    x -= dx
        d[0] = x
        d[1] = y
        occ.add(x | (y << 9))
        keep.append(d)
    G.fire = keep

    # Tanks sitting in the fire get burnt
    G.fire_t += 1
    if G.fire_t % FIRE_TICK == 0:
        for p in G.players:
            if not p.alive:
                continue
            n = 0
            for d in G.fire:
                if -4 <= d[0] - p.x <= 4 and p.y - 7 <= d[1] <= p.y:
                    n += 1
            if n:
                hurt(p, min(6, 1 + n // 4), G.fire_owner)


def detonate(s, out):
    """Blow up a shot. Any bomblets it throws out are added to the out list."""
    if s.kind == K_TRACER:
        return
    if s.kind == K_NAPALM:
        boom(int(s.x), int(s.y), s.radius, s.damage, s.owner, False)
        splash_napalm(int(s.x), int(s.y), s.owner)
        return
    boom(int(s.x), int(s.y), s.radius, s.damage, s.owner, s.kind == K_DIRT)
    if s.kind == K_FUNKY:
        for _ in range(FUNKY_BITS):
            c = Shot(s.x, s.y - 2, random.uniform(-1.6, 1.6), random.uniform(-2.6, -1.2),
                     s.owner, s.weapon)
            c.kind = K_MISSILE
            c.radius = 6
            c.damage = 30
            c.age = 99
            out.append(c)
        sound.blip(1400, 3)


def start_roll(s, ix, iy):
    s.rolling = True
    s.x = ix
    s.y = iy
    left = ground_below(ix - 3, iy - 6)
    right = ground_below(ix + 3, iy - 6)
    if right > left:
        s.rdir = 1
    elif left > right:
        s.rdir = -1
    else:
        s.rdir = 1 if s.vx >= 0 else -1
    s.speed = 30


def roll_shot(s):
    """Move a landed roller along the ground. Returns True when it blows up."""
    s.rtime += 1
    if s.rtime > 240:
        return True
    for _ in range(2 if s.rtime & 1 else 1):
        nx = s.x + s.rdir
        if nx < 0 or nx >= W:
            return True
        top = ground_below(nx, s.y - 3)
        drop = top - s.y
        if drop < -2:
            return True             # Ran into a wall
        if drop > 3:
            s.y += 3                # Falling off a ledge
            s.speed += 4
        else:
            s.y = top
            s.speed += drop * 12 - 1
        s.x = nx
        if s.speed > 60:
            s.speed = 60
        if s.speed <= 0:
            return True             # Came to rest in a valley
        for p in G.players:
            if p.alive and (p is not s.owner or s.rtime > 10):
                if -4 <= s.x - p.x <= 4 and p.y - 7 <= s.y <= p.y + 1:
                    return True
    return False


def add_trail(x, y):
    n = G.trail_n
    if n < MAX_TRAIL and -8 <= x < W + 8 and y > -500:
        trail_x[n] = int(x) + 8
        trail_y[n] = int(y) + 512
        G.trail_n = n + 1


def step_shot(s):
    """Move a flying shot one frame. Returns 0 still flying, 1 burst, 2 gone, 3 split."""
    ax = G.wind * WIND_K / SUB
    ay = GRAVITY / SUB
    for k in range(SUB):
        s.vx += ax
        s.vy += ay
        s.x += s.vx / SUB
        s.y += s.vy / SUB
        if k & 1:
            add_trail(s.x, s.y)
        if s.kind == K_MIRV and not s.split and s.vy > 0:
            return 3
        if s.x < 0 or s.x >= W:
            if s.x < -6 or s.x >= W + 6 or s.y >= H:
                return 2
            continue
        ix = int(s.x)
        iy = int(s.y + 512) - 512
        if iy >= BEDROCK or (iy >= 0 and terrain[iy * W + ix]):
            if s.kind == K_ROLLER:
                start_roll(s, ix, iy)
                return 0
            return 1
        if hit_tank(ix, iy, s) is not None:
            return 1
    s.age += 1
    if s.age > 3000:
        return 2                    # Safety net: nothing flies for 50 seconds
    return 0


G_Q16 = const(819)         # GRAVITY / SUB in 16.16 fixed point


@micropython.viper
def sim_shot(x: int, y: int, vx: int, vy: int) -> int:
    """Where a shot would land, ignoring tanks, in 16.16 fixed point.
    Wind per sub-step comes from sim_ax[0]. Used by the CPU to aim."""
    t = ptr8(terrain)
    ax = int(ptr32(sim_ax)[0])
    n = 0
    while n < 4000:
        vx += ax
        vy += G_Q16
        x += vx >> 2
        y += vy >> 2
        if x < 0:
            return -60
        if x >= 16777216:
            return 316
        if y >= 0:
            iy = y >> 16
            if iy >= 126:
                return x >> 16
            if t[iy * 256 + (x >> 16)] != 0:
                return x >> 16
        n += 1
    return x >> 16


def fire(p):
    w = p.wsel
    if p.inv[w] == 0:
        w = 0
    if p.inv[w] > 0:
        p.inv[w] -= 1
    a = math.radians(p.angle)
    speed = p.power * V_MAX / 1000
    tx, ty = p.barrel_tip(p.angle, 7)
    G.shots = [Shot(tx, ty, math.cos(a) * speed, -math.sin(a) * speed, p, w)]
    G.trail_n = 0
    G.trail_color = p.color
    if p.inv[p.wsel] == 0:
        p.next_weapon()
    G.state = ST_FLY
    sound.blip(180, 4)


# ---------------------------------------------------------------------------
# CPU players
# ---------------------------------------------------------------------------
def cpu_plan(p):
    """Generator that works out a shot a few simulations per frame.
    Yields the angle being tried so the barrel can be seen searching."""
    skill = CPU_SKILL[p.ctype]
    foes = [q for q in G.players if q.alive and q is not p]
    # Hurt tanks have less power, so stick to targets in range if there are any
    sp = p.max_power() * V_MAX / 1000
    reach = sp * sp / GRAVITY * 0.9
    near = [q for q in foes if abs(q.x - p.x) < reach]
    if near:
        foes = near
    if p.ctype == 1:
        t = foes[random.randrange(len(foes))]
    else:
        t = foes[0]
        for q in foes:
            # Prefer close, weak targets
            if abs(q.x - p.x) + q.hp < abs(t.x - p.x) + t.hp:
                t = q
    if t is p.ai_target:
        p.ai_streak += 1
    else:
        p.ai_target = t
        p.ai_streak = 0
    side = 1 if t.x >= p.x else -1
    tries = (50, 62, 40, 72, 30)[:p.ctype + 2] + (45,)     # 45 goes farthest
    maxp = p.max_power()
    best_err = 9999
    best_angle = p.angle
    best_power = p.power
    sim_ax[0] = int(G.wind * WIND_K / SUB * 65536)
    for a in tries:
        ang = a if side > 0 else 180 - a
        rad = math.radians(ang)
        tx, ty = p.barrel_tip(ang, 7)
        lo = 60
        hi = maxp
        for _ in range(9):
            mid = (lo + hi) // 2
            sp = mid * V_MAX / 1000
            hx = sim_shot(int(tx * 65536), int(ty * 65536),
                          int(math.cos(rad) * sp * 65536), int(-math.sin(rad) * sp * 65536))
            err = hx - t.x
            if abs(err) < best_err:
                best_err = abs(err)
                best_angle = ang
                best_power = mid
            if err * side < 0:
                lo = mid
            else:
                hi = mid
            yield ang
        if best_err <= 3:
            break

    ea, ep, focus, special = skill
    zero_in = max(0.25, focus ** p.ai_streak)
    ea = int(ea * zero_in + 0.5)
    ep = int(ep * zero_in + 0.5)
    p.ai_angle = max(0, min(180, best_angle + random.randint(-ea, ea)))
    p.ai_power = max(min(50, maxp), min(maxp, best_power + random.randint(-ep, ep)))

    # Maybe pick something bigger, as long as it won't hit ourselves
    dist = abs(t.x - p.x)
    options = [i for i in range(1, len(WEAPONS))
               if p.inv[i] != 0 and WEAPONS[i][3] in (K_MISSILE, K_MIRV, K_FUNKY, K_NAPALM)
               and WEAPONS[i][1] + 8 < dist]
    if options and random.random() < special:
        p.wsel = options[random.randrange(len(options))]
    else:
        p.wsel = 0


def toward(v, target, step):
    if v < target:
        return min(target, v + step)
    return max(target, v - step)


def update_cpu(p):
    if G.ai is not None:
        try:
            for _ in range(2):
                G.ai_peek = next(G.ai)
        except StopIteration:
            G.ai = None
            G.ai_wait = 0
        p.angle = toward(p.angle, G.ai_peek, 2)
        return
    p.angle = toward(p.angle, p.ai_angle, 1)
    p.power = toward(p.power, p.ai_power, 15)
    if p.angle == p.ai_angle and p.power == p.ai_power:
        G.ai_wait += 1
        if G.ai_wait > 25:
            fire(p)


# ---------------------------------------------------------------------------
# Turn flow
# ---------------------------------------------------------------------------
def start_game():
    G.players = []
    for i in range(settings["n"]):
        G.players.append(Player(i, NAMES[settings["names"][i]], settings["types"][i]))
    G.rounds = ROUND_OPTS[settings["r"]]
    G.round_no = 0
    open_shop()


def next_round():
    G.round_no += 1
    for p in G.players:
        p.new_round()
    new_landscape(G.players)
    G.wind = random.randint(-10, 10)
    G.shots = []
    G.blasts = []
    G.dying = []
    G.popups = []
    G.debris = []
    G.fire = []
    G.trail_n = 0
    G.dx0 = W
    G.dx1 = -1
    G.turn_count = 0
    G.calm = 0
    G.sudden = False
    begin_turn((G.round_no - 1) % len(G.players))
    G.cam = G.players[G.turn].x - 64.0
    clamp_cam()


def begin_turn(i):
    G.turn = i
    p = G.players[i]
    G.state = ST_TURN
    G.timer = 0
    G.pan = 0
    G.ai = cpu_plan(p) if p.is_cpu() else None
    G.ai_peek = p.angle
    G.ai_wait = 0
    if p.power > p.max_power():
        p.power = p.max_power()
    if p.inv[p.wsel] == 0:
        p.wsel = 0
    sound.blip(660, 3)


def end_turn():
    alive = [p for p in G.players if p.alive]
    if len(alive) <= 1:
        round_end(alive[0] if alive else None)
        return
    # Nobody can hit anybody: open up full power for everyone
    G.calm += 1
    if not G.sudden and G.calm >= 3 * len(alive):
        G.sudden = True
    # Wind wanders a little between turns
    G.wind = max(-MAX_WIND, min(MAX_WIND, G.wind + random.randint(-2, 2)))
    n = len(G.players)
    i = G.turn
    for _ in range(n):
        i = (i + 1) % n
        if G.players[i].alive:
            break
    G.turn_count += 1
    begin_turn(i)


def round_end(winner):
    G.state = ST_ROUND_END
    G.timer = 0
    G.winner = winner
    sound.whistle_stop()
    for p in G.players:
        p.money += ROUND_PAY
    if winner is not None:
        winner.wins += 1
        winner.money += ROUND_BONUS


def clamp_cam():
    if G.cam < 0:
        G.cam = 0.0
    elif G.cam > W - SW:
        G.cam = float(W - SW)


def cam_toward(x, speed):
    G.cam += (x - 64 - G.cam) * speed
    clamp_cam()


def hold_steps(i, btn):
    """Steps to move this frame for a held button: one on press, then faster the longer it's held."""
    if btn.is_pressed:
        G.held[i] += 1
    else:
        G.held[i] = 0
        return 0
    h = G.held[i]
    if h == 1:
        return 1
    if h > 45:
        return 3
    if h > 15:
        return 1
    return 0


def try_drive(p, d):
    nx = p.x + d
    if nx < 4 or nx > W - 5 or p.items[IT_FUEL] <= 0:
        return
    for q in G.players:
        if q is not p and q.alive and abs(q.x - nx) < 8 and abs(q.y - p.y) < 8:
            return
    top = 128
    for c in range(nx - 3, nx + 4):
        g = ground_below(c, p.y - 8)
        if g < top:
            top = g
    if top < p.y - 2 or top > p.y + 3:
        return                      # Too steep to climb, or a cliff
    p.x = nx
    p.y = top
    p.items[IT_FUEL] -= 1


def update_human_aim(p):
    b_held = engine_io.B.is_pressed
    left = hold_steps(0, engine_io.LEFT)
    right = hold_steps(1, engine_io.RIGHT)
    if b_held:
        # Hold B and use left/right to look around the battlefield
        if engine_io.LEFT.is_pressed:
            G.pan -= 3
            G.panned = True
        if engine_io.RIGHT.is_pressed:
            G.pan += 3
            G.panned = True
        # Stop at the world edges so panning back responds straight away
        G.pan = max(SW // 2 - p.x, min(W - SW // 2 - p.x, G.pan))
    else:
        if left:
            p.angle = min(180, p.angle + left)
        if right:
            p.angle = max(0, p.angle - right)

    up = hold_steps(2, engine_io.UP)
    down = hold_steps(3, engine_io.DOWN)
    if up:
        p.power = min(p.max_power(), p.power + up * 5)
    if down:
        p.power = max(0, p.power - down * 5)

    # Tapping B (without panning) switches weapon
    if engine_io.B.is_just_pressed:
        G.panned = False
        G.b_armed = True
    if engine_io.B.is_just_released:
        if G.b_armed and not G.panned:
            p.next_weapon()
            sound.blip(880, 2)
        G.b_armed = False

    if engine_io.LB.is_pressed or engine_io.RB.is_pressed:
        G.drive_t += 1
        if G.drive_t % 3 == 1:
            try_drive(p, -1 if engine_io.LB.is_pressed else 1)
    else:
        G.drive_t = 0

    if engine_io.A.is_just_pressed:
        fire(p)


def update_play():
    p = G.players[G.turn]
    for q in G.players:
        if q.flash > 0:
            q.flash -= 1

    for pu in G.popups:
        pu[3] -= 1
        if pu[3] & 1:
            pu[1] -= 1
    G.popups = [pu for pu in G.popups if pu[3] > 0]

    for b in G.blasts:
        b.t += 1
    G.blasts = [b for b in G.blasts if b.t < b.dur]
    if G.debris:
        update_debris()
    if G.fire:
        update_fire()

    st = G.state
    if st == ST_TURN:
        G.timer += 1
        cam_toward(p.x, 0.12)
        skip = not p.is_cpu() and (engine_io.A.is_just_pressed or engine_io.B.is_just_pressed)
        if G.timer > 55 or skip:
            G.state = ST_AIM
            G.b_armed = False
    elif st == ST_AIM:
        if p.is_cpu():
            update_cpu(p)
        else:
            update_human_aim(p)
        cam_toward(p.x + G.pan, 0.15)
    elif st == ST_FLY:
        update_fly()
    elif st == ST_BOOM:
        if G.blasts:
            b = G.blasts[-1]
            cam_toward(b.x, 0.1)
        elif G.fire:
            cam_toward(G.fire[0][0], 0.1)
        elif G.dying:
            d = G.dying.pop(0)
            boom(d.x, d.y - 3, 11, 40, None, False)
            popup(d.x, d.y - 16, "BOOM!", C_GOLD)
        else:
            G.state = ST_SETTLE
            G.quiet = 0
    elif st == ST_SETTLE:
        update_settle()


def update_fly():
    alive = []
    for s in G.shots:
        if s.rolling:
            if roll_shot(s):
                detonate(s, alive)
            else:
                alive.append(s)
            continue
        r = step_shot(s)
        if r == 0:
            alive.append(s)
        elif r == 1:
            detonate(s, alive)
        elif r == 3:
            # MIRV: split into five warheads
            for k in (-2, -1, 0, 1, 2):
                c = Shot(s.x, s.y, s.vx + k * 0.35, s.vy, s.owner, s.weapon)
                c.split = True
                c.age = s.age
                alive.append(c)
            sound.blip(1200, 3)
    G.shots = alive
    if alive:
        s = alive[len(alive) // 2]
        cam_toward(s.x, 0.25)
        sound.whistle(max(200, min(1600, 1500 - int(s.y) * 9)))
    else:
        sound.whistle_stop()
        G.state = ST_BOOM


def update_settle():
    moved = 0
    if G.dx0 <= G.dx1:
        m = settle_dirt(G.dx0, G.dx1) + settle_dirt(G.dx0, G.dx1)
        if m == 0:
            G.dx0 = W
            G.dx1 = -1
        moved += m
    for p in G.players:
        if not supported(p):
            moved += 1
            if p.alive and not p.chute and p.fall >= FALL_SAFE and p.items[IT_CHUTE] > 0:
                p.items[IT_CHUTE] -= 1
                p.chute = True
                sound.blip(500, 3)
            if p.chute and G.frame & 1:
                continue            # Parachutes fall at half speed
            p.y += 1
            p.fall += 1
        elif p.fall:
            if p.fall > FALL_SAFE and not p.chute:
                hurt(p, (p.fall - FALL_SAFE) * 2, None, False)
            p.fall = 0
            p.chute = False
    if moved:
        G.quiet = 0
    else:
        G.quiet += 1
        if G.quiet >= 3:
            if G.dying:
                G.state = ST_BOOM
            else:
                end_turn()


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
def draw_tank(fb, p, cam, oy, active):
    x = p.x - cam
    y = p.y - oy
    if x < -10 or x > SW + 10:
        return
    if not p.alive and p not in G.dying:
        fb.fill_rect(x - 3, y - 3, 7, 3, C_WRECK)
        fb.fill_rect(x - 1, y - 4, 2, 1, C_WRECK)
        fb.line(x, y - 4, x + 3, y - 6, C_WRECK)
        return
    col = p.color
    if p.flash & 2:
        col = C_WHITE
    tx, ty = p.barrel_tip(p.angle, 6)
    fb.line(x, y - 5, int(tx + 0.5) - cam, int(ty + 0.5) - oy, C_BARREL)
    fb.fill_rect(x - 1, y - 6, 3, 2, col)
    fb.fill_rect(x - 3, y - 4, 7, 2, col)
    fb.fill_rect(x - 3, y - 2, 7, 2, C_TREAD)
    fb.pixel(x - 2, y - 1, C_WHEEL)
    fb.pixel(x, y - 1, C_WHEEL)
    fb.pixel(x + 2, y - 1, C_WHEEL)
    if p.shield > 0 and p.alive:
        sc = C_SHIELD if p.shield > 20 or (G.frame // 4) & 1 else C_GREY
        fb.ellipse(x, y - 4, 6, 6, sc)
    if p.chute:
        fb.hline(x - 3, y - 16, 7, C_WHITE)
        fb.hline(x - 4, y - 15, 9, C_WHITE)
        fb.line(x - 4, y - 14, x - 2, y - 7, C_GREY)
        fb.line(x + 4, y - 14, x + 2, y - 7, C_GREY)
    if p.alive:
        fb.hline(x - 3, y - 9, 7, C_HP_BG)
        w = (p.hp * 7 + 99) // 100
        fb.hline(x - 3, y - 9, w, C_HP if p.hp > 35 else C_HP_LOW)
    if active and (G.frame // 8) & 1:
        fb.hline(x - 2, y - 14, 5, C_WHITE)
        fb.hline(x - 1, y - 13, 3, C_WHITE)
        fb.pixel(x, y - 12, C_WHITE)


def draw_aim_help(fb, p, cam, oy):
    """Dotted start of the shot's path (gravity only, no wind) for younger players."""
    a = math.radians(p.angle)
    sp = p.power * V_MAX / 1000
    x, y = p.barrel_tip(p.angle, 7)
    vx = math.cos(a) * sp
    vy = -math.sin(a) * sp
    for f in range(1, 46):
        vy += GRAVITY
        x += vx
        y += vy
        ix = int(x)
        iy = int(y)
        if ix < 0 or ix >= W or iy >= BEDROCK or (iy >= 0 and terrain[iy * W + ix]):
            break
        if f % 3 == 0:
            fb.pixel(ix - cam, iy - oy, C_WHITE if (f // 3) & 1 else C_BLACK)


def draw_scene(fb):
    cam = int(G.cam + 0.5)
    oy = 0
    if G.shake > 0 and not G.paused:
        a = (G.shake + 2) // 3
        oy = random.randint(-a, a)
        G.shake -= 1
    render_world(cam, oy)

    draw_trail(G.trail_n, cam, oy, G.trail_color)

    cur = G.players[G.turn] if G.players else None
    aiming = G.state in (ST_TURN, ST_AIM)
    for p in G.players:
        draw_tank(fb, p, cam, oy, aiming and p is cur)

    if G.state == ST_AIM and cur is not None and not cur.is_cpu() and settings["aim"]:
        draw_aim_help(fb, cur, cam, oy)

    for s in G.shots:
        sx = int(s.x) - cam
        sy = int(s.y) - oy
        if s.rolling:
            fb.fill_rect(sx - 1, sy - 3, 3, 3, C_WHITE)
        else:
            fb.fill_rect(sx, sy, 2, 2, C_WHITE)
            if sy < HUD_H and 0 <= sx < SW and (G.frame // 4) & 1:
                # Up off the top of the view: show where it is
                fb.pixel(sx, HUD_H + 1, C_WHITE)
                fb.hline(sx - 1, HUD_H + 2, 3, C_WHITE)

    for d in G.debris:
        fb.pixel(int(d[0]) - cam, int(d[1]) - oy, d[5])

    if G.fire:
        f = G.frame
        for d in G.fire:
            fx = d[0] - cam
            fy = d[1] - oy
            fb.pixel(fx, fy, FIRE_COLORS[1 + ((fx + f) & 1)])
            if (fx * 7 + f) % 3 == 0:
                fb.pixel(fx, fy - 1, FIRE_COLORS[2 + ((fy + f) & 1)])

    for b in G.blasts:
        b.draw(fb, cam, oy)

    for pu in G.popups:
        s = pu[2]
        tiny(s, pu[0] - cam - len(s) * 2 + 1, pu[1] - oy, pu[4])

    draw_hud(fb, cur, cam)


def draw_hud(fb, p, cam):
    fb.fill_rect(0, 0, SW, HUD_H, C_HUD)
    if p is None:
        return
    tiny(p.name, 1, 1, p.color)
    tiny("HP" + str(p.hp), 30, 1, C_HP if p.hp > 35 else C_HP_LOW)
    fuel = p.items[IT_FUEL]
    if fuel > 0:
        tiny("F" + str(fuel), 54, 1, C_GREY)
    if p.shield > 0:
        tiny("S" + str(p.shield), 70, 1, C_SHIELD)
    if p.items[IT_CHUTE] > 0:
        tiny("C" + str(p.items[IT_CHUTE]), 86, 1, C_WHITE)
    w = G.wind
    if w == 0:
        ws = "WIND 0"
    elif w > 0:
        ws = "WIND " + str(w) + ">"
    else:
        ws = "WIND <" + str(-w)
    tiny(ws, SW - len(ws) * 4, 1, C_WHITE)

    tiny("A" + str(p.angle), 1, 7, C_WHITE)
    tiny("P" + str(p.power), 21, 7, C_WHITE)
    wpn = WEAPONS[p.wsel]
    n = p.inv[p.wsel]
    ws = wpn[0] if n < 0 else wpn[0] + " " + str(n)
    tiny(ws, SW - len(ws) * 4, 7, C_GOLD)

    # Minimap: whole world at half size, with the visible part underlined
    fb.fill_rect(0, 13, SW, 4, C_MAP)
    fb.hline(cam // 2, 16, SW // 2, C_GREY)
    for q in G.players:
        if q.alive:
            fb.fill_rect(q.x // 2 - 1, 13, 2, 2, q.color)
        else:
            fb.fill_rect(q.x // 2 - 1, 14, 2, 1, C_DARK)
    for s in G.shots:
        fb.pixel(int(s.x) // 2, 15, C_WHITE)


def draw_banner(fb):
    p = G.players[G.turn]
    if G.timer < 50 or (G.timer // 6) & 1:
        if G.turn_count == 0:
            # First turn of a round also shows the round number
            s = "ROUND " + str(G.round_no)
            if G.rounds > 1:
                s += "/" + str(G.rounds)
            text_center(fb, s, 34, C_WHITE)
        text_center(fb, p.name + "'S TURN", 46, p.color)
        if p.is_cpu():
            tiny_center("CPU " + ("EASY", "MEDIUM", "HARD")[p.ctype - 1], 57, C_GREY)
        if G.sudden:
            text_center(fb, "SUDDEN DEATH!", 66, C_ORANGE)
            tiny_center("EVERYONE GETS FULL POWER", 77, C_WHITE)


def draw_panel(fb, x, y, w, h):
    fb.fill_rect(x, y, w, h, C_HUD)
    fb.rect(x, y, w, h, C_GREY)


def draw_pause(fb):
    dim_screen()
    draw_panel(fb, 14, 38, 100, 50)
    text_center(fb, "PAUSED", 45, C_WHITE)
    tiny_center("A: RESUME", 62, C_WHITE)
    tiny_center("B: QUIT TO TITLE", 72, C_GREY)


def draw_standings(fb, title, title_color, subtitle):
    dim_screen()
    n = len(G.players)
    y0 = 24
    h = 52 + n * 10
    draw_panel(fb, 6, y0, 116, h)
    text_center(fb, title, y0 + 6, title_color)
    tiny_center(subtitle, y0 + 17, C_GREY)
    y = y0 + 27
    for p in sorted(G.players, key=lambda q: -q.wins):
        fb.fill_rect(12, y, 5, 5, p.color)
        tiny(p.name, 20, y, C_WHITE)
        tiny(str(p.wins) + (" WIN" if p.wins == 1 else " WINS"), 60, y, C_GOLD)
        tiny("$" + str(p.money), 92, y, C_GREY)
        y += 10
    if G.timer > 30 and (G.frame // 10) & 1:
        tiny_center("PRESS A", y0 + h - 10, C_WHITE)


def draw_round_end(fb):
    sub = "ROUND " + str(G.round_no) + " OF " + str(G.rounds)
    if G.winner is None:
        draw_standings(fb, "DRAW!", C_WHITE, sub)
    else:
        draw_standings(fb, G.winner.name + " WINS!", G.winner.color, sub)


def draw_game_end(fb):
    best = max(p.wins for p in G.players)
    champs = [p for p in G.players if p.wins == best]
    if len(champs) == 1:
        draw_standings(fb, champs[0].name + " WINS!", champs[0].color, "CHAMPION - GAME OVER")
    else:
        draw_standings(fb, "IT'S A TIE!", C_WHITE, "GAME OVER")


# ---------------------------------------------------------------------------
# Title and setup screens
# ---------------------------------------------------------------------------
def update_title(fb):
    G.timer += 1
    G.cam = 64 + 60 * math.sin(G.timer / 160)
    render_world(int(G.cam), 0)
    big_center(fb, "SCORCHED", 18, C_ORANGE, C_BLACK, 4)
    big_center(fb, "THUMB", 44, C_GOLD, C_BLACK, 4)
    if (G.timer // 20) & 1:
        text_center(fb, "PRESS A", 96, C_WHITE)
    tiny_center("A SCORCHED EARTH TRIBUTE", 120, C_WHITE)
    if engine_io.A.is_just_pressed:
        G.state = ST_SETUP
        G.sel = 0
        sound.blip(660, 3)


SETUP_P0 = const(3)      # Setup row of the first player


def setup_rows():
    return SETUP_P0 + settings["n"] + 1     # Players, rounds, aim help, each player, start


def cycle_name(i):
    used = [settings["names"][k] for k in range(settings["n"]) if k != i]
    v = settings["names"][i]
    for _ in range(len(NAMES)):
        v = (v + 1) % len(NAMES)
        if v not in used:
            break
    settings["names"][i] = v


def update_setup(fb):
    rows = setup_rows()
    if engine_io.UP.is_just_pressed:
        G.sel = (G.sel - 1) % rows
        sound.blip(520, 2)
    if engine_io.DOWN.is_just_pressed:
        G.sel = (G.sel + 1) % rows
        sound.blip(520, 2)
    d = 0
    if engine_io.LEFT.is_just_pressed:
        d = -1
    if engine_io.RIGHT.is_just_pressed:
        d = 1
    sel = G.sel
    start_row = rows - 1
    if d:
        sound.blip(740, 2)
        if sel == 0:
            settings["n"] = min(4, max(2, settings["n"] + d))
            # Fix up any repeated names when a player joins
            for i in range(settings["n"]):
                if settings["names"][i] in [settings["names"][k] for k in range(i)]:
                    cycle_name(i)
        elif sel == 1:
            settings["r"] = (settings["r"] + d) % len(ROUND_OPTS)
        elif sel == 2:
            settings["aim"] = 1 - settings["aim"]
        elif sel < start_row:
            i = sel - SETUP_P0
            settings["types"][i] = (settings["types"][i] + d) % len(TYPE_LABELS)
    if engine_io.A.is_just_pressed:
        if sel == start_row:
            save_settings()
            sound.blip(990, 5)
            start_game()
            return
        elif SETUP_P0 <= sel < start_row:
            cycle_name(sel - SETUP_P0)
            sound.blip(740, 2)
    if engine_io.B.is_just_pressed:
        G.state = ST_TITLE
        G.timer = 0
        return
    G.sel = min(G.sel, setup_rows() - 1)

    # Draw
    fb.fill(C_SETUP_BG)
    text_center(fb, "BATTLE SETUP", 3, C_GOLD)
    rows = setup_rows()
    for r in range(rows):
        y = 17 + r * 11
        if r == G.sel:
            fb.fill_rect(0, y - 2, SW, 11, C_SEL)
        if r == 0:
            fb.text("PLAYERS", 4, y, C_WHITE)
            fb.text("<" + str(settings["n"]) + ">", 92, y, C_GOLD)
        elif r == 1:
            fb.text("ROUNDS", 4, y, C_WHITE)
            v = str(ROUND_OPTS[settings["r"]])
            fb.text("<" + v + ">", 92 if len(v) == 1 else 88, y, C_GOLD)
        elif r == 2:
            fb.text("AIM HELP", 4, y, C_WHITE)
            fb.text("<ON>" if settings["aim"] else "<OFF>", 88 if settings["aim"] else 80, y, C_GOLD)
        elif r < rows - 1:
            i = r - SETUP_P0
            fb.fill_rect(3, y, 7, 7, PLAYER_COLORS[i])
            fb.text(NAMES[settings["names"][i]], 14, y, C_WHITE)
            t = TYPE_LABELS[settings["types"][i]]
            fb.text(t, SW - len(t) * 8 - 2, y, C_GREY if settings["types"][i] else C_WHITE)
        else:
            text_center(fb, "START!", y, C_ORANGE)
    if SETUP_P0 <= G.sel < rows - 1:
        tiny_center("L/R: HUMAN OR CPU   A: NAME", 112, C_GREY)
    elif G.sel == 2:
        tiny_center("SHOWS WHERE SHOTS START TO GO", 112, C_GREY)
    else:
        tiny_center("UP/DOWN: PICK   L/R: CHANGE", 112, C_GREY)
    tiny_center("A: OK   B: BACK", 119, C_GREY)


# ---------------------------------------------------------------------------
# Shop
# ---------------------------------------------------------------------------
def store_info(e):
    """(name, price, bundle size, description) for a shop entry."""
    if e[0] == 0:
        w = WEAPONS[e[1]]
        return w[0], w[4], w[5], w[6]
    return ITEMS[e[1]]


def store_have(p, e):
    return p.inv[e[1]] if e[0] == 0 else p.items[e[1]]


def store_buy(p, e):
    name, price, n, desc = store_info(e)
    if p.money < price:
        return False
    p.money -= price
    if e[0] == 0:
        p.inv[e[1]] += n
    else:
        p.items[e[1]] += n
    return True


def cpu_shop(p):
    """Spend about 70% of the money on random things from the wish list."""
    keep = p.money * 3 // 10
    for _ in range(12):
        opts = [e for e in CPU_WISH if store_info(e)[1] <= p.money - keep]
        if not opts:
            break
        store_buy(p, opts[random.randrange(len(opts))])


def open_shop():
    for p in G.players:
        if p.is_cpu():
            cpu_shop(p)
    G.shop_queue = [p for p in G.players if not p.is_cpu()]
    if not G.shop_queue:
        next_round()
        return
    G.state = ST_SHOP
    G.sel = 0
    G.shop_top = 0
    G.shop_msg = 0
    G.timer = 0
    sound.blip(660, 3)


def update_shop(fb):
    p = G.shop_queue[0]
    n = len(STORE)
    G.timer += 1
    if engine_io.UP.is_just_pressed:
        G.sel = (G.sel - 1) % n
        sound.blip(520, 2)
    if engine_io.DOWN.is_just_pressed:
        G.sel = (G.sel + 1) % n
        sound.blip(520, 2)
    if G.sel < G.shop_top:
        G.shop_top = G.sel
    elif G.sel >= G.shop_top + SHOP_ROWS:
        G.shop_top = G.sel - SHOP_ROWS + 1
    if G.timer > 10:
        if engine_io.A.is_just_pressed:
            if store_buy(p, STORE[G.sel]):
                sound.blip(1100, 3)
                G.shop_msg = 0
            else:
                sound.blip(150, 6)
                G.shop_msg = 50
        elif engine_io.B.is_just_pressed:
            G.shop_queue.pop(0)
            sound.blip(990, 4)
            if not G.shop_queue:
                next_round()
                return
            G.sel = 0
            G.shop_top = 0
            G.shop_msg = 0
            G.timer = 0
            p = G.shop_queue[0]
    if G.shop_msg > 0:
        G.shop_msg -= 1

    # Draw
    fb.fill(C_SETUP_BG)
    fb.fill_rect(0, 0, SW, 12, C_HUD)
    fb.fill_rect(2, 2, 7, 7, p.color)
    fb.text(p.name, 12, 2, C_WHITE)
    ms = "$" + str(p.money)
    fb.text(ms, SW - len(ms) * 8 - 1, 2, C_GOLD)
    tiny("ITEM", 4, 15, C_GREY)
    tiny("GET", 60, 15, C_GREY)
    tiny("COST", 89, 15, C_GREY)
    tiny("HAVE", 109, 15, C_GREY)
    for k in range(SHOP_ROWS):
        i = G.shop_top + k
        if i >= n:
            break
        e = STORE[i]
        name, price, bundle, desc = store_info(e)
        y = 25 + k * 9
        if i == G.sel:
            fb.fill_rect(0, y - 2, SW, 9, C_SEL)
        ok = p.money >= price
        tiny(name, 4, y, C_WHITE if ok else C_GREY)
        tiny("x" + str(bundle), 60, y, C_GREY)
        ps = "$" + str(price)
        tiny(ps, 105 - len(ps) * 4, y, C_GOLD if ok else C_RED)
        hs = str(store_have(p, e))
        tiny(hs, 125 - len(hs) * 4, y, C_WHITE)
    # Scroll arrows
    if G.shop_top > 0:
        fb.pixel(122, 20, C_WHITE)
        fb.hline(121, 21, 3, C_WHITE)
    if G.shop_top + SHOP_ROWS < n:
        fb.hline(121, 106, 3, C_WHITE)
        fb.pixel(122, 107, C_WHITE)
    if G.shop_msg > 0:
        tiny_center("NOT ENOUGH MONEY!", 110, C_RED)
    else:
        tiny_center(store_info(STORE[G.sel])[3], 110, C_WHITE)
    tiny_center("A: BUY   B: DONE", 119, C_GREY)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def tick():
    fb = engine_draw.back_fb()
    G.frame += 1
    sound.tick()
    st = G.state

    if st == ST_TITLE:
        update_title(fb)
        return
    if st == ST_SETUP:
        update_setup(fb)
        return
    if st == ST_SHOP:
        update_shop(fb)
        return

    if G.paused:
        if engine_io.A.is_just_pressed or engine_io.MENU.is_just_pressed:
            G.paused = False
        elif engine_io.B.is_just_pressed:
            G.paused = False
            sound.whistle_stop()
            G.state = ST_TITLE
            G.timer = 0
            new_landscape([])
            return
        draw_scene(fb)
        draw_pause(fb)
        return

    if engine_io.MENU.is_just_pressed and st != ST_GAME_END:
        G.paused = True
        sound.whistle_stop()
        draw_scene(fb)
        draw_pause(fb)
        return

    if st == ST_ROUND_END:
        G.timer += 1
        draw_scene(fb)
        draw_round_end(fb)
        if G.timer > 30 and engine_io.A.is_just_pressed:
            if G.round_no >= G.rounds:
                G.state = ST_GAME_END
                G.timer = 0
            else:
                open_shop()
        return
    if st == ST_GAME_END:
        G.timer += 1
        draw_scene(fb)
        draw_game_end(fb)
        if G.timer > 30 and engine_io.A.is_just_pressed:
            G.state = ST_TITLE
            G.timer = 0
            new_landscape([])
        return

    update_play()
    draw_scene(fb)
    if G.state == ST_TURN:
        draw_banner(fb)


load_settings()
new_landscape([])
engine.fps_limit(60)

while True:
    if engine.tick():
        tick()
