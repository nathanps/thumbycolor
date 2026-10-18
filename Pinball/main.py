# Space Pinball - a pinball table for the Thumby Color
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

# ---------------------------------------------------------------------------
# Table layout
# ---------------------------------------------------------------------------
SW = const(128)         # Screen width
TW = const(128)         # Table width
TH = const(248)         # Table height, about two screens. The camera follows the ball
HUD_H = const(7)        # Rows covered by the score bar at the top of the screen
VIEW_H = const(121)     # Table rows that fit under the score bar
CAM_MAX = const(127)    # TH - VIEW_H

BALL_R = 3.0
CONTACT = 3.5           # Ball centre to wall pixel centre distance when touching
GRAVITY = 0.075         # Pixels per frame per frame, down the table
V_MAX = 9.0             # Speed limit, so the ball never moves too far in one sub-step
E_WALL = 0.45           # Bounciness of walls
E_FLIP = 0.25           # Bounciness of flipper rubber (the kick comes from the swing)
BUMP_V = 4.4            # Speed a pop bumper kicks the ball away at
SLING_V = 3.2           # Speed a slingshot adds

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

BALLS = const(3)
MAX_EXTRA = const(2)    # Extra balls a game can earn (every third alien bank)
BALL_SAVE = const(600)  # Frames of ball save after the ball reaches the playfield

# Wall materials (looked up through the kinds table for each palette index)
K_AIR = const(0)
K_WALL = const(1)
K_SLING_L = const(2)
K_SLING_R = const(3)
K_BUMP = const(4)       # 4, 5, 6: the three pop bumpers
K_TARGET = const(8)     # 8 to 11: the four alien drop targets

# Palette indices used in the table picture. 64 and up are solid.
P_BG = const(0)
P_STAR = const(1)       # 1, 2, 3: dim to bright stars
P_PLANET = const(4)     # 4 lit side, 5 dark side, 6 ring, 7 craters
P_ART = const(8)        # Lines and arrows painted on the playfield
P_ART2 = const(9)
P_LANE = const(16)      # 16, 17, 18: rollover lane stars
P_MULT = const(19)      # 19 to 22: 2X 3X 4X 5X lamps
P_SAVE = const(23)      # "SAVE" lamp between the flippers
P_WALL = const(64)
P_WALL_HI = const(65)
P_POST = const(66)
P_SLING_L = const(67)
P_SLING_R = const(68)
P_SLING_BODY = const(69)
P_BUMP = const(70)      # 70, 71, 72: bumper centres
P_RING = const(73)      # 73, 74, 75: bumper rings
P_ALIEN = const(76)     # 76 to 79: alien drop targets
P_EYE = const(80)       # 80 to 83: their eyes
P_GATE = const(84)      # One-way gate at the top of the plunger lane
P_APRON = const(85)

# Game states
ST_TITLE = const(0)
ST_PLAY = const(1)
ST_OVER = const(2)

# Ball states while playing
B_SERVE = const(0)      # Sitting on the plunger
B_LIVE = const(1)
B_DRAIN = const(2)      # Gone down the middle, waiting for the next ball


def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


C_BLACK = const(0)
C_WHITE = const(0xFFFF)
C_GREY = rgb(140, 140, 160)
C_GOLD = rgb(255, 200, 40)
C_HUD = rgb(14, 10, 34)
C_PANEL = rgb(20, 16, 50)
C_BALL = rgb(190, 195, 215)
C_BALL_DARK = rgb(110, 115, 140)
C_FLIP = rgb(240, 240, 250)
C_FLIP_RUB = rgb(240, 60, 90)
C_PLUNGER = rgb(200, 200, 220)
C_SPRING = rgb(150, 150, 170)
C_RED = rgb(255, 80, 80)
C_GREEN = rgb(90, 240, 120)

