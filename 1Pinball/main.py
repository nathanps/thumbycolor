# Pinball - five pinball tables for the Thumby Color
import engine_main

import engine
import engine_io
import engine_draw
import engine_audio
import engine_save
from engine_resources import ToneSoundResource

import array
import math
import random

# NOTE: the device has no big integers. Every whole number in this file, and every
# result worked out from them, must stay below 2**30.

# ---------------------------------------------------------------------------
# Table layout
# ---------------------------------------------------------------------------
SW = const(128)         # Screen width
TW = const(128)         # Table width
TH = const(248)         # Table height, about two screens. The camera follows the ball
HUD_H = const(7)        # Rows covered by the score bar at the top of the screen
VIEW_H = const(121)     # Table rows that fit under the score bar
CAM_MAX = const(127)    # TH - VIEW_H: the camera at the bottom, showing the flippers
CAM_TOP = 30            # When the camera has to rise, the ball sits this far below the top
CAM_LEAD = 12           # Frames of movement the camera looks ahead by

BALL_R = 3.0
CONTACT = 3.5           # Ball centre to wall pixel centre distance when touching
GRAVITY = 0.075         # Pixels per frame per frame, down the table
V_MAX = 9.0             # Speed limit, so the ball never moves too far in one sub-step
E_WALL = 0.45           # Bounciness of walls
E_RAIL = 0.1            # The curved top of the table hardly bounces, so orbit shots roll round it
E_FLIP = 0.25           # Bounciness of flipper rubber (the kick comes from the swing)
BUMP_V = 4.4            # Speed a pop bumper kicks the ball away at
SLING_V = 3.2           # Speed a slingshot adds
HOLE_V = 7.5            # Balls slower than this drop into a hole
RAMP_V = 3.2            # Speed along a ramp, pixels per frame
KICK_V = 5.2            # Kickback launch speed

# Flippers: pivot, length, angles (radians, 0 = pointing at the other flipper, + is down)
FLIP_LEN = 23.0
FLIP_R0 = 3.0           # Rubber radius at the pivot
FLIP_R1 = 1.8           # and at the tip
FLIP_REST = 0.47
FLIP_UP = -0.5
FLIP_W_UP = 0.33        # Swing speed up and down, radians per frame
FLIP_W_DOWN = 0.2
LFLIP_X = 27.0
RFLIP_X = 87.0
FLIP_Y = 224.0
MID_X = 57              # Centre line of the playfield (left wall to the plunger lane)

# Plunger lane
LANE_X = 120.0          # Ball x in the plunger lane
PLUNGE_Y = 236          # Plunger head at rest
PLUNGE_PULL = 8         # Pixels the plunger pulls back at full charge
SERVE_Y = PLUNGE_Y - CONTACT
LAUNCH_MIN = 6.6        # Launch speeds at no charge and full charge
LAUNCH_MAX = 8.6
AUTO_V = 7.8            # Launch speed for balls the machine fires itself (multiball)

BALLS = const(3)
MAX_EXTRA = const(2)    # Extra balls a game can earn

# Wall materials (looked up through the kinds table for each palette index)
K_AIR = const(0)
K_WALL = const(1)
K_SLING_L = const(2)
K_SLING_R = const(3)
K_BUMP = const(4)       # 4 to 11: pop bumpers
K_TARGET = const(16)    # 16 to 47: drop targets
K_DOOR = const(48)      # The castle gate
K_RAIL = const(49)      # The curved top of the table
K_GUIDE = const(50)     # Outlane guides: solid only to a ball coming down

# Palette indices. 0-15 are each table's painted colours, 16-63 lamps and zones
# (not solid), 64-79 each table's wall colours, and 80 up solid features.
P_BG = const(0)
P_RAIL = const(15)      # Ramp rails
P_SAVE = const(16)      # "SAVE" lamp between the flippers
LAMP0 = const(17)       # First lamp handed out by new_lamp()
P_WALL = const(64)
P_WALL_HI = const(65)
P_POST = const(66)
P_SLING_L = const(67)
P_SLING_R = const(68)
P_SLING_BODY = const(69)
P_APRON = const(70)
P_GATE = const(71)
P_S1 = const(72)        # 72 to 76: extra solid colours for a table's own walls
P_ARC = const(78)       # The curved top of the table (same colours as the walls)
P_ARC_HI = const(79)
P_GUIDE = const(77)
SOLID0 = const(80)      # First solid handed out by new_solid()

# Zone types (zones are non-solid areas that do something when the ball enters)
ZT_LANE = const(1)
ZT_SPIN = const(2)
ZT_HOLE = const(3)
ZT_RAMP = const(4)
ZT_KICK = const(5)

# Game states
ST_TITLE = const(0)
ST_PLAY = const(1)
ST_OVER = const(2)

# Ball states while playing
B_LIVE = const(1)
B_DRAIN = const(2)      # Last ball gone, waiting for the next one

# What each ball is doing
M_PLAY = const(0)
M_SERVE = const(1)      # Sitting on the plunger
M_HOLE = const(2)       # Caught in a hole
M_RAMP = const(3)       # Riding a ramp

# Drop target bank rewards
R_EXTRA = const(0)      # Every few clears, an extra ball
R_KICK = const(1)       # Lights the kickback
R_LOCK = const(2)       # Lights the lock hole for multiball

# Hole jobs
H_PLAIN = const(0)
H_COUNT = const(1)      # Enough visits starts multiball
H_LOCK = const(2)       # Starts multiball when lit


def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def rgbt(c):
    return ((c[0] & 0xF8) << 8) | ((c[1] & 0xFC) << 3) | (c[2] >> 3)


C_BLACK = const(0)
C_WHITE = const(0xFFFF)
C_GREY = rgb(140, 140, 160)
C_GOLD = rgb(255, 200, 40)
C_HUD = rgb(14, 10, 34)
C_PANEL = rgb(20, 16, 50)
C_BALL = rgb(190, 195, 215)
C_BALL_DARK = rgb(110, 115, 140)
C_SHADOW = rgb(10, 10, 16)
C_FLIP = rgb(240, 240, 250)
C_FLIP_RUB = rgb(240, 60, 90)
C_PLUNGER = rgb(200, 200, 220)
C_SPRING = rgb(150, 150, 170)
C_RED = rgb(255, 80, 80)
C_SPIN = rgb(230, 230, 240)
C_SPIN_EDGE = rgb(120, 120, 140)

table = bytearray(TW * TH)          # One palette index per pixel
palette = array.array("H", [0] * 256)
kinds = bytearray(256)              # Material of each palette index
zones = bytearray(256)              # Non-zero for palette indices that are zones
pr = array.array("i", [0] * 5)      # Results from probe()

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
# Fast functions
# ---------------------------------------------------------------------------
@micropython.viper
def render_table(cam: int):
    """Copy table rows cam.. to the screen under the score bar, through the palette."""
    buf = ptr16(engine_draw.back_fb_data())
    t = ptr8(table)
    pal = ptr16(palette)
    o = 896                 # HUD_H * 128
    src = cam * 128
    while o < 16384:
        buf[o] = pal[t[src]]
        o += 1
        src += 1


@micropython.viper
def probe(x: int, y: int) -> int:
    """Look for wall pixels touching a ball centred at x, y (in 1/16 pixels).
    Returns how many. pr gets the summed offsets to them, the squared distance
    to the nearest one, the nearest one's material and the zone under the ball."""
    t = ptr8(table)
    k = ptr8(kinds)
    z = ptr8(zones)
    out = ptr32(pr)
    cx = x >> 4
    cy = y >> 4
    sx = 0
    sy = 0
    n = 0
    best = 9999
    kind = 0
    x0 = cx - 4
    if x0 < 0:
        x0 = 0
    x1 = cx + 4
    if x1 > 127:
        x1 = 127
    py = cy - 4
    while py <= cy + 4:
        if py >= 0 and py < 248:
            dy = (py << 4) + 8 - y
            row = py * 128
            px = x0
            while px <= x1:
                v = k[t[row + px]]
                if v:
                    dx = (px << 4) + 8 - x
                    d2 = dx * dx + dy * dy
                    if d2 < 3136:           # (CONTACT * 16) squared
                        sx += dx
                        sy += dy
                        n += 1
                        if d2 < best:
                            best = d2
                            kind = v
                px += 1
        py += 1
    out[0] = sx
    out[1] = sy
    out[2] = best
    out[3] = kind
    zn = 0
    if cx >= 0 and cx < 128 and cy >= 0 and cy < 248:
        zn = z[t[cy * 128 + cx]]
    out[4] = zn
    return n


@micropython.viper
def stamp(cx: int, cy: int, r: int, c: int):
    """Paint a disc into the table. Centre and radius in 1/16 pixels."""
    t = ptr8(table)
    x0 = (cx - r) >> 4
    x1 = (cx + r) >> 4
    y0 = (cy - r) >> 4
    y1 = (cy + r) >> 4
    if x0 < 0:
        x0 = 0
    if x1 > 127:
        x1 = 127
    if y0 < 0:
        y0 = 0
    if y1 > 247:
        y1 = 247
    rr = r * r
    y = y0
    while y <= y1:
        dy = (y << 4) + 8 - cy
        x = x0
        while x <= x1:
            dx = (x << 4) + 8 - cx
            if dx * dx + dy * dy <= rr:
                t[y * 128 + x] = c
            x += 1
        y += 1


@micropython.viper
def stamp_under(cx: int, cy: int, r: int, c: int):
    """Like stamp, but only paints over plain background art (indices below 15),
    so ramp rails never cut holes in walls or cover lamps."""
    t = ptr8(table)
    x0 = (cx - r) >> 4
    x1 = (cx + r) >> 4
    y0 = (cy - r) >> 4
    y1 = (cy + r) >> 4
    if x0 < 0:
        x0 = 0
    if x1 > 127:
        x1 = 127
    if y0 < 0:
        y0 = 0
    if y1 > 247:
        y1 = 247
    rr = r * r
    y = y0
    while y <= y1:
        dy = (y << 4) + 8 - cy
        x = x0
        while x <= x1:
            dx = (x << 4) + 8 - cx
            if dx * dx + dy * dy <= rr and t[y * 128 + x] < 15:
                t[y * 128 + x] = c
            x += 1
        y += 1


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