table = bytearray(TW * TH)          # One palette index per pixel
palette = array.array("H", [0] * 256)
kinds = bytearray(256)              # Material of each palette index
pr = array.array("i", [0] * 4)      # Results from probe()

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
    to the nearest one and the nearest one's material."""
    t = ptr8(table)
    k = ptr8(kinds)
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
# Building the table picture
# ---------------------------------------------------------------------------
def tdisc(x, y, r, c):
    stamp(int(x * 16), int(y * 16), int(r * 16), c)


def tline(x0, y0, x1, y1, r, c):
    """A thick line made of discs every half pixel."""
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
    for i in range(n + 1):
        f = i / n
        tdisc(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, r, c)


def trow(y, x0, x1, c):
    """Fill pixels x0..x1-1 of row y."""
    if x1 > x0:
        o = y * TW
        table[o + x0:o + x1] = bytes((c,)) * (x1 - x0)


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


def mirror(p):
    return (2 * MID_X - p[0], p[1])


# Corner arcs at the top of the table
ARC_R = 37
ARC_L = 40              # Left arc centre x
ARC_RX = 87             # Right arc centre x
ARC_Y = 40

# Slingshots above the flippers (left one; the right one is its mirror). The bottom
# edge runs alongside the inlane guide, 12 pixels up, so the ball can roll between them
SLING = ((17, 163), (17, 181), (29, 203))
GUIDE = ((3, 180), (25, 220))       # Inlane guide down to the left flipper

# Rollover lanes along the top: posts between them, and each lane's middle
POSTS = (30, 48, 66, 84)
LANES = (39, 57, 75)
LANE_Y0 = 14
LANE_Y1 = 24

BUMPERS = ((39, 56), (75, 56), (57, 79))
BUMP_RING = 7

ALIEN_X = (34, 47, 60, 73)
ALIEN_Y = 118
ALIEN = ("..####..",
         ".######.",
         "##o##o##",
         "########",
         ".#.##.#.",
         "#......#")
MULT_X = (33, 47, 61, 75)
MULT_Y = 98


def build_table():
    for i in range(len(table)):
        table[i] = P_BG
    # Stars, from a fixed seed so the sky is always the same
    s = 12345
    for i in range(170):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        x = (s >> 8) % TW
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        y = (s >> 8) % TH
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        table[y * TW + x] = P_STAR + (s >> 8) % 3

    # A ringed planet painted in the middle of the playfield
    px, py, prad = MID_X, 160, 12
    for y in range(py - prad, py + prad + 1):
        for x in range(px - prad, px + prad + 1):
            dx = x + 0.5 - px
            dy = y + 0.5 - py
            if dx * dx + dy * dy <= prad * prad:
                lit = (dx + 4) * (dx + 4) + (dy + 4) * (dy + 4) < (prad + 3) * (prad + 3)
                table[y * TW + x] = P_PLANET if lit else P_PLANET + 1
    for cx, cy in ((53, 155), (61, 163), (51, 165)):
        table[cy * TW + cx] = P_PLANET + 3
        table[cy * TW + cx + 1] = P_PLANET + 3
    for i in range(160):
        a = i * 2 * math.pi / 160
        x = px + 21 * math.cos(a)
        y = py + 5 * math.sin(a) - 3 * math.cos(a)
        behind = math.sin(a) < 0 and abs(x - px) < prad
        if not behind:
            table[int(y) * TW + int(x)] = P_PLANET + 2

    # Arrows on the playfield pointing up at the aliens and the lanes
    for ax in (20, 94):
        for k in range(3):
            y = 140 + k * 6
            tline(ax - 3, y + 3, ax, y, 0.5, P_ART)
            tline(ax, y, ax + 3, y + 3, 0.5, P_ART)
    ttext("SAVE", MID_X - 7, 239, P_SAVE)
    for i in range(4):
        ttext(str(i + 2) + "X", MULT_X[i], MULT_Y, P_MULT + i)

    # Rollover lane stars
    for i in range(3):
        x = LANES[i]
        y = 30
        for dx, dy in ((0, -2), (0, -1), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0),
                       (-1, 1), (1, 1), (-1, 2), (1, 2)):
            table[(y + dy) * TW + x + dx] = P_LANE + i

    # Outer walls with rounded top corners. Everything outside is solid
    for y in range(TH):
        if y < 3:
            trow(y, 0, TW, P_WALL)
            continue
        if y < ARC_Y:
            dy = ARC_Y - y - 0.5
            w = math.sqrt(ARC_R * ARC_R - dy * dy) if dy < ARC_R else 0
            xl = int(ARC_L - w + 0.5)
            xr = int(ARC_RX + w + 0.5)
        else:
            xl = 3
            xr = 125
        trow(y, 0, xl, P_WALL)
        trow(y, xr, TW, P_WALL)
        table[y * TW + xl - 1] = P_WALL_HI
        table[y * TW + xr] = P_WALL_HI

    # Plunger lane: separator wall, gate, floor
    for y in range(72, TH):
        trow(y, 112, 115, P_WALL)
    tdisc(113.5, 72, 1.5, P_WALL_HI)
    tline(113.5, 70, 125, 60, 1.0, P_GATE)
    for y in range(PLUNGE_Y + PLUNGE_PULL + 2, TH):
        trow(y, 115, 125, P_WALL)

    # Inlane guides and the aprons outside them
    for side in (0, 1):
        g0, g1 = GUIDE
        if side:
            g0, g1 = mirror(g0), mirror(g1)
        for y in range(g0[1], TH):
            if y <= g1[1]:
                gx = g0[0] + (g1[0] - g0[0]) * (y - g0[1]) / (g1[1] - g0[1])
            else:
                gx = g1[0]
            if side:
                trow(y, int(gx), 112, P_APRON)
            else:
                trow(y, 3, int(gx) + 1, P_APRON)
        tline(g0[0], g0[1], g1[0], g1[1], 1.5, P_WALL_HI)
        fx = RFLIP_X if side else LFLIP_X
        tdisc(fx, FLIP_Y, 2, P_WALL)            # Hidden under the flipper's pivot

    # Slingshots
    for side in (0, 1):
        a, b, c = SLING
        if side:
            a, b, c = mirror(a), mirror(b), mirror(c)
        ttri(a, b, c, P_SLING_BODY)
        tline(a[0], a[1], b[0], b[1], 1.0, P_WALL_HI)
        tline(b[0], b[1], c[0], c[1], 1.0, P_WALL_HI)
        tline(a[0], a[1], c[0], c[1], 1.2, P_SLING_R if side else P_SLING_L)

    # Rollover lane posts
    for x in POSTS:
        tline(x, LANE_Y0 - 1, x, LANE_Y1 + 1, 1.2, P_POST)

    # Pop bumpers
    for i in range(3):
        bx, by = BUMPERS[i]
        tdisc(bx, by, BUMP_RING, P_RING + i)
        tdisc(bx, by, BUMP_RING - 2.2, P_BUMP + i)

    # Alien drop targets
    for i in range(4):
        for ry in range(len(ALIEN)):
            row = ALIEN[ry]
            for rx in range(8):
                ch = row[rx]
                if ch != ".":
                    table[(ALIEN_Y + ry) * TW + ALIEN_X[i] + rx] = P_EYE + i if ch == "o" else P_ALIEN + i


def setup_palette():
    pal = (
        (P_BG, (6, 4, 22)), (P_STAR, (70, 70, 110)), (P_STAR + 1, (140, 140, 190)),
        (P_STAR + 2, (255, 255, 255)),
        (P_PLANET, (90, 200, 230)), (P_PLANET + 1, (40, 90, 140)), (P_PLANET + 2, (230, 190, 120)),
        (P_PLANET + 3, (60, 140, 180)),
        (P_ART, (70, 50, 140)), (P_ART2, (110, 80, 200)),
        (P_WALL, (60, 50, 120)), (P_WALL_HI, (150, 140, 230)), (P_POST, (210, 210, 240)),
        (P_SLING_BODY, (45, 40, 100)), (P_APRON, (30, 24, 70)), (P_GATE, (150, 140, 230)),
    )
    for i, c in pal:
        palette[i] = rgb(c[0], c[1], c[2])
    for i in range(64, 256):
        kinds[i] = K_WALL
    kinds[P_SLING_L] = K_SLING_L
    kinds[P_SLING_R] = K_SLING_R
    for i in range(3):
        kinds[P_BUMP + i] = K_BUMP + i
        kinds[P_RING + i] = K_BUMP + i
    for i in range(4):
        kinds[P_ALIEN + i] = K_TARGET + i
        kinds[P_EYE + i] = K_TARGET + i