def commas(n):
    s = str(n)
    out = ""
    while len(s) > 3:
        out = "," + s[-3:] + out
        s = s[:-3]
    return s + out


# ---------------------------------------------------------------------------
# Painting the table
# ---------------------------------------------------------------------------
def tdisc(x, y, r, c):
    stamp(int(x * 16), int(y * 16), int(r * 16), c)


def tline(x0, y0, x1, y1, r, c):
    """A thick line made of discs every half pixel."""
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
    for i in range(n + 1):
        f = i / n
        stamp(int((x0 + (x1 - x0) * f) * 16), int((y0 + (y1 - y0) * f) * 16), int(r * 16), c)


def tpath(pts, r, c, under=False):
    """Thick lines through a list of points."""
    fn = stamp_under if under else stamp
    for k in range(len(pts) - 1):
        x0, y0 = pts[k]
        x1, y1 = pts[k + 1]
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
        for i in range(n + 1):
            f = i / n
            fn(int((x0 + (x1 - x0) * f) * 16), int((y0 + (y1 - y0) * f) * 16), int(r * 16), c)


def trow(y, x0, x1, c):
    """Fill pixels x0..x1-1 of row y."""
    if x0 < 0:
        x0 = 0
    if x1 > TW:
        x1 = TW
    if x1 > x0 and 0 <= y < TH:
        o = y * TW
        table[o + x0:o + x1] = bytes((c,)) * (x1 - x0)


def trect(x, y, w, h, c):
    for yy in range(y, y + h):
        trow(yy, x, x + w, c)


def ttri(a, b, c, col):
    """Fill a triangle given three (x, y) corners."""
    x0 = int(min(a[0], b[0], c[0]))
    x1 = int(max(a[0], b[0], c[0])) + 1
    y0 = int(min(a[1], b[1], c[1]))
    y1 = int(max(a[1], b[1], c[1])) + 1

    def side(p, q, x, y):
        return (q[0] - p[0]) * (y - p[1]) - (q[1] - p[1]) * (x - p[0])
    for y in range(y0, y1):
        for x in range(x0, x1):
            px = x + 0.5
            py = y + 0.5
            s0 = side(a, b, px, py)
            s1 = side(b, c, px, py)
            s2 = side(c, a, px, py)
            if (s0 >= 0 and s1 >= 0 and s2 >= 0) or (s0 <= 0 and s1 <= 0 and s2 <= 0):
                table[y * TW + x] = col


def ttext(s, x, y, c):
    """Paint 3x5 text into the table."""
    for ch in s:
        g = (ord(ch) - 32) * 5
        for ry in range(5):
            bits = FONT[g + ry]
            for rx in range(3):
                if (bits >> (2 - rx)) & 1:
                    table[(y + ry) * TW + x + rx] = c
        x += 4


def tsprite(rows, x, y, cmap):
    """Paint a picture made of strings; cmap maps each character to a palette index."""
    for ry in range(len(rows)):
        row = rows[ry]
        for rx in range(len(row)):
            c = cmap.get(row[rx])
            if c is not None:
                table[(y + ry) * TW + x + rx] = c


def specks(seed, n, x0, y0, x1, y1, colors):
    """Scatter n pixels of the given colours, the same every time. The generator
    keeps its numbers small because the device has no big integers."""
    s = seed
    w = x1 - x0
    h = y1 - y0
    for i in range(n):
        s = (s * 75 + 74) % 65537
        x = x0 + s % w
        s = (s * 75 + 74) % 65537
        y = y0 + s % h
        s = (s * 75 + 74) % 65537
        table[y * TW + x] = colors[s % len(colors)]


def mirror(p):
    return (2 * MID_X - p[0], p[1])


# ---------------------------------------------------------------------------
# Table features. Each table is painted by a build function that calls these.
# ---------------------------------------------------------------------------
class TableState:
    def __init__(self):
        self.bumpers = []
        self.banks = []
        self.targets = []           # (bank, slot) for each drop target, by number
        self.lane_lamps = []
        self.lit = []               # Which rollover lanes are lit
        self.holes = []
        self.spinners = []
        self.ramps = []
        self.door = None
        self.kick_lamp = -1
        self.kick_lit = False
        self.mult_lamps = []
        self.blinkers = []          # (index, colour a, colour b, frames per flash)
        self.zone_map = {}          # Zone palette index -> (type, thing)
        self.next_lamp = LAMP0
        self.next_solid = SOLID0
        self.bg = 0


T = TableState()


def new_lamp(color):
    i = T.next_lamp
    T.next_lamp += 1
    palette[i] = rgbt(color)
    return i


def new_zone(ztype, thing, color=None):
    i = new_lamp(color if color else (0, 0, 0))
    if color is None:
        palette[i] = T.bg
    zones[i] = i
    T.zone_map[i] = (ztype, thing)
    return i


def new_solid(kind, color):
    i = T.next_solid
    T.next_solid += 1
    kinds[i] = kind
    palette[i] = rgbt(color)
    return i


class Bumper:
    def __init__(self, x, y, r, color, ring):
        self.x = x
        self.y = y
        self.color = rgbt(color)
        self.ring_color = rgbt(ring)
        n = len(T.bumpers)
        self.core = new_solid(K_BUMP + n, color)
        self.ring = new_solid(K_BUMP + n, ring)
        self.cd = 0
        self.flash = 0


def add_bumper(x, y, r, color, ring=None, gear=False):
    if ring is None:
        ring = (min(255, color[0] + 90), min(255, color[1] + 90), min(255, color[2] + 90))
    b = Bumper(x, y, r, color, ring)
    tdisc(x, y, r, b.ring)
    tdisc(x, y, r - 2.2, b.core)
    if gear:
        for k in range(8):
            a = k * math.pi / 4
            tdisc(x + (r + 0.6) * math.cos(a), y + (r + 0.6) * math.sin(a), 1.1, b.ring)
        tdisc(x, y, 1.2, b.ring)
    T.bumpers.append(b)
    return b


class Bank:
    def __init__(self, reward, every, respawn, points, name):
        self.reward = reward
        self.every = every          # For R_EXTRA: clears per extra ball
        self.respawn = respawn      # Frames until a knocked down target pops back up (0 = never)
        self.points = points
        self.name = name
        self.body = []
        self.eye = []
        self.kind = []
        self.up = []
        self.down_t = []
        self.clears = 0
        self.reset_t = 0


def add_bank(xs, y, sprite, up, eye, down, reward, every=3, respawn=0, points=750, name="TARGETS"):
    bank = Bank(reward, every, respawn, points, name)
    bank.c_up = rgbt(up)
    bank.c_eye = rgbt(eye)
    bank.c_down = rgbt(down)
    for x in xs:
        n = len(T.targets)
        body = new_solid(K_TARGET + n, up)
        e = new_solid(K_TARGET + n, eye)
        tsprite(sprite, x, y, {"#": body, "o": e})
        bank.body.append(body)
        bank.eye.append(e)
        bank.kind.append(K_TARGET + n)
        bank.up.append(True)
        bank.down_t.append(0)
        T.targets.append((bank, len(bank.up) - 1))
    T.banks.append(bank)
    return bank


def add_lanes(posts, lamp_y=29, letters=None):
    """Rollover lanes across the top, between posts. All lit = multiplier up."""
    T.lit = [False] * (len(posts) - 1)
    for i in range(len(posts) - 1):
        x0 = posts[i] + 2
        x1 = posts[i + 1] - 1
        z = new_zone(ZT_LANE, i)
        trect(x0, 15, x1 - x0, 9, z)
        lamp = new_lamp((0, 0, 0))
        cx = (posts[i] + posts[i + 1]) // 2
        if letters:
            ttext(letters[i], cx - 1, lamp_y - 2, lamp)
        else:
            for dx, dy in ((0, -2), (0, -1), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0),
                           (-1, 1), (1, 1), (-1, 2), (1, 2)):
                table[(lamp_y + dy) * TW + cx + dx] = lamp
        T.lane_lamps.append(lamp)
    for x in posts:
        tline(x + 0.5, 13, x + 0.5, 25, 1.0, P_POST)   # Centred on a pixel, so the tip is one pixel


def add_mult(y, xs=(33, 47, 61, 75)):
    for i in range(4):
        lamp = new_lamp((0, 0, 0))
        ttext(str(i + 2) + "X", xs[i], y, lamp)
        T.mult_lamps.append(lamp)


class Hole:
    def __init__(self, x, y, kick, role, count, name, points):
        self.x = x
        self.y = y
        self.kick = kick
        self.role = role
        self.count = count
        self.hits = 0
        self.name = name
        self.points = points
        self.lit = False


def add_hole(x, y, kick, role=H_PLAIN, count=3, name="HOLE!", points=2500, rim=(70, 70, 80)):
    h = Hole(x, y, kick, role, count, name, points)
    h.ring = new_lamp(rim)
    h.rim = rgbt(rim)
    tdisc(x, y, 5, h.ring)
    tdisc(x, y, 3.6, new_lamp((0, 0, 0)))
    z = new_zone(ZT_HOLE, h, (0, 0, 0))
    tdisc(x, y, 2.6, z)
    T.holes.append(h)
    return h


class Spinner:
    def __init__(self, x0, x1, y):
        self.x0 = x0
        self.x1 = x1
        self.y = y
        self.spin = 0               # Frames left spinning
        self.phase = 0


def add_spinner(x0, x1, y):
    s = Spinner(x0, x1, y)
    z = new_zone(ZT_SPIN, s)
    trect(x0, y - 1, x1 - x0, 3, z)
    T.spinners.append(s)
    return s


class Ramp:
    def __init__(self, pts, exit_v, name, points):
        self.pts = pts
        self.exit_v = exit_v
        self.name = name
        self.points = points
        self.cum = [0.0]
        for k in range(len(pts) - 1):
            dx = pts[k + 1][0] - pts[k][0]
            dy = pts[k + 1][1] - pts[k][1]
            self.cum.append(self.cum[-1] + math.sqrt(dx * dx + dy * dy))
        self.length = self.cum[-1]
        self.count = 0