BUMP_COLORS = ((230, 60, 60), (60, 130, 255), (255, 150, 30))


def lamp(i, on, lit, unlit):
    c = lit if on else unlit
    palette[i] = rgb(c[0], c[1], c[2])


def update_lamps():
    """Set the palette entries for everything that lights up."""
    f = G.frame
    for i in range(3):
        c = BUMP_COLORS[i]
        if G.bump_flash[i]:
            palette[P_BUMP + i] = C_WHITE
            palette[P_RING + i] = rgb(255, 255, 160)
        else:
            palette[P_BUMP + i] = rgb(c[0], c[1], c[2])
            palette[P_RING + i] = rgb(min(255, c[0] + 90), min(255, c[1] + 90), min(255, c[2] + 90))
    lamp(P_SLING_L, G.sling_flash[0], (255, 255, 255), (255, 70, 150))
    lamp(P_SLING_R, G.sling_flash[1], (255, 255, 255), (255, 70, 150))
    for i in range(3):
        lamp(P_LANE + i, G.lanes[i], (255, 230, 60), (70, 60, 30))
    for i in range(4):
        lamp(P_MULT + i, G.mult >= i + 2, (255, 170, 40), (60, 40, 30))
    for i in range(4):
        up = G.aliens[i]
        lamp(P_ALIEN + i, up, (90, 235, 90), (30, 50, 40))
        lamp(P_EYE + i, up, (10, 20, 10), (30, 50, 40))
        kinds[P_ALIEN + i] = K_TARGET + i if up else K_AIR
        kinds[P_EYE + i] = K_TARGET + i if up else K_AIR
    save = G.save_t > 0 and (G.save_t > 120 or (f >> 3) & 1)
    lamp(P_SAVE, save, (80, 255, 120), (25, 50, 35))
    kinds[P_GATE] = K_WALL if G.gate else K_AIR
    lamp(P_GATE, G.gate, (150, 140, 230), (35, 30, 70))
    lamp(P_ART2, (f >> 4) & 1, (130, 100, 230), (70, 50, 140))


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


# ---------------------------------------------------------------------------
# Ball and flippers
# ---------------------------------------------------------------------------
class Ball:
    def __init__(self):
        self.x = LANE_X
        self.y = SERVE_Y
        self.vx = 0.0
        self.vy = 0.0


class Flipper:
    def __init__(self, x, side):
        self.px = x
        self.py = FLIP_Y
        self.side = side            # 1 for the left flipper, -1 for the right
        self.ang = FLIP_REST
        self.w = 0.0                # Angle change per frame
        self.step = 0.0
        self.tvx = 0.0              # Tip velocity per frame
        self.tvy = 0.0
        self.up = False
        self.place()

    def place(self):
        self.tx = self.px + self.side * FLIP_LEN * math.cos(self.ang)
        self.ty = self.py + FLIP_LEN * math.sin(self.ang)

    def moving(self):
        return self.ang != (FLIP_UP if self.up else FLIP_REST)

    def begin(self, n):
        """Work out this frame's swing, spread over n sub-steps."""
        target = FLIP_UP if self.up else FLIP_REST
        d = target - self.ang
        lim = FLIP_W_UP if self.up else FLIP_W_DOWN
        if d > lim:
            d = lim
        elif d < -lim:
            d = -lim
        self.w = d
        self.step = d / n
        self.n = n
        if d == 0:
            self.tvx = 0.0
            self.tvy = 0.0

    def substep(self):
        if self.step:
            ox = self.tx
            oy = self.ty
            self.ang += self.step
            self.place()
            self.tvx = (self.tx - ox) * self.n
            self.tvy = (self.ty - oy) * self.n

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
    """Push the ball out of any table wall it overlaps and bounce it. Returns the material."""
    n = probe(int(b.x * 16), int(b.y * 16))
    if n == 0:
        return K_AIR
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
    if K_BUMP <= kind < K_BUMP + 3:
        i = kind - K_BUMP
        if G.bump_cd[i] == 0:
            # Pop bumpers fire the ball straight away from their middle
            tx = b.vx - vn * nx
            ty = b.vy - vn * ny
            b.vx = nx * BUMP_V + tx * 0.4
            b.vy = ny * BUMP_V + ty * 0.4
            G.bump_cd[i] = 6
            G.events.append(kind)
            return kind
    if vn < 0:
        b.vx -= (1 + E_WALL) * vn * nx
        b.vy -= (1 + E_WALL) * vn * ny
        if kind == K_SLING_L or kind == K_SLING_R:
            i = kind - K_SLING_L
            if vn < -0.4 and G.sling_cd[i] == 0:
                b.vx += nx * SLING_V
                b.vy += ny * SLING_V
                G.sling_cd[i] = 8
                G.events.append(kind)
        elif kind >= K_TARGET:
            if G.aliens[kind - K_TARGET]:
                G.events.append(kind)
    return kind


def physics():
    b = ball
    sp = abs(b.vx) + abs(b.vy)
    n = 2 + int(sp * 1.3)
    if b.y > 190 and (lflip.moving() or rflip.moving()) and n < 8:
        n = 8           # Small steps while a flipper swings, so it can't jump past the ball
    inv = 1.0 / n
    lflip.begin(n)
    rflip.begin(n)
    g = GRAVITY * inv
    near = b.y > 190
    for _ in range(n):
        lflip.substep()
        rflip.substep()
        b.vy += g
        b.x += b.vx * inv
        b.y += b.vy * inv
        hit_walls(b)
        if near or b.y > 190:
            lflip.collide(b)
            rflip.collide(b)
    b.vx *= 0.999
    b.vy *= 0.999
    s2 = b.vx * b.vx + b.vy * b.vy
    if s2 > V_MAX * V_MAX:
        k = V_MAX / math.sqrt(s2)
        b.vx *= k
        b.vy *= k


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.state = ST_TITLE
        self.frame = 0
        self.timer = 0
        self.paused = False
        self.reset()

    def reset(self):
        self.score = 0
        self.ball_no = 1
        self.balls_left = BALLS     # Including the one in play
        self.extra_balls = 0
        self.bstate = B_SERVE
        self.btimer = 0
        self.charge = 0.0
        self.gate = False
        self.save_t = 0
        self.mult = 1
        self.lanes = [False, False, False]
        self.in_lane = -1
        self.aliens = [True, True, True, True]
        self.alien_reset = 0        # Frames until a cleared alien bank comes back
        self.bank_clears = 0
        self.bump_cd = [0, 0, 0]
        self.bump_flash = [0, 0, 0]
        self.sling_cd = [0, 0]
        self.sling_flash = [0, 0]
        self.events = []
        self.cam = float(CAM_MAX)
        self.shake = 0
        self.nudge_cd = 0
        self.msg = ""
        self.msg2 = ""
        self.msg_t = 0
        self.still_t = 0            # Frames the ball has hardly moved
        self.still_x = 0.0
        self.still_y = 0.0
        self.unsticks = 0
        self.escapes = 0
        self.new_hi = False


G = Game()
ball = Ball()
lflip = Flipper(LFLIP_X, 1)
rflip = Flipper(RFLIP_X, -1)

engine_save._init_saves_dir("Saves/Games/Pinball")
engine_save.set_location("save")

hiscore = 0


def load_hi():
    global hiscore
    try:
        hiscore = int(engine_save.load("hi", 0))
    except Exception:
        hiscore = 0


def save_hi():
    try:
        engine_save.save("hi", hiscore)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Game rules
# ---------------------------------------------------------------------------
def show(msg, msg2="", frames=90):
    G.msg = msg
    G.msg2 = msg2
    G.msg_t = frames