def add_ramp(xl, xr, ytop, ybot, pts, exit_v, name, points=2000):
    """A ramp: a channel up to the entrance, then a wire ramp along pts. A ball
    going up the channel fast enough rides the ramp and drops out at the end."""
    r = Ramp(pts, exit_v, name, points)
    tline(xl, ybot, xl, ytop - 4, 1.0, P_WALL_HI)
    tline(xr, ybot, xr, ytop - 4, 1.0, P_WALL_HI)
    tline(xl, ytop - 4, xr, ytop - 4, 1.0, P_WALL_HI)
    # Peaked roof, so a ball landing on top rolls off instead of sitting there
    xc = (xl + xr) / 2
    tline(xl, ytop - 4, xc, ytop - 10, 1.0, P_WALL_HI)
    tline(xc, ytop - 10, xr, ytop - 4, 1.0, P_WALL_HI)
    for y in range(ytop - 9, ytop - 4):
        w = (y - (ytop - 10)) * (xr - xl) / 12
        trow(y, int(xc - w), int(xc + w) + 1, P_WALL)
    z = new_zone(ZT_RAMP, r)
    trect(int(xl) + 2, ytop, int(xr - xl) - 3, 4, z)
    T.ramps.append(r)
    return r


def paint_rails():
    """Ramp rails go on last, and only over plain background, so they look like they pass over it."""
    for r in T.ramps:
        pts = r.pts
        for side in (-1, 1):
            off = []
            for k in range(len(pts)):
                a = pts[max(0, k - 1)]
                b = pts[min(len(pts) - 1, k + 1)]
                dx = b[0] - a[0]
                dy = b[1] - a[1]
                ln = math.sqrt(dx * dx + dy * dy) or 1
                off.append((pts[k][0] - dy / ln * 4 * side, pts[k][1] + dx / ln * 4 * side))
            tpath(off, 0.5, P_RAIL, True)


class Door:
    def __init__(self, hits):
        self.need = hits
        self.hits = 0
        self.open = False
        self.cd = 0


def add_door(x, y, w, h, hits, wood, band):
    d = Door(hits)
    d.c_wood = rgbt(wood)
    d.c_band = rgbt(band)
    d.body = new_solid(K_DOOR, wood)
    d.bands = new_solid(K_DOOR, band)
    trect(x, y, w, h, d.body)
    for bx in range(x + 2, x + w - 1, 4):
        trect(bx, y, 1, h, d.bands)
    T.door = d
    return d


def add_kickback(lit):
    """Kickback in the left outlane: fires a ball that would drain back up."""
    z = new_zone(ZT_KICK, None)
    trect(3, 226, 8, 6, z)
    T.kick_lamp = new_lamp((0, 0, 0))
    for k in range(3):
        y = 206 + k * 5
        tline(5, y + 2, 7, y, 0.5, T.kick_lamp)
        tline(7, y, 9, y + 2, 0.5, T.kick_lamp)
    T.kick_lit = lit


# The shell every table shares: walls, rounded top, plunger lane, slingshots, flippers
ARC_R = 37
ARC_L = 40
ARC_RX = 87
ARC_Y = 40
SLING_KIDS = ((17, 163), (17, 181), (29, 203))
GUIDE_KIDS = ((3, 180), (25, 220))
SLING_OUT = ((25, 172), (25, 192), (34, 210))
GUIDE_OUT = ((12, 193), (25, 220))


def build_shell(outlanes):
    # Outer walls with rounded top corners. Everything outside is solid
    for y in range(TH):
        if y < 3:
            trow(y, 0, TW, P_ARC)
            continue
        if y < ARC_Y:
            dy = ARC_Y - y - 0.5
            w = math.sqrt(ARC_R * ARC_R - dy * dy) if dy < ARC_R else 0
            xl = int(ARC_L - w + 0.5)
            xr = int(ARC_RX + w + 0.999)     # Rounded up, so it meets the lane wall without a step
        else:
            xl = 3
            xr = 125
        top = y < ARC_Y
        trow(y, 0, xl, P_ARC if top else P_WALL)
        trow(y, xr, TW, P_ARC if top else P_WALL)
        table[y * TW + xl - 1] = P_ARC_HI if top else P_WALL_HI
        table[y * TW + xr] = P_ARC_HI if top else P_WALL_HI

    # Plunger lane: separator wall, gate, floor
    for y in range(72, TH):
        trow(y, 112, 115, P_WALL)
    tdisc(113.5, 72, 1.5, P_WALL_HI)
    tline(113.5, 70, 125, 60, 1.0, P_GATE)
    for y in range(PLUNGE_Y + PLUNGE_PULL + 2, TH):
        trow(y, 115, 125, P_WALL)

    ttext("SAVE", MID_X - 7, 239, P_SAVE)

    sling = SLING_OUT if outlanes else SLING_KIDS
    guide = GUIDE_OUT if outlanes else GUIDE_KIDS
    for side in (0, 1):
        g0, g1 = guide
        if side:
            g0, g1 = mirror(g0), mirror(g1)
        # Aprons outside the inlane guides
        for y in range(g0[1], TH):
            if y <= g1[1]:
                gx = g0[0] + (g1[0] - g0[0]) * (y - g0[1]) / (g1[1] - g0[1])
            else:
                gx = g1[0]
            if side:
                trow(y, int(gx), 103 if outlanes else 112, P_APRON)
            else:
                trow(y, 11 if outlanes else 3, int(gx) + 1, P_APRON)
        tline(g0[0], g0[1], g1[0], g1[1], 1.5, P_WALL_HI)
        if outlanes:
            # Post between the outlane and the inlane
            px = 102 if side else 12
            tline(px + 0.5, 170, px + 0.5, g0[1], 1.0, P_POST)
            tline(px, g0[1], px, TH, 1.0, P_WALL_HI)
        if outlanes:
            # Rubber guide above the outlane: a ball running down the side wall gets
            # turned into the inlane instead of dropping straight down the outlane
            gx0, gx1 = (111, 102) if side else (3, 12)
            tline(gx0, 150, gx1, 160, 1.2, P_GUIDE)
        fx = RFLIP_X if side else LFLIP_X
        tdisc(fx, FLIP_Y, 2, P_WALL)            # Hidden under the flipper's pivot

        a, b, c = sling
        if side:
            a, b, c = mirror(a), mirror(b), mirror(c)
        ttri(a, b, c, P_SLING_BODY)
        tline(a[0], a[1], b[0], b[1], 1.0, P_WALL_HI)
        tline(b[0], b[1], c[0], c[1], 1.0, P_WALL_HI)
        tline(a[0], a[1], c[0], c[1], 1.2, P_SLING_R if side else P_SLING_L)


# ---------------------------------------------------------------------------
# The tables
# ---------------------------------------------------------------------------
ALIEN = ("..####..", ".######.", "##o##o##", "########", ".#.##.#.", "#......#")
EGG = ("..###..", ".#####.", ".##o##.", "#######", "##o####", "#####o#", ".#####.", "..###..")
SKULL = (".#####.", "#######", "#oo#oo#", "###o###", ".#####.", ".#.#.#.")
TROLL = ("..####..", ".#o##o#.", ".######.", "#.#oo#.#", "..####..", ".##..##.", ".#....#.")
BOLT = ("..###..", ".#####.", "##ooo##", "##o#o##", "##ooo##", ".#####.", "..###..")


def space_decor():
    specks(1234, 170, 3, 3, 112, TH, (1, 2, 3))
    px, py, prad = MID_X, 160, 12
    for y in range(py - prad, py + prad + 1):
        for x in range(px - prad, px + prad + 1):
            dx = x + 0.5 - px
            dy = y + 0.5 - py
            if dx * dx + dy * dy <= prad * prad:
                lit = (dx + 4) * (dx + 4) + (dy + 4) * (dy + 4) < (prad + 3) * (prad + 3)
                table[y * TW + x] = 4 if lit else 5
    for cx, cy in ((53, 155), (61, 163), (51, 165)):
        table[cy * TW + cx] = 7
        table[cy * TW + cx + 1] = 7
    for i in range(160):
        a = i * 2 * math.pi / 160
        x = px + 21 * math.cos(a)
        y = py + 5 * math.sin(a) - 3 * math.cos(a)
        if not (math.sin(a) < 0 and abs(x - px) < prad):
            table[int(y) * TW + int(x)] = 6
    for ax in (20, 94):
        for k in range(3):
            y = 140 + k * 6
            tline(ax - 3, y + 3, ax, y, 0.5, 8)
            tline(ax, y, ax + 3, y + 3, 0.5, 8)


def space_build():
    add_lanes((30, 48, 66, 84))
    add_bumper(39, 56, 7, (230, 60, 60))
    add_bumper(75, 56, 7, (60, 130, 255))
    add_bumper(57, 79, 7, (255, 150, 30))
    add_mult(98)
    add_bank((34, 47, 60, 73), 118, ALIEN, (90, 235, 90), (10, 20, 10), (30, 50, 40),
             R_EXTRA, every=3, name="ALIENS")


def dino_decor():
    specks(777, 260, 3, 3, 112, TH, (1, 2, 3))
    # Volcano under the bumpers, with lava at the top
    ttri((31, 84), (83, 84), (57, 40), 4)
    ttri((57, 40), (83, 84), (66, 84), 5)
    for k in range(5):
        tline(57 - k, 42 + k * 2, 57 + k, 42 + k * 2, 0.6, 6)
    tline(54, 44, 50, 58, 0.7, 7)
    tline(60, 44, 64, 54, 0.7, 7)
    # T-rex head around the hole on the left
    trect(5, 93, 23, 6, 8)
    trect(5, 109, 21, 4, 8)
    trect(5, 99, 6, 10, 8)
    for x in range(12, 27, 3):
        table[99 * TW + x] = 10
        table[108 * TW + x] = 10
    table[95 * TW + 9] = 11
    table[95 * TW + 10] = 11
    # Palm leaves at the sides
    for cx, cy in ((10, 148), (104, 148)):
        for a in range(5):
            ang = -2.6 + a * 0.55
            tline(cx, cy, cx + 9 * math.cos(ang), cy + 7 * math.sin(ang) + 4, 0.6, 9)
        tline(cx, cy, cx, cy + 14, 0.6, 12)