def add_score(points):
    G.score += points * G.mult


def serve():
    """Put a ball on the plunger."""
    G.bstate = B_SERVE
    G.charge = 0.0
    G.gate = False
    G.save_t = 0
    ball.x = LANE_X
    ball.y = SERVE_Y
    ball.vx = 0.0
    ball.vy = 0.0
    G.still_t = 0


def start_game():
    G.reset()
    G.state = ST_PLAY
    G.paused = False
    serve()
    show("BALL 1", "", 60)


def flipper_buttons():
    return (engine_io.LB.is_pressed or engine_io.LEFT.is_pressed,
            engine_io.RB.is_pressed or engine_io.A.is_pressed)


def update_flippers():
    lp, rp = flipper_buttons()
    if lp and not lflip.up:
        sound.blip(170, 2, 1, 0.15)
    if rp and not rflip.up:
        sound.blip(190, 2, 1, 0.15)
    if lp and not lflip.up and G.bstate == B_LIVE:
        # Lane change: the lit lanes slide left
        G.lanes = G.lanes[1:] + G.lanes[:1]
    if rp and not rflip.up and G.bstate == B_LIVE:
        G.lanes = G.lanes[-1:] + G.lanes[:-1]
    lflip.up = lp
    rflip.up = rp


def update_serve():
    if engine_io.DOWN.is_pressed:
        if G.charge < 1:
            G.charge = min(1.0, G.charge + 1 / 40)
            if G.frame % 4 == 0:
                sound.blip(200 + int(G.charge * 300), 2)
    elif G.charge > 0:
        ball.vy = -(LAUNCH_MIN + (LAUNCH_MAX - LAUNCH_MIN) * G.charge)
        ball.vx = 0.0
        ball.y = SERVE_Y
        G.charge = 0.0
        G.bstate = B_LIVE
        sound.play(((300, 2), (450, 2), (650, 3)))
        return
    ball.x = LANE_X
    ball.y = SERVE_Y + G.charge * PLUNGE_PULL


def ball_lost():
    if G.save_t > 0:
        show("BALL SAVED!", "", 90)
        sound.play(((900, 4), (1200, 6)))
        serve()
        return
    G.bstate = B_DRAIN
    G.btimer = 0
    G.balls_left -= 1
    sound.play(((440, 8), (330, 8), (220, 14)))
    if G.balls_left > 0:
        show("BALL LOST", "", 80)


def next_ball():
    G.ball_no += 1
    G.mult = 1
    G.lanes = [False, False, False]
    serve()
    show("BALL " + str(G.ball_no), "", 60)


def game_over():
    global hiscore
    G.state = ST_OVER
    G.timer = 0
    G.new_hi = G.score > hiscore
    if G.new_hi:
        hiscore = G.score
        save_hi()
        sound.play(((660, 6), (880, 6), (1100, 6), (1320, 12)))


def handle_events():
    for k in G.events:
        if K_BUMP <= k < K_BUMP + 3:
            i = k - K_BUMP
            G.bump_flash[i] = 6
            add_score(100)
            sound.blip((880, 1040, 1240)[i], 3)
        elif k == K_SLING_L or k == K_SLING_R:
            G.sling_flash[k - K_SLING_L] = 5
            add_score(10)
            sound.blip(600, 2)
        elif k >= K_TARGET:
            i = k - K_TARGET
            if G.aliens[i]:
                G.aliens[i] = False
                add_score(750)
                sound.blip(1400, 4)
                if not any(G.aliens):
                    alien_bank_cleared()
    G.events = []


def alien_bank_cleared():
    G.bank_clears += 1
    add_score(5000)
    G.alien_reset = 60
    if G.bank_clears % 3 == 0 and G.extra_balls < MAX_EXTRA:
        G.balls_left += 1
        G.extra_balls += 1
        show("EXTRA BALL!", "", 120)
        sound.play(((880, 5), (1100, 5), (1320, 5), (1760, 14)))
    else:
        show("ALIENS DOWN!", commas(5000 * G.mult), 90)
        sound.play(((700, 4), (900, 4), (1200, 8)))


def check_lanes():
    b = ball
    lane = -1
    if LANE_Y0 <= b.y <= LANE_Y1:
        for i in range(3):
            if POSTS[i] + 2 < b.x < POSTS[i + 1] - 2:
                lane = i
    if lane >= 0 and lane != G.in_lane:
        if G.lanes[lane]:
            add_score(100)
        else:
            G.lanes[lane] = True
            add_score(500)
        sound.blip(1500, 3)
        if all(G.lanes):
            G.lanes = [False, False, False]
            add_score(2000)
            if G.mult < 5:
                G.mult += 1
                show(str(G.mult) + "X MULTIPLIER", "", 90)
            else:
                show("LANES DONE!", commas(2000 * G.mult), 70)
            sound.play(((800, 4), (1000, 4), (1200, 4), (1600, 8)))
    G.in_lane = lane


def check_ball():
    """Ball-save timer, the gate, draining, and getting a stuck ball moving again."""
    b = ball
    if G.gate is False and b.x < 108 and b.y < 110:
        G.gate = True
        G.save_t = BALL_SAVE
    if b.y > TH + 4:
        ball_lost()
        return
    if b.x < 0 or b.x > TW or b.y < 0:
        # Should never happen; put the ball back rather than lose it
        G.escapes += 1
        serve()
        return
    if b.x > 114 and b.y > SERVE_Y - 2 and abs(b.vy) < 0.5:
        # Rolled back down the plunger lane: launch it again
        serve()
        G.gate = False
        return
    # A ball that hardly moves for four seconds gets a shove (unless it's held on a flipper)
    if abs(b.x - G.still_x) > 2 or abs(b.y - G.still_y) > 2:
        G.still_x = b.x
        G.still_y = b.y
        G.still_t = 0
    else:
        G.still_t += 1
        held = (lflip.up or rflip.up) and b.y > 200
        if G.still_t > 240 and not held:
            G.unsticks += 1
            b.vx = random.uniform(-1.5, 1.5)
            b.vy = -2.5
            G.still_t = 0


def update_timers():
    for i in range(3):
        if G.bump_cd[i]:
            G.bump_cd[i] -= 1
        if G.bump_flash[i]:
            G.bump_flash[i] -= 1
    for i in range(2):
        if G.sling_cd[i]:
            G.sling_cd[i] -= 1
        if G.sling_flash[i]:
            G.sling_flash[i] -= 1
    if G.save_t > 0 and G.bstate == B_LIVE:
        G.save_t -= 1
    if G.alien_reset:
        G.alien_reset -= 1
        if G.alien_reset == 0:
            G.aliens = [True, True, True, True]
    if G.nudge_cd:
        G.nudge_cd -= 1
    if G.shake:
        G.shake -= 1
    if G.msg_t:
        G.msg_t -= 1


def nudge():
    if G.nudge_cd == 0 and G.bstate == B_LIVE:
        ball.vy -= 1.4
        ball.vx += random.uniform(-0.6, 0.6)
        G.nudge_cd = 40
        G.shake = 6
        sound.blip(90, 4)


def update_camera():
    target = ball.y - 58
    if G.bstate == B_SERVE:
        target = CAM_MAX
    G.cam += (target - G.cam) * 0.2
    # Never let the ball get too close to the edge of the screen
    if ball.y - G.cam < 14:
        G.cam = ball.y - 14
    if ball.y - G.cam > VIEW_H - 14:
        G.cam = ball.y - (VIEW_H - 14)
    if G.cam < 0:
        G.cam = 0.0
    if G.cam > CAM_MAX:
        G.cam = float(CAM_MAX)


def update_play():
    update_timers()
    update_flippers()
    if engine_io.UP.is_just_pressed:
        nudge()
    if G.bstate == B_SERVE:
        update_serve()
        physics_flippers_only()
    elif G.bstate == B_LIVE:
        physics()
        handle_events()
        check_lanes()
        check_ball()
    else:
        physics_flippers_only()
        G.btimer += 1
        if G.btimer > 90:
            if G.balls_left > 0:
                next_ball()
            else:
                game_over()
    update_camera()