def dino_build():
    add_lanes((30, 48, 66, 84), letters="DNA")
    add_bumper(43, 54, 6, (230, 70, 30), (255, 190, 60))
    add_bumper(71, 54, 6, (230, 70, 30), (255, 190, 60))
    add_bumper(57, 73, 6, (230, 70, 30), (255, 190, 60))
    add_hole(20, 104, (2.8, -2.2), H_COUNT, 3, "CHOMP!", rim=(60, 120, 50))
    tline(46.5, 96, 46.5, 104, 1.0, P_POST)
    tline(68.5, 96, 68.5, 104, 1.0, P_POST)
    add_spinner(48, 67, 100)
    add_bank((66, 78, 90), 112, EGG, (240, 230, 200), (110, 170, 90), (60, 60, 45),
             R_EXTRA, every=2, name="EGGS")
    add_mult(132)


def pirate_decor():
    # Waves
    for y in range(12, TH, 14):
        for x in range(3, 112):
            if (x + y // 2) % 12 < 5:
                wy = y + (2 if (x + y // 2) % 12 in (1, 2, 3) else 3)
                table[wy * TW + x] = 1 if (y // 14) & 1 else 2
    # Ship in the middle: hull, mast, sail, flag
    ttri((32, 146), (82, 146), (38, 158), 3)
    ttri((82, 146), (38, 158), (76, 158), 3)
    trow(146, 32, 83, 4)
    for x in range(40, 76, 6):
        tdisc(x + 0.5, 152, 1.2, 4)
    trect(56, 126, 2, 20, 4)
    ttri((40, 128), (56, 128), (56, 143), 5)
    ttri((74, 130), (58, 130), (58, 143), 5)
    trect(58, 122, 7, 4, 6)
    table[123 * TW + 61] = 7
    # Treasure chest around the hole
    trect(49, 118, 17, 3, 8)
    trect(49, 126, 17, 3, 8)


def pirate_build():
    add_lanes((30, 48, 66, 84), letters="ARR")
    add_bumper(40, 52, 7, (150, 90, 40), (210, 160, 90))
    add_bumper(74, 52, 7, (150, 90, 40), (210, 160, 90))
    add_mult(66)
    add_bank((72, 82, 92), 96, SKULL, (240, 240, 230), (20, 20, 20), (50, 60, 80),
             R_KICK, name="SKULLS")
    add_hole(57, 122, (-1.6, -3.0), H_COUNT, 3, "TREASURE!", rim=(255, 200, 40))
    add_ramp(15, 29, 96, 128, ((22, 96), (22, 58), (25, 46), (34, 38), (46, 34), (57, 34)),
             (0.4, 1.4), "MAST RAMP!")
    add_kickback(True)


def castle_decor():
    # Stone bricks
    for y in range(4, TH, 6):
        trow(y, 3, 112, 1)
        off = 0 if (y // 6) & 1 else 6
        for x in range(3 + off, 112, 12):
            for yy in range(y + 1, min(TH, y + 6)):
                table[yy * TW + x] = 1
    # Torches by the lanes
    for x in (22, 92):
        trect(x, 50, 2, 6, 2)
        tdisc(x + 1, 48, 1.6, 3)
        table[47 * TW + x] = 4
    # Banners low on the table
    for x in (20, 90):
        trect(x, 132, 7, 12, 5)
        ttri((x, 144), (x + 7, 144), (x + 3, 148), 5)
        trect(x + 2, 135, 3, 3, 6)


def castle_build():
    add_lanes((30, 48, 66, 84))
    # The castle: towers, walls and a peaked roof, with a pocket behind the gate
    ttri((37, 45), (77, 45), (57, 34), P_S1)
    trect(37, 45, 41, 26, P_S1)
    trect(48, 50, 19, 16, P_S2)             # Pocket (dark, made not-solid below)
    for x in (38, 72):
        trect(x, 46, 4, 6, P_S3)            # Windows
    for x in range(38, 77, 6):
        trect(x, 44, 3, 2, P_WALL_HI)
    kinds[P_S2] = K_AIR
    add_door(48, 66, 19, 5, 3, (140, 90, 40), (60, 60, 70))
    add_hole(57, 57, (0.0, 3.2), H_LOCK, name="CASTLE!", points=5000, rim=(90, 80, 70))
    # Bumpers off to the sides, leaving a clear shot at the gate from both flippers
    add_bumper(36, 86, 5, (200, 40, 50), (240, 200, 90))
    add_bumper(78, 86, 5, (200, 40, 50), (240, 200, 90))
    add_bank((30, 68), 104, TROLL, (120, 170, 80), (230, 60, 40), (50, 60, 50),
             R_KICK, respawn=480, points=1000, name="TROLLS")
    add_mult(124)
    # Left orbit with a spinner
    tline(16.5, 58, 16.5, 140, 1.0, P_WALL_HI)
    add_spinner(3, 15, 112)
    add_ramp(87, 102, 100, 132, ((94.5, 100), (94.5, 52), (90, 38), (78, 30), (57, 28), (30, 30),
                                 (16, 38), (9, 50), (9, 58)), (0.0, 1.6), "CATAPULT!", 2500)
    add_kickback(False)


def robot_decor():
    for y in range(8, TH, 8):
        trow(y, 3, 112, 1)
    for x in range(8, 112, 8):
        for y in range(3, TH):
            if table[y * TW + x] == 0:
                table[y * TW + x] = 1
    for x in range(3, 112):
        for y in (4, 5):
            table[y * TW + x] = 2 if (x // 3) & 1 else 3
    # Robot face low on the table
    trect(39, 140, 37, 26, 4)
    trect(41, 142, 33, 22, 5)
    trect(56, 134, 3, 6, 4)
    tdisc(57.5, 133, 2, 6)
    for x in range(45, 71, 5):
        trect(x, 158, 3, 3, 4)


def robot_build():
    add_lanes((30, 48, 66, 84), letters="BOT")
    add_bumper(40, 56, 6, (90, 110, 140), (200, 220, 240), gear=True)
    add_bumper(74, 56, 6, (90, 110, 140), (200, 220, 240), gear=True)
    add_bumper(57, 72, 6, (90, 110, 140), (200, 220, 240), gear=True)
    add_hole(57, 90, (1.4, 2.6), H_LOCK, name="LOCKED!", points=1000, rim=(80, 90, 110))
    add_bank((34, 46, 58, 70), 104, BOLT, (230, 190, 40), (90, 70, 20), (60, 55, 30),
             R_LOCK, points=500, name="BOLTS")
    add_mult(124)
    add_ramp(14, 28, 92, 126, ((21, 92), (21, 54), (24, 42), (33, 35), (44, 34)), (1.0, 1.0),
             "LEFT RAMP!")
    add_ramp(86, 100, 92, 126, ((93, 92), (93, 54), (90, 42), (81, 35), (70, 34)), (-1.0, 1.0),
             "RIGHT RAMP!")
    add_spinner(16, 27, 112)
    add_spinner(88, 99, 112)
    # Robot eyes light up when the lock is lit
    eye = new_lamp((0, 0, 0))
    trect(46, 146, 7, 5, eye)
    trect(62, 146, 7, 5, eye)
    T.eye_lamp = eye
    add_kickback(False)


# Each table: name, difficulty, ball save frames, outlanes, multiball size,
# colours (index: rgb), slingshot rubber colour, painter and builder
TABLES = (
    {"name": "SPACE", "level": "EASY", "save": 600, "out": False, "mb": 2,
     "pal": {0: (6, 4, 22), 1: (70, 70, 110), 2: (140, 140, 190), 3: (255, 255, 255),
             4: (90, 200, 230), 5: (40, 90, 140), 6: (230, 190, 120), 7: (60, 140, 180),
             8: (70, 50, 140), 15: (150, 150, 200),
             64: (60, 50, 120), 65: (150, 140, 230), 66: (210, 210, 240), 69: (45, 40, 100),
             70: (30, 24, 70)},
     "rubber": (255, 70, 150), "decor": space_decor, "build": space_build},
    {"name": "DINO PARK", "level": "EASY", "save": 600, "out": False, "mb": 2,
     "pal": {0: (8, 26, 14), 1: (20, 55, 28), 2: (30, 80, 38), 3: (55, 115, 45),
             4: (90, 60, 40), 5: (70, 45, 30), 6: (255, 120, 30), 7: (255, 190, 60),
             8: (70, 140, 60), 9: (60, 150, 60), 10: (250, 250, 240), 11: (230, 40, 40),
             12: (110, 75, 40), 15: (190, 170, 120),
             64: (100, 64, 32), 65: (190, 140, 80), 66: (230, 210, 170), 69: (60, 40, 20),
             70: (40, 28, 14)},
     "rubber": (120, 230, 90), "decor": dino_decor, "build": dino_build},
    {"name": "PIRATE SHIP", "level": "MEDIUM", "save": 480, "out": True, "mb": 2,
     "pal": {0: (6, 22, 50), 1: (20, 55, 100), 2: (35, 85, 140), 3: (100, 65, 35),
             4: (70, 42, 22), 5: (230, 225, 200), 6: (20, 20, 20), 7: (240, 240, 240),
             8: (200, 150, 40), 15: (200, 180, 140),
             64: (120, 80, 45), 65: (200, 160, 100), 66: (230, 220, 190), 69: (70, 40, 20),
             70: (40, 25, 12)},
     "rubber": (230, 60, 50), "decor": pirate_decor, "build": pirate_build},
    {"name": "CASTLE", "level": "HARD", "save": 360, "out": True, "mb": 3,
     "pal": {0: (22, 20, 30), 1: (34, 32, 44), 2: (90, 60, 30), 3: (255, 150, 40),
             4: (255, 230, 120), 5: (170, 30, 40), 6: (230, 180, 40), 15: (170, 160, 150),
             64: (110, 108, 120), 65: (190, 188, 200), 66: (220, 215, 200), 69: (60, 58, 70),
             70: (40, 38, 50), 72: (120, 118, 130), 73: (12, 10, 16), 74: (255, 200, 80)},
     "rubber": (230, 180, 40), "decor": castle_decor, "build": castle_build},
    {"name": "ROBOT FACTORY", "level": "HARD", "save": 360, "out": True, "mb": 3,
     "pal": {0: (14, 16, 22), 1: (24, 28, 38), 2: (230, 190, 30), 3: (30, 30, 30),
             4: (120, 130, 150), 5: (60, 66, 80), 6: (255, 80, 80), 15: (120, 200, 230),
             64: (80, 100, 130), 65: (170, 200, 235), 66: (220, 230, 240), 69: (40, 48, 62),
             70: (24, 28, 38)},
     "rubber": (80, 255, 240), "decor": robot_decor, "build": robot_build},
)
P_S2 = const(73)
P_S3 = const(74)


def build_table(i):
    """Paint table i and set up its features."""
    global T
    spec = TABLES[i]
    T = TableState()
    T.spec = spec
    T.eye_lamp = -1
    for k in range(256):
        palette[k] = 0
        kinds[k] = K_AIR
        zones[k] = 0
    for k, c in spec["pal"].items():
        palette[k] = rgbt(c)
    T.bg = palette[P_BG]
    for k in range(64, 80):
        kinds[k] = K_WALL
    kinds[P_SLING_L] = K_SLING_L
    kinds[P_SLING_R] = K_SLING_R
    kinds[P_ARC] = K_RAIL
    kinds[P_GUIDE] = K_GUIDE
    palette[P_GUIDE] = palette[P_POST]
    kinds[P_ARC_HI] = K_RAIL
    palette[P_ARC] = palette[P_WALL]
    palette[P_ARC_HI] = palette[P_WALL_HI]
    T.rubber = rgbt(spec["rubber"])
    T.wall_hi = palette[P_WALL_HI]
    for y in range(TH):
        trow(y, 0, TW, P_BG)
    spec["decor"]()
    build_shell(spec["out"])
    spec["build"]()
    paint_rails()


def lamp(i, on, lit, unlit):
    palette[i] = lit if on else unlit


L_ON = rgb(255, 220, 60)
L_OFF = rgb(70, 60, 30)
M_ON = rgb(255, 170, 40)
M_OFF = rgb(60, 40, 30)


def update_lamps():
    """Set the palette entries for everything that lights up or changes."""
    f = G.frame
    for b in T.bumpers:
        if b.flash:
            palette[b.core] = C_WHITE
            palette[b.ring] = rgb(255, 255, 160)
        else:
            palette[b.core] = b.color
            palette[b.ring] = b.ring_color
    lamp(P_SLING_L, G.sling_flash[0], C_WHITE, T.rubber)
    lamp(P_SLING_R, G.sling_flash[1], C_WHITE, T.rubber)
    for i in range(len(T.lane_lamps)):
        lamp(T.lane_lamps[i], T.lit[i], L_ON, L_OFF)
    for i in range(len(T.mult_lamps)):
        lamp(T.mult_lamps[i], G.mult >= i + 2, M_ON, M_OFF)
    for bank in T.banks:
        for i in range(len(bank.up)):
            up = bank.up[i]
            palette[bank.body[i]] = bank.c_up if up else bank.c_down
            palette[bank.eye[i]] = bank.c_eye if up else bank.c_down
            k = bank.kind[i] if up else K_AIR
            kinds[bank.body[i]] = k
            kinds[bank.eye[i]] = k
    for h in T.holes:
        lit = (h.role == H_LOCK and lock_ready(h)) or (h.role == H_COUNT and h.hits > 0)
        if h.role == H_COUNT and h.hits > 0 and h.hits < h.count:
            lit = (f >> (5 - h.hits)) & 1      # Blinks faster as it gets closer
        lamp(h.ring, lit, L_ON, h.rim)
    d = T.door
    if d:
        if d.open:
            palette[d.body] = palette[P_S2]
            palette[d.bands] = palette[P_S2]
            kinds[d.body] = K_AIR
            kinds[d.bands] = K_AIR
        else:
            k = d.hits * 60
            palette[d.body] = C_WHITE if d.cd > 10 else d.c_wood - (k >> 3 << 11)
            palette[d.bands] = d.c_band
            kinds[d.body] = K_DOOR
            kinds[d.bands] = K_DOOR
    if T.kick_lamp >= 0:
        lamp(T.kick_lamp, T.kick_lit, rgb(255, 80, 60), rgb(60, 30, 30))
    if T.eye_lamp >= 0:
        lit = any(h.lit for h in T.holes)
        lamp(T.eye_lamp, lit and (f >> 3) & 1 or G.multi, rgb(80, 255, 240), rgb(20, 60, 60))
    save = G.save_t > 0 and (G.save_t > 120 or (f >> 3) & 1)
    lamp(P_SAVE, save, rgb(80, 255, 120), rgb(25, 50, 35))
    kinds[P_GATE] = K_WALL if G.gate else K_AIR
    lamp(P_GATE, G.gate, T.wall_hi, T.bg)


# ---------------------------------------------------------------------------
# Sound
# ---------------------------------------------------------------------------
class Sound:
    # Setting a tone's frequency fades it out and back in (about 9ms), and a tone's
    # clock only resets when it's created. So every blip gets a fresh tone, and
    # tunes are played one fresh tone per note.
    def __init__(self):
        self.frames = [0, 0, 0]     # Frames left on each channel
        self.tune = []              # Notes still to play on channel 0: (freq, frames)

    def tone(self, freq, channel, gain):
        try:
            engine_audio.stop(channel)
            t = ToneSoundResource()
            t.frequency = freq
            ch = engine_audio.play(t, channel, True)
            ch.gain = gain
        except Exception:
            pass

    def blip(self, freq, frames=3, channel=2, gain=0.2):
        self.tone(freq, channel, gain)
        self.frames[channel] = frames

    def play(self, notes):
        self.tune = list(notes)
        self.frames[0] = 0

    def tick(self):
        for c in range(3):
            if self.frames[c] > 0:
                self.frames[c] -= 1
                if self.frames[c] == 0:
                    if c == 0 and self.tune:
                        continue
                    try:
                        engine_audio.stop(c)
                    except Exception:
                        pass
        if self.tune and self.frames[0] == 0:
            freq, n = self.tune.pop(0)
            if freq:
                self.tone(freq, 0, 0.18)
            else:
                try:
                    engine_audio.stop(0)
                except Exception:
                    pass
            self.frames[0] = n


sound = Sound()

T_GOOD = ((700, 4), (900, 4), (1200, 8))
T_BIG = ((800, 4), (1000, 4), (1200, 4), (1600, 8))
T_MULTI = ((523, 5), (659, 5), (784, 5), (1047, 5), (784, 4), (1047, 12))


# ---------------------------------------------------------------------------
# Balls and flippers
# ---------------------------------------------------------------------------
class Ball:
    def __init__(self, x, y, mode):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.mode = mode
        self.zone = 0               # Zone the ball is in, so entering one only counts once
        self.in_lane = True         # In the plunger lane, so the gate stays open
        self.timer = 0
        self.hole = None
        self.ramp = None
        self.dist = 0.0
        self.still_t = 0            # Frames the ball has hardly moved
        self.still_x = x
        self.still_y = y


class Flipper:
    def __init__(self, x, side):
        self.px = x
        self.py = FLIP_Y
        self.side = side            # 1 for the left flipper, -1 for the right
        self.ang = FLIP_REST
        self.a0 = FLIP_REST
        self.w = 0.0                # Angle change this frame
        self.tvx = 0.0              # Tip velocity per frame
        self.tvy = 0.0
        self.up = False
        self.pose(0.0)

    def pose(self, f):
        """Put the flipper f of the way through this frame's swing."""
        a = self.a0 + self.w * f
        c = math.cos(a)
        s = math.sin(a)
        self.tx = self.px + self.side * FLIP_LEN * c
        self.ty = self.py + FLIP_LEN * s
        self.tvx = -self.side * FLIP_LEN * s * self.w
        self.tvy = FLIP_LEN * c * self.w

    def begin(self):
        """Work out this frame's swing."""
        target = FLIP_UP if self.up else FLIP_REST
        d = target - self.ang
        lim = FLIP_W_UP if self.up else FLIP_W_DOWN
        if d > lim:
            d = lim
        elif d < -lim:
            d = -lim
        self.a0 = self.ang
        self.w = d
        self.target = target
        if d == 0:
            self.tvx = 0.0
            self.tvy = 0.0

    def end(self):
        if self.w:
            self.ang = self.a0 + self.w
            if abs(self.ang - self.target) < 0.0001:
                self.ang = self.target
            self.a0 = self.ang
            self.w = 0.0
            self.pose(0.0)

    def collide(self, b):
        ax = self.px
        ay = self.py
        rx = b.x - ax
        ry = b.y - ay
        if ry < -14 or ry > 20 or rx * self.side < -8 or rx * self.side > 31:
            return
        dx = self.tx - ax
        dy = self.ty - ay
        t = (rx * dx + ry * dy) / (FLIP_LEN * FLIP_LEN)
        if t < 0:
            t = 0.0
        elif t > 1:
            t = 1.0
        qx = ax + dx * t
        qy = ay + dy * t
        ex = b.x - qx
        ey = b.y - qy
        rr = BALL_R + FLIP_R0 - (FLIP_R0 - FLIP_R1) * t
        d2 = ex * ex + ey * ey
        if d2 >= rr * rr:
            return
        d = math.sqrt(d2)
        if d < 0.01:
            # Dead centre: push out of the top face
            nx = dy * self.side / FLIP_LEN
            ny = -dx * self.side / FLIP_LEN
        else:
            nx = ex / d
            ny = ey / d
        b.x = qx + nx * rr
        b.y = qy + ny * rr
        svx = self.tvx * t
        svy = self.tvy * t
        rvx = b.vx - svx
        rvy = b.vy - svy
        vn = rvx * nx + rvy * ny
        if vn < 0:
            rvx -= (1 + E_FLIP) * vn * nx
            rvy -= (1 + E_FLIP) * vn * ny
            b.vx = rvx + svx
            b.vy = rvy + svy


def hit_walls(b):
    """Push the ball out of any table wall it overlaps and bounce it."""
    n = probe(int(b.x * 16), int(b.y * 16))
    if n == 0:
        return
    if pr[3] == K_GUIDE and b.vy < 0:
        # One way: a ball going up (a kickback shot) passes through the outlane
        # guide, but must still hit the side wall the guide is joined to
        kinds[P_GUIDE] = K_AIR
        n = probe(int(b.x * 16), int(b.y * 16))
        kinds[P_GUIDE] = K_GUIDE
        if n == 0:
            return
    sx = pr[0]
    sy = pr[1]
    ln = math.sqrt(sx * sx + sy * sy)
    if ln < 1:
        # Walls all round: back out the way we came
        sp = math.sqrt(b.vx * b.vx + b.vy * b.vy)
        if sp < 0.01:
            nx, ny = 0.0, -1.0
        else:
            nx = -b.vx / sp
            ny = -b.vy / sp
    else:
        nx = -sx / ln
        ny = -sy / ln
    pen = CONTACT - math.sqrt(pr[2]) / 16
    if pen > 0:
        if pen > 1.5:
            pen = 1.5
        b.x += nx * pen
        b.y += ny * pen
    kind = pr[3]
    vn = b.vx * nx + b.vy * ny
    if K_BUMP <= kind < K_TARGET:
        bp = T.bumpers[kind - K_BUMP]
        if bp.cd == 0:
            # Pop bumpers fire the ball straight away from their middle
            tx = b.vx - vn * nx
            ty = b.vy - vn * ny
            b.vx = nx * BUMP_V + tx * 0.4
            b.vy = ny * BUMP_V + ty * 0.4
            bp.cd = 6
            bp.flash = 6
            add_score(100)
            count("bump")
            sound.blip(880 + 160 * (kind - K_BUMP), 3)
            return
    if vn < 0:
        e = E_RAIL if kind == K_RAIL else E_WALL
        b.vx -= (1 + e) * vn * nx
        b.vy -= (1 + e) * vn * ny
        if kind == K_SLING_L or kind == K_SLING_R:
            i = kind - K_SLING_L
            if vn < -0.4 and G.sling_cd[i] == 0:
                b.vx += nx * SLING_V
                b.vy += ny * SLING_V
                G.sling_cd[i] = 8
                G.sling_flash[i] = 5
                add_score(10)
                count("sling")
                sound.blip(600, 2)
        elif K_TARGET <= kind < K_DOOR:
            target_hit(kind - K_TARGET)
        elif kind == K_DOOR and vn < -0.5:
            door_hit()


def physics(b, moving):
    """Move one ball for a frame in small steps. moving is True while a flipper swings."""
    sp = abs(b.vx) + abs(b.vy)
    n = 2 + int(sp * 1.3)
    near = b.y > 185
    if near and moving and n < 8:
        n = 8           # Small steps while a flipper swings, so it can't jump past the ball
    inv = 1.0 / n
    g = GRAVITY * inv
    for k in range(n):
        b.vy += g
        b.x += b.vx * inv
        b.y += b.vy * inv
        hit_walls(b)
        z = pr[4]
        if z != b.zone:
            b.zone = z
            if z and enter_zone(b, z):
                return
        if near or b.y > 185:
            if moving:
                f = (k + 1) * inv
                lflip.pose(f)
                rflip.pose(f)
            lflip.collide(b)
            rflip.collide(b)
    b.vx *= 0.999
    b.vy *= 0.999
    s2 = b.vx * b.vx + b.vy * b.vy
    if s2 > V_MAX * V_MAX:
        k = V_MAX / math.sqrt(s2)
        b.vx *= k
        b.vy *= k


def collide_balls():
    """Balls knock each other about (multiball)."""
    n = len(balls)
    for i in range(n):
        a = balls[i]
        if a.mode != M_PLAY:
            continue
        for j in range(i + 1, n):
            b = balls[j]
            if b.mode != M_PLAY:
                continue
            dx = b.x - a.x
            dy = b.y - a.y
            d2 = dx * dx + dy * dy
            if d2 < 36 and d2 > 0.0001:
                d = math.sqrt(d2)
                nx = dx / d
                ny = dy / d
                push = (6 - d) / 2
                a.x -= nx * push
                a.y -= ny * push
                b.x += nx * push
                b.y += ny * push
                vn = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
                if vn < 0:
                    a.vx += vn * nx * 0.95
                    a.vy += vn * ny * 0.95
                    b.vx -= vn * nx * 0.95
                    b.vy -= vn * ny * 0.95


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.state = ST_TITLE
        self.frame = 0
        self.timer = 0
        self.paused = False
        self.table_i = 0
        self.stats = {}
        self.reset()

    def reset(self):
        self.score = 0
        self.ball_no = 1
        self.balls_left = BALLS     # Including the one in play
        self.extra_balls = 0
        self.bstate = B_LIVE
        self.btimer = 0
        self.charge = 0.0
        self.gate = False
        self.save_t = 0
        self.mult = 1
        self.multi = False          # Multiball running
        self.spawn = 0              # Balls still to fire for multiball
        self.spawn_t = 0
        self.sling_cd = [0, 0]
        self.sling_flash = [0, 0]
        self.cam = float(CAM_MAX)
        self.shake = 0
        self.nudge_cd = 0
        self.msg = ""
        self.msg2 = ""
        self.msg_t = 0
        self.unsticks = 0
        self.escapes = 0
        self.new_hi = False
        self.stats = {}


G = Game()
balls = []
lflip = Flipper(LFLIP_X, 1)
rflip = Flipper(RFLIP_X, -1)

engine_save._init_saves_dir("Saves/Games/Pinball")
engine_save.set_location("save")

hiscores = [0] * len(TABLES)


def hi_key(i):
    return "hi" if i == 0 else "hi" + str(i)     # Table 0 keeps the key from before there were others


def load_saves():
    for i in range(len(TABLES)):
        try:
            hiscores[i] = int(engine_save.load(hi_key(i), 0))
        except Exception:
            hiscores[i] = 0
    try:
        G.table_i = int(engine_save.load("tbl", 0)) % len(TABLES)
    except Exception:
        G.table_i = 0


def save_hi(i):
    try:
        engine_save.save(hi_key(i), hiscores[i])
    except Exception:
        pass


def save_table_choice():
    try:
        engine_save.save("tbl", G.table_i)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Game rules
# ---------------------------------------------------------------------------
def count(name):
    G.stats[name] = G.stats.get(name, 0) + 1


def show(msg, msg2="", frames=90):
    G.msg = msg
    G.msg2 = msg2
    G.msg_t = frames


def add_score(points):
    G.score += points * G.mult * (2 if G.multi else 1)


def serve():
    """Put a ball on the plunger."""
    G.charge = 0.0
    G.save_t = 0
    b = Ball(LANE_X, SERVE_Y, M_SERVE)
    balls.append(b)
    return b


def auto_launch():
    """The machine fires a ball up the plunger lane by itself (multiball)."""
    b = Ball(LANE_X, SERVE_Y, M_PLAY)
    b.vy = -AUTO_V
    balls.append(b)
    sound.play(((300, 2), (450, 2), (650, 3)))


def start_game():
    G.reset()
    reset_table()
    G.state = ST_PLAY
    G.paused = False
    balls[:] = []
    serve()
    show("BALL 1", T.spec["name"], 70)


def reset_table():
    """Put every feature back to how it starts."""
    T.lit = [False] * len(T.lane_lamps)
    for bank in T.banks:
        for i in range(len(bank.up)):
            bank.up[i] = True
            bank.down_t[i] = 0
        bank.clears = 0
        bank.reset_t = 0
    for h in T.holes:
        h.hits = 0
        h.lit = False
    for s in T.spinners:
        s.spin = 0
    for r in T.ramps:
        r.count = 0
    if T.door:
        T.door.hits = 0
        T.door.open = False
    T.kick_lit = T.kick_lamp >= 0 and T.spec["name"] == "PIRATE SHIP"
    T.last_ramp = None


def flipper_buttons():
    return (engine_io.LB.is_pressed or engine_io.LEFT.is_pressed,
            engine_io.RB.is_pressed or engine_io.A.is_pressed)


def update_flippers():
    lp, rp = flipper_buttons()
    if lp and not lflip.up:
        sound.blip(170, 2, 1, 0.15)
        T.lit = T.lit[1:] + T.lit[:1]       # Lane change: the lit lanes slide left
    if rp and not rflip.up:
        sound.blip(190, 2, 1, 0.15)
        T.lit = T.lit[-1:] + T.lit[:-1]
    lflip.up = lp
    rflip.up = rp


def serve_tick(b):
    if engine_io.DOWN.is_pressed:
        if G.charge < 1:
            G.charge = min(1.0, G.charge + 1 / 40)
            if G.frame % 4 == 0:
                sound.blip(200 + int(G.charge * 300), 2)
    elif G.charge > 0:
        b.vy = -(LAUNCH_MIN + (LAUNCH_MAX - LAUNCH_MIN) * G.charge)
        b.vx = 0.0
        b.y = SERVE_Y
        G.charge = 0.0
        b.mode = M_PLAY
        b.in_lane = True
        b.served = True
        sound.play(((300, 2), (450, 2), (650, 3)))
        return
    b.x = LANE_X
    b.y = SERVE_Y + G.charge * PLUNGE_PULL


def target_hit(n):
    bank, i = T.targets[n]
    if not bank.up[i]:
        return
    bank.up[i] = False
    bank.down_t[i] = bank.respawn
    add_score(bank.points)
    count("target")
    sound.blip(1400, 4)
    if not any(bank.up):
        bank_cleared(bank)


def bank_cleared(bank):
    bank.clears += 1
    count("bank")
    add_score(3000)
    if bank.respawn:
        for i in range(len(bank.up)):
            bank.down_t[i] = 45         # Pop straight back up
    else:
        bank.reset_t = 60
    if bank.reward == R_EXTRA:
        if bank.clears % bank.every == 0 and G.extra_balls < MAX_EXTRA:
            G.balls_left += 1
            G.extra_balls += 1
            show("EXTRA BALL!", "", 120)
            sound.play(((880, 5), (1100, 5), (1320, 5), (1760, 14)))
            return
        show(bank.name + " DOWN!", commas(3000 * G.mult), 90)
    elif bank.reward == R_KICK:
        T.kick_lit = True
        show(bank.name + " DOWN!", "KICKBACK IS LIT", 90)
    else:
        for h in T.holes:
            if h.role == H_LOCK:
                h.lit = True
        show(bank.name + " DOWN!", "LOCK IS LIT", 90)
    sound.play(T_GOOD)


def door_hit():
    d = T.door
    if d.open or d.cd:
        return
    d.cd = 15
    d.hits += 1
    add_score(1000)
    count("door")
    G.shake = 4
    sound.blip(140, 6)
    if d.hits >= d.need:
        d.open = True
        show("GATE OPEN!", "SHOOT THE CASTLE", 90)
        sound.play(T_BIG)
    else:
        show("CRASH!", str(d.need - d.hits) + " MORE HITS", 50)


def lock_ready(h):
    if T.door:
        return T.door.open
    return h.lit


def lane_hit(i):
    if T.lit[i]:
        add_score(100)
    else:
        T.lit[i] = True
        add_score(500)
    count("lane")
    sound.blip(1500, 3)
    if all(T.lit):
        T.lit = [False] * len(T.lit)
        add_score(2000)
        if G.mult < 5:
            G.mult += 1
            show(str(G.mult) + "X MULTIPLIER", "", 90)
        else:
            show("LANES DONE!", commas(2000 * G.mult), 70)
        sound.play(T_BIG)


def enter_zone(b, z):
    """The ball has just moved onto zone z. Returns True if it was taken off the table."""
    zt, thing = T.zone_map[z]
    if zt == ZT_LANE:
        lane_hit(thing)
    elif zt == ZT_SPIN:
        sp = abs(b.vx) + abs(b.vy)
        thing.spin = min(90, thing.spin + int(sp * 10))
        count("spin")
    elif zt == ZT_HOLE:
        if abs(b.vx) + abs(b.vy) < HOLE_V:
            catch_ball(b, thing)
            return True
    elif zt == ZT_RAMP:
        if b.vy < -1.0:
            b.mode = M_RAMP
            b.ramp = thing
            b.dist = 0.0
            ramp_entered(thing)
            return True
    elif zt == ZT_KICK:
        if T.kick_lit:
            T.kick_lit = False
            b.x = 7.0
            b.vx = 0.0
            b.vy = -KICK_V
            count("kick")
            show("KICKBACK!", "", 50)
            sound.play(((200, 3), (400, 3), (800, 5)))
    return False


def catch_ball(b, h):
    b.mode = M_HOLE
    b.hole = h
    b.x = float(h.x)
    b.y = float(h.y)
    b.vx = 0.0
    b.vy = 0.0
    b.timer = 50
    count("hole")
    add_score(h.points)
    sound.play(((300, 4), (200, 4), (150, 6)))
    if h.role == H_COUNT:
        h.hits += 1
        if h.hits >= h.count and not G.multi:
            h.hits = 0
            start_multiball(b, h.name)
        else:
            show(h.name, str(h.count - h.hits) + " MORE FOR MULTIBALL" if not G.multi else "", 60)
    elif h.role == H_LOCK and lock_ready(h) and not G.multi:
        h.lit = False
        start_multiball(b, h.name)
    else:
        show(h.name, commas(h.points * G.mult), 50)


def start_multiball(b, name):
    G.multi = True
    G.spawn = T.spec["mb"] - 1
    G.spawn_t = 30
    G.save_t = 900
    b.timer = 90
    count("multiball")
    show("MULTIBALL!", name + " DOUBLE SCORE", 120)
    sound.play(T_MULTI)


def end_multiball():
    G.multi = False
    G.spawn = 0
    if T.door:
        T.door.open = False
        T.door.hits = 0
    show("MULTIBALL OVER", "", 60)


def ramp_entered(r):
    r.count += 1
    count("ramp")
    combo = T.last_ramp is not None and T.last_ramp is not r
    pts = r.points * (2 if combo else 1)
    add_score(pts)
    T.last_ramp = r
    show(r.name, ("COMBO " if combo else "") + commas(pts * G.mult), 50)
    sound.play(((500, 3), (700, 3), (900, 3), (1200, 5)))
    if len(T.ramps) > 1 and all(rr.count for rr in T.ramps) and not T.kick_lit and T.kick_lamp >= 0:
        T.kick_lit = True
        for rr in T.ramps:
            rr.count = 0


def ramp_tick(b):
    r = b.ramp
    b.dist += RAMP_V
    if b.dist >= r.length:
        x, y = r.pts[-1]
        b.x = float(x)
        b.y = float(y)
        b.vx, b.vy = r.exit_v
        b.mode = M_PLAY
        b.zone = 0
        return
    k = 0
    while r.cum[k + 1] < b.dist:
        k += 1
    f = (b.dist - r.cum[k]) / (r.cum[k + 1] - r.cum[k])
    x0, y0 = r.pts[k]
    x1, y1 = r.pts[k + 1]
    b.vx = (x1 - x0) / (r.cum[k + 1] - r.cum[k]) * RAMP_V    # So the camera can lead
    b.vy = (y1 - y0) / (r.cum[k + 1] - r.cum[k]) * RAMP_V
    b.x = x0 + (x1 - x0) * f
    b.y = y0 + (y1 - y0) * f


def hole_tick(b):
    b.timer -= 1
    if b.timer <= 0:
        b.vx, b.vy = b.hole.kick
        b.mode = M_PLAY
        sound.blip(250, 4)


def ball_gone(b):
    """A ball dropped off the bottom of the table."""
    balls.remove(b)
    count("out_left" if b.x < 12 else ("out_right" if b.x > 102 else "drain_middle"))
    if G.save_t > 0:
        if G.multi or len(balls):
            auto_launch()
        else:
            show("BALL SAVED!", "", 90)
            sound.play(((900, 4), (1200, 6)))
            serve()
        return
    if G.multi and len(balls) <= 1:
        end_multiball()
    if len(balls) == 0:
        G.bstate = B_DRAIN
        G.btimer = 0
        G.balls_left -= 1
        sound.play(((440, 8), (330, 8), (220, 14)))
        if G.balls_left > 0:
            show("BALL LOST", "", 80)


def next_ball():
    G.ball_no += 1
    G.mult = 1
    T.lit = [False] * len(T.lit)
    G.bstate = B_LIVE
    serve()
    show("BALL " + str(G.ball_no), "", 60)


def game_over():
    G.state = ST_OVER
    G.timer = 0
    i = G.table_i
    G.new_hi = G.score > hiscores[i]
    if G.new_hi:
        hiscores[i] = G.score
        save_hi(i)
        sound.play(((660, 6), (880, 6), (1100, 6), (1320, 12)))


def check_balls():
    """Gate, ball save start, draining, and getting a stuck ball moving again."""
    G.gate = True
    for b in balls[:]:
        if b.mode == M_SERVE:
            G.gate = False
            continue
        if b.in_lane:
            if b.x < 108 and b.y < 110:
                b.in_lane = False
                if getattr(b, "served", False) and not G.multi:
                    G.save_t = T.spec["save"]
            else:
                G.gate = False
        if b.mode != M_PLAY:
            continue
        if b.y > TH + 4:
            ball_gone(b)
            continue
        if b.x < 0 or b.x > TW or b.y < 0:
            # Should never happen; put the ball back rather than lose it
            G.escapes += 1
            b.x = LANE_X
            b.y = SERVE_Y
            b.vx = 0.0
            b.vy = -AUTO_V
            b.in_lane = True
            continue
        if b.x > 114 and b.y > SERVE_Y - 2 and abs(b.vy) < 0.5:
            # Rolled back down the plunger lane: fire it again
            if len(balls) == 1 and not G.multi:
                b.mode = M_SERVE
                G.charge = 0.0
            else:
                b.vy = -AUTO_V
            b.in_lane = True
            continue
        # A ball that hardly moves for four seconds gets a shove (unless it's held on a flipper)
        if abs(b.x - b.still_x) > 2 or abs(b.y - b.still_y) > 2:
            b.still_x = b.x
            b.still_y = b.y
            b.still_t = 0
        else:
            b.still_t += 1
            held = (lflip.up or rflip.up) and b.y > 200
            if b.still_t > 240 and not held:
                G.unsticks += 1
                b.vx = random.uniform(-1.5, 1.5)
                b.vy = -2.5
                b.still_t = 0


def update_timers():
    for bp in T.bumpers:
        if bp.cd:
            bp.cd -= 1
        if bp.flash:
            bp.flash -= 1
    for i in range(2):
        if G.sling_cd[i]:
            G.sling_cd[i] -= 1
        if G.sling_flash[i]:
            G.sling_flash[i] -= 1
    if G.save_t > 0 and G.bstate == B_LIVE and not any(b.mode == M_SERVE for b in balls):
        G.save_t -= 1
    for bank in T.banks:
        if bank.reset_t:
            bank.reset_t -= 1
            if bank.reset_t == 0:
                for i in range(len(bank.up)):
                    bank.up[i] = True
        if bank.respawn:
            for i in range(len(bank.up)):
                if not bank.up[i]:
                    bank.down_t[i] -= 1
                    if bank.down_t[i] <= 0:
                        bank.up[i] = True
    for s in T.spinners:
        if s.spin > 0:
            s.spin -= 1
            s.phase += 1 + s.spin // 12
            if s.spin % 5 == 0:
                add_score(100)
                sound.blip(2000, 1)
    if T.door and T.door.cd:
        T.door.cd -= 1
    if G.spawn:
        G.spawn_t -= 1
        if G.spawn_t <= 0:
            G.spawn -= 1
            G.spawn_t = 50
            auto_launch()
    if G.nudge_cd:
        G.nudge_cd -= 1
    if G.shake:
        G.shake -= 1
    if G.msg_t:
        G.msg_t -= 1


def nudge():
    if G.nudge_cd == 0 and G.bstate == B_LIVE:
        for b in balls:
            if b.mode == M_PLAY:
                b.vy -= 1.4
                b.vx += random.uniform(-0.6, 0.6)
        G.nudge_cd = 40
        G.shake = 6
        sound.blip(90, 4)


def focus_ball():
    """The ball the camera watches: the lowest one that's in play."""
    best = None
    for b in balls:
        if b.mode == M_SERVE:
            continue
        if best is None or b.y > best.y:
            best = b
    return best


def update_camera():
    """Show the flippers whenever the ball allows it. The camera only rises when the
    ball is high on the table, looks ahead along the ball's path, and drops fast."""
    b = focus_ball()
    if b is None:
        target = CAM_MAX
        top = bottom = None
    else:
        target = b.y - CAM_TOP + b.vy * CAM_LEAD
        top = b.y - 12
        bottom = b.y - (VIEW_H - 12)
    if target > CAM_MAX:
        target = CAM_MAX
    G.cam += (target - G.cam) * (0.3 if target > G.cam else 0.18)
    # Never let the ball get too close to the edge of the screen
    if b is not None:
        if G.cam > top:
            G.cam = top
        if G.cam < bottom:
            G.cam = bottom
    if G.cam < 0:
        G.cam = 0.0
    if G.cam > CAM_MAX:
        G.cam = float(CAM_MAX)


def update_play():
    update_timers()
    update_flippers()
    if engine_io.UP.is_just_pressed:
        nudge()
    lflip.begin()
    rflip.begin()
    moving = lflip.w != 0 or rflip.w != 0
    if G.bstate == B_LIVE:
        for b in balls[:]:
            m = b.mode
            if m == M_PLAY:
                physics(b, moving)
            elif m == M_SERVE:
                serve_tick(b)
            elif m == M_HOLE:
                hole_tick(b)
            else:
                ramp_tick(b)
    lflip.end()
    rflip.end()
    if G.bstate == B_LIVE:
        if len(balls) > 1:
            collide_balls()
        check_balls()
    else:
        G.btimer += 1
        if G.btimer > 90:
            if G.balls_left > 0:
                next_ball()
            else:
                game_over()
    update_camera()


def flippers_idle():
    lflip.begin()
    rflip.begin()
    lflip.end()
    rflip.end()


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
def draw_flipper(fb, f, oy):
    if f.py + oy < HUD_H - 6:
        return
    for k in range(12):
        t = k / 11
        x = int(f.px + (f.tx - f.px) * t)
        y = int(f.py + (f.ty - f.py) * t) + oy
        r = int(FLIP_R0 - (FLIP_R0 - FLIP_R1) * t + 0.5)
        fb.ellipse(x, y, r, r, C_FLIP_RUB, True)
    for k in range(12):
        t = k / 11
        x = int(f.px + (f.tx - f.px) * t)
        y = int(f.py + (f.ty - f.py) * t) + oy
        r = int(FLIP_R0 - (FLIP_R0 - FLIP_R1) * t - 0.5)
        fb.ellipse(x, y, r, r, C_FLIP, True)
    fb.pixel(int(f.px), int(f.py) + oy, C_GREY)


def draw_plunger(fb, oy):
    top = PLUNGE_Y + oy
    for b in balls:
        if b.mode == M_SERVE:
            top += int(G.charge * PLUNGE_PULL)
    floor = PLUNGE_Y + PLUNGE_PULL + 2 + oy
    if top > SW:
        return
    fb.fill_rect(116, top, 8, 2, C_PLUNGER)
    # Spring
    y = top + 2
    k = 0
    while y < floor:
        fb.hline(117 if k & 1 else 118, y, 5, C_SPRING)
        y += 2
        k += 1


def draw_spinners(fb, oy):
    for s in T.spinners:
        y = s.y + oy
        if y < HUD_H - 3 or y > SW + 3:
            continue
        # The plate looks thinner and fatter as it turns
        h = (0, 1, 2, 1)[(s.phase >> 1) & 3]
        fb.fill_rect(s.x0, y - h, s.x1 - s.x0, 2 * h + 1, C_SPIN if h else C_SPIN_EDGE)
        fb.pixel(s.x0, y, C_SPIN_EDGE)
        fb.pixel(s.x1 - 1, y, C_SPIN_EDGE)


def draw_ball(fb, b, oy):
    x = int(b.x)
    y = int(b.y) + oy
    if y < HUD_H - 4 or y > SW + 4:
        return
    if b.mode == M_RAMP:
        fb.ellipse(x + 2, y + 3, 3, 3, C_SHADOW, True)   # Shadow on the table below the ramp
        y -= 1
    fb.ellipse(x, y, 3, 3, C_BALL_DARK, True)
    fb.ellipse(x - 1, y - 1, 2, 2, C_BALL, True)
    fb.pixel(x - 1, y - 2, C_WHITE)
    fb.pixel(x - 2, y - 1, C_WHITE)


def draw_hud(fb):
    fb.fill_rect(0, 0, SW, HUD_H, C_HUD)
    tiny(commas(G.score), 2, 1, C_WHITE)
    if G.multi:
        if (G.frame >> 3) & 1:
            tiny("MULTI", 64, 1, C_RED)
    elif G.mult > 1:
        tiny(str(G.mult) + "X", 72, 1, C_GOLD)
    for i in range(min(G.balls_left, 5)):
        x = 123 - i * 6
        fb.ellipse(x, 3, 2, 2, C_BALL, True)


def draw_message(fb):
    if G.msg_t <= 0:
        return
    h = 26 if G.msg2 else 16
    # Keep out of the ball's way: top half of the screen if the ball is low, and the other way round
    b = focus_ball()
    low = b is None or b.y - G.cam + HUD_H > 64
    y = 22 if low else 84
    fb.fill_rect(4, y, SW - 8, h, C_PANEL)
    fb.rect(4, y, SW - 8, h, C_GOLD)
    text_center(fb, G.msg, y + 4, C_GOLD)
    if G.msg2:
        tiny_center(G.msg2, y + 16, C_WHITE)


def draw_table(fb):
    cam = int(G.cam)
    if G.shake:
        cam += 2 if G.shake & 2 else -2
        cam = 0 if cam < 0 else (CAM_MAX if cam > CAM_MAX else cam)
    render_table(cam)
    oy = HUD_H - cam
    draw_plunger(fb, oy)
    draw_spinners(fb, oy)
    draw_flipper(fb, lflip, oy)
    draw_flipper(fb, rflip, oy)
    if G.state == ST_PLAY:
        for b in balls:
            draw_ball(fb, b, oy)


def draw_play(fb):
    draw_table(fb)
    draw_hud(fb)
    if (G.frame >> 5) & 1 and G.charge == 0 and any(b.mode == M_SERVE for b in balls):
        y = SERVE_Y - G.cam + HUD_H - 30
        tiny("HOLD", 86, int(y), C_WHITE)
        tiny("DOWN", 86, int(y) + 7, C_WHITE)
    draw_message(fb)


def draw_pause(fb):
    dim_screen()
    fb.fill_rect(14, 38, 100, 50, C_PANEL)
    fb.rect(14, 38, 100, 50, C_GREY)
    text_center(fb, "PAUSED", 45, C_WHITE)
    tiny_center("A: RESUME", 62, C_WHITE)
    tiny_center("B: QUIT TO TITLE", 72, C_GREY)


LEVEL_COLORS = {"EASY": rgb(90, 240, 120), "MEDIUM": rgb(255, 200, 40), "HARD": rgb(255, 80, 80)}


def update_title(fb):
    G.timer += 1
    G.cam = 64 + 63 * math.sin(G.timer / 150)
    lflip.up = rflip.up = False
    flippers_idle()
    n = len(TABLES)
    step = 0
    if engine_io.LEFT.is_just_pressed:
        step = -1
    elif engine_io.RIGHT.is_just_pressed:
        step = 1
    if step:
        G.table_i = (G.table_i + step) % n
        build_table(G.table_i)
        reset_table()
        sound.blip(520, 2)
    draw_table(fb)
    dim_screen()
    dim_screen()
    big_center(fb, "PINBALL", 10, C_GOLD, C_BLACK, 4)
    spec = TABLES[G.table_i]
    text_center(fb, spec["name"], 42, C_WHITE)
    fb.text("<", 2, 42, C_GREY)
    fb.text(">", 119, 42, C_GREY)
    tiny_center(spec["level"], 53, LEVEL_COLORS[spec["level"]])
    tiny_center("TABLE " + str(G.table_i + 1) + " OF " + str(n), 60, C_GREY)
    tiny_center("HIGH SCORE", 70, C_GREY)
    tiny_center(commas(hiscores[G.table_i]), 77, C_WHITE)
    if (G.timer >> 4) & 1:
        text_center(fb, "PRESS A", 88, C_WHITE)
    tiny_center("LB / LEFT  - LEFT FLIPPER", 103, C_GREY)
    tiny_center("RB / A  - RIGHT FLIPPER", 110, C_GREY)
    tiny_center("HOLD DOWN: LAUNCH  UP: NUDGE", 117, C_GREY)
    if engine_io.A.is_just_pressed:
        sound.blip(660, 3)
        save_table_choice()
        start_game()


def update_over(fb):
    G.timer += 1
    flippers_idle()
    draw_table(fb)
    draw_hud(fb)
    dim_screen()
    fb.fill_rect(10, 30, 108, 66, C_PANEL)
    fb.rect(10, 30, 108, 66, C_GOLD)
    text_center(fb, "GAME OVER", 36, C_RED)
    tiny_center("SCORE", 52, C_GREY)
    text_center(fb, commas(G.score), 59, C_WHITE)
    if G.new_hi:
        if (G.timer >> 3) & 1:
            tiny_center("NEW HIGH SCORE!", 72, C_GOLD)
    else:
        tiny_center("HIGH SCORE " + commas(hiscores[G.table_i]), 72, C_GREY)
    if G.timer > 60:
        tiny_center("A: PLAY AGAIN", 80, C_WHITE)
        tiny_center("B: TITLE", 87, C_GREY)
        if engine_io.A.is_just_pressed:
            start_game()
        elif engine_io.B.is_just_pressed:
            to_title()


def to_title():
    G.state = ST_TITLE
    G.timer = 0
    G.multi = False
    G.save_t = 0
    balls[:] = []
    reset_table()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def tick():
    fb = engine_draw.back_fb()
    G.frame += 1
    sound.tick()
    update_lamps()
    st = G.state
    if st == ST_TITLE:
        update_title(fb)
        return
    if st == ST_OVER:
        update_over(fb)
        return
    if G.paused:
        if engine_io.A.is_just_pressed or engine_io.MENU.is_just_pressed:
            G.paused = False
        elif engine_io.B.is_just_pressed:
            G.paused = False
            to_title()
            return
        draw_play(fb)
        draw_pause(fb)
        return
    if engine_io.MENU.is_just_pressed:
        G.paused = True
        draw_play(fb)
        draw_pause(fb)
        return
    update_play()
    draw_play(fb)


load_saves()
build_table(G.table_i)
reset_table()
engine.fps_limit(60)

while True:
    if engine.tick():
        tick()