def physics_flippers_only():
    lflip.begin(1)
    rflip.begin(1)
    lflip.substep()
    rflip.substep()


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
    if G.bstate == B_SERVE:
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


def draw_ball(fb, oy):
    x = int(ball.x)
    y = int(ball.y) + oy
    if y < HUD_H - 4 or y > SW + 4:
        return
    fb.ellipse(x, y, 3, 3, C_BALL_DARK, True)
    fb.ellipse(x - 1, y - 1, 2, 2, C_BALL, True)
    fb.pixel(x - 1, y - 2, C_WHITE)
    fb.pixel(x - 2, y - 1, C_WHITE)


def draw_hud(fb):
    fb.fill_rect(0, 0, SW, HUD_H, C_HUD)
    tiny(commas(G.score), 2, 1, C_WHITE)
    if G.mult > 1:
        tiny(str(G.mult) + "X", 80, 1, C_GOLD)
    # Balls left (counting the one in play)
    for i in range(min(G.balls_left, 5)):
        x = 123 - i * 6
        fb.ellipse(x, 3, 2, 2, C_BALL, True)


def draw_message(fb):
    if G.msg_t <= 0:
        return
    h = 26 if G.msg2 else 16
    y = 52
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
    draw_flipper(fb, lflip, oy)
    draw_flipper(fb, rflip, oy)
    if G.state != ST_PLAY or G.bstate != B_DRAIN:
        draw_ball(fb, oy)


def draw_play(fb):
    draw_table(fb)
    draw_hud(fb)
    if G.bstate == B_SERVE and G.charge == 0 and (G.frame >> 5) & 1:
        tiny("HOLD", 86, 98, C_WHITE)
        tiny("DOWN", 86, 105, C_WHITE)
    draw_message(fb)


def draw_pause(fb):
    dim_screen()
    fb.fill_rect(14, 38, 100, 50, C_PANEL)
    fb.rect(14, 38, 100, 50, C_GREY)
    text_center(fb, "PAUSED", 45, C_WHITE)
    tiny_center("A: RESUME", 62, C_WHITE)
    tiny_center("B: QUIT TO TITLE", 72, C_GREY)


def update_title(fb):
    G.timer += 1
    G.cam = 64 + 63 * math.sin(G.timer / 150)
    lflip.up = rflip.up = False
    physics_flippers_only()
    draw_table(fb)
    dim_screen()
    big_center(fb, "SPACE", 14, rgb(120, 200, 255), C_BLACK, 4)
    big_center(fb, "PINBALL", 40, C_GOLD, C_BLACK, 3)
    tiny_center("HIGH SCORE", 64, C_GREY)
    tiny_center(commas(hiscore), 71, C_WHITE)
    if (G.timer >> 4) & 1:
        text_center(fb, "PRESS A", 84, C_WHITE)
    tiny_center("LB / LEFT  - LEFT FLIPPER", 101, C_GREY)
    tiny_center("RB / A  - RIGHT FLIPPER", 108, C_GREY)
    tiny_center("HOLD DOWN: LAUNCH  UP: NUDGE", 115, C_GREY)
    if engine_io.A.is_just_pressed:
        sound.blip(660, 3)
        start_game()


def update_over(fb):
    G.timer += 1
    physics_flippers_only()
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
        tiny_center("HIGH SCORE " + commas(hiscore), 72, C_GREY)
    if G.timer > 60:
        tiny_center("A: PLAY AGAIN", 80, C_WHITE)
        tiny_center("B: TITLE", 87, C_GREY)
        if engine_io.A.is_just_pressed:
            start_game()
        elif engine_io.B.is_just_pressed:
            G.state = ST_TITLE
            G.timer = 0


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
            G.state = ST_TITLE
            G.timer = 0
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


load_hi()
setup_palette()
build_table()
engine.fps_limit(60)

while True:
    if engine.tick():
        tick()
