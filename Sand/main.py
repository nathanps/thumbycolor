import engine_main

import engine
import engine_io
import engine_draw
from engine_nodes import Sprite2DNode, CameraNode
from engine_resources import TextureResource

import framebuf
import random
import gc
import math
import engine_save
import json

W = const(130)
H = const(130)

# Particle Format (8-bit)
#   IIISDDCC
#   C: Color (variants)
#   D: Density
#   S: Static
#   I: ID

P_C = const(0b00000011)     # Color bit mask
P_D = const(0b00001100)     # Density bit mask
P_ID = const(0b11100000)     # ID bit mask

# Density values
P_D_GAS = const(0 << 2)
P_D_LIQUID = const(1 << 2)
P_D_SOLID = const(2 << 2)

# STATIC bit flag
P_S_STATIC = const(1 << 4)

# Particle definitions
#   - Each type of particle consists of an ID, static flag, density value, and color value
#   - By using bitwise OR, they can be composed by combining each category value
P_AIR = const((0 << 5) | P_S_STATIC | P_D_GAS)
P_SAND = const((1 << 5) | P_D_SOLID)
P_WATER = const((2 << 5) | P_D_LIQUID)
P_WALL = const((3 << 5) | P_S_STATIC | P_D_SOLID)
P_ANT = const((4 << 5) | P_S_STATIC | P_D_SOLID)   # Creature marker (static so physics ignores)
P_FISH = const((5 << 5) | P_S_STATIC | P_D_LIQUID) # Creature marker (static so physics ignores)

# Creature type constants
CREATURE_ANT = const(0)
CREATURE_FISH = const(1)
MAX_CREATURES = const(20)

# Cycle order for picking an element (B button)
Picks = [P_SAND, P_WATER, P_WALL, P_ANT, P_FISH]

# State Format (8-bit)
#   000000BM
#   M: MOVED
#   B: BIAS

S_M = const(0b00000001)  # MOVED bit mask
S_B = const(0b00000010)  # BIAS bit mask

# Set/Reset MOVED bit flag
S_M_MOVED = const(1)
S_M_INV_MOVED = const(255 - S_M_MOVED)

# Set/Reset BIAS bit flag
S_B_BIAS = const(1 << 1)
S_B_INV_BIAS = const(255 - S_B_BIAS)

# Buffers that contain each pixel on the screen, plus some extra along the edges
particles = bytearray(W*H)  # Particle type (air, sand, water, wall)
state = bytearray(W*H)      # Particle state (moved, bias)

# Setup empty screen full of air, with the extra along the edges as walls
for px in range(W):
    particles[px] = P_WALL
    particles[W*(H-1)+px] = P_WALL
for py in range(H):
    particles[py*W] = P_WALL
    particles[py*W+(W-1)] = P_WALL
for py in range(1, H-1):
    for px in range(1, W-1):
        particles[py*W+px] = P_AIR


# Creature class for ants and fish
class Creature:
    def __init__(self, x, y, ctype):
        self.x = x
        self.y = y
        self.ctype = ctype
        self.dir = random.choice([-1, 1])
        self.alive = True
        self.timer = 0
        self.vy = 0.0

creatures = []

# Pause menu state
pause_menu_active = False
pause_menu_selection = 0
PAUSE_OPTIONS = ["Resume", "Save & Quit", "Clear", "Quit"]
SAVE_FILE = "sand_save.data"


def save_game():
    """Save game state to persistent storage."""
    engine_save.set_location(SAVE_FILE)
    # Save particles as hex string
    engine_save.save("particles", particles.hex())
    # Save creatures as list of dicts
    creature_data = []
    for c in creatures:
        creature_data.append({
            "x": c.x, "y": c.y, "ctype": c.ctype,
            "dir": c.dir, "timer": c.timer, "vy": c.vy
        })
    engine_save.save("creatures", json.dumps(creature_data))


def load_game():
    """Load saved game state. Returns True if loaded, False if no save."""
    global creatures
    try:
        engine_save.set_location(SAVE_FILE)
        saved_particles = engine_save.load("particles", None)
        if saved_particles is None:
            return False

        # Restore particles
        saved_bytes = bytearray.fromhex(saved_particles)
        for i in range(min(len(saved_bytes), len(particles))):
            particles[i] = saved_bytes[i]

        # Restore creatures
        saved_creatures = engine_save.load("creatures", "[]")
        if saved_creatures:
            creature_data = json.loads(saved_creatures)
            creatures = []
            for cd in creature_data:
                c = Creature(cd["x"], cd["y"], cd["ctype"])
                c.dir = cd.get("dir", 1)
                c.timer = cd.get("timer", 0)
                c.vy = cd.get("vy", 0.0)
                creatures.append(c)

        # Delete save after loading
        engine_save.save("particles", None)
        engine_save.save("creatures", None)
        return True
    except:
        # If loading fails, start fresh
        return False


def draw_pause_menu():
    """Draw pause menu overlay."""
    fb = engine_draw.back_fb()
    # Dark background box
    fb.rect(20, 30, 88, 68, 0x0000, True)
    fb.rect(20, 30, 88, 68, 0xFFFF, False)
    # Title
    fb.text("PAUSED", 44, 36, 0xFFFF)
    # Options
    for i, option in enumerate(PAUSE_OPTIONS):
        y = 50 + i * 12
        if i == pause_menu_selection:
            fb.text("> " + option, 26, y, 0xFFFF)
        else:
            fb.text("  " + option, 26, y, 0x8410)


@micropython.viper
def physics():
    # Viper pointers for quick access to the buffers
    pa = ptr8(particles)
    sa = ptr8(state)

    for py in range(1, H-1):
        for i in range(W):
            # Every other row, reverse processing order to reduce left-right bias
            # (this trick may not be needed anymore, since I added a bias state?)
            if py & 0b1:
                px = 1 + i
            else:
                px = (W-2) - i

            mi = W * py + px   # middle index (particle/state being processed)

            mmp, mms = pa[mi], sa[mi]   # middle particle, middle state
            mmpd = mmp & P_D            # middle particle density
            mmsb = mms & S_B            # middle state bias flag

            # Skip processing this particle if flagged static (wall) or already moved this frame
            if mmp & P_S_STATIC or mms & S_M_MOVED:
                continue

            # Use bias flag to determine priority (1, 2) when deciding middle sideways movement
            if mmpd == P_D_LIQUID:
                if mmsb:
                    msi1, msi2 = mi-1, mi+1     # middle side index 1 & 2
                else:
                    msi1, msi2 = mi+1, mi-1     # middle side index 1 & 2
                msp1, mss1 = pa[msi1], sa[msi1]  # m side 1 particle & state
                msp2, mss2 = pa[msi2], sa[msi2]  # m side 2 particle & state

            di = mi + H                # down index (pixel below)
            dmp, dms = pa[di], sa[di]   # down particle, down state

            # Use bias flag to determine priority (1, 2) when deciding down sideways movement
            if mmsb:
                dsi1, dsi2 = di-1, di+1     # down side index 1 & 2
            else:
                dsi1, dsi2 = di+1, di-1     # down side index 1 & 2
            dsp2, dss2 = pa[dsi2], sa[dsi2]  # d side 1 particle & state
            dsp1, dss1 = pa[dsi1], sa[dsi1]  # d side 2 particle & state

            # If down particle hasn't moved yet and has lighter density
            if not dms & S_M_MOVED and dmp & P_D < mmpd:
                si, sb = di, mmsb ^ S_B_BIAS    # Swap index & bias (flip)
            # If down side 1 particle hasn't moved yet and has lighter density
            elif not dss1 & S_M_MOVED and dsp1 & P_D < mmpd:
                si, sb = dsi1, mmsb             # Swap index & bias
            # If down side 2 particle hasn't moved yet and has lighter density
            elif not dss2 & S_M_MOVED and dsp2 & P_D < mmpd:
                si, sb = dsi2, mmsb ^ S_B_BIAS  # Swap index & bias (flip)
            # If I am liquid and middle side 1 particle hasn't moved yet and has lighter density
            elif mmpd == P_D_LIQUID and not mss1 & S_M_MOVED and msp1 & P_D < mmpd:
                si, sb = msi1, mmsb             # Swap index & bias
            # If I am liquid and middle side 2 particle hasn't moved yet and has lighter density
            elif mmpd == P_D_LIQUID and not mss2 & S_M_MOVED and msp2 & P_D < mmpd:
                si, sb = msi2, mmsb ^ S_B_BIAS  # Swap index & bias (flip)
            # If no swaps are found, skip to next particle
            else:
                continue

            # Swap particles
            pa[mi], pa[si] = pa[si], pa[mi]

            # Flag both have moved
            sa[mi] |= S_M_MOVED
            sa[si] |= S_M_MOVED

            # Set/Reset bias flag
            if sb:
                sa[si] |= S_B_BIAS
            else:
                sa[si] &= S_B_INV_BIAS

    # Reset moved flag for all to be ready for next frame
    for i in range(W*H):
        sa[i] &= S_M_INV_MOVED


palettes_raw = [
    0x2965, 0x2965, 0x2965, 0x2965,  # AIR (ID 0)
    0xe736, 0xd6d5, 0xdef6, 0xf7b8,  # SAND (ID 1)
    0x63d7, 0x63d7, 0x63d7, 0x63d7,  # WATER (ID 2)
    0xa513, 0xa4f2, 0x94b1, 0x9490,  # WALL (ID 3)
    0x4208, 0x5ACB, 0x4A49, 0x630C,  # ANT (ID 4) - brown/dark
    0xFD20, 0xFBE0, 0xFC60, 0xFD00,  # FISH (ID 5) - orange/gold
    0, 0, 0, 0,  # ID 6 (reserved)
    0, 0, 0, 0,  # ID 7 (reserved)
]
palettes = bytearray([((v >> (8*i)) & 0xFF)
                     for v in palettes_raw for i in range(2)])


@micropython.native
def randomColor(pick):
    c = random.randrange(0, 4)
    return (pick & 0b11111100) | c


@micropython.viper
def render():

    # Viper pointers for quick access to the buffers
    buf = ptr16(engine_draw.back_fb_data())
    pa = ptr8(particles)
    pal = ptr16(palettes)

    o = 0   # screen index
    for py in range(1, H-1):
        for px in range(1, W-1):
            p = pa[W*py+px]    # particle
            pal_row = p >> 5
            pal_col = p & P_C
            c = pal[pal_row*4+pal_col]
            buf[o] = c
            o += 1


# Fish air timer (frames before death when out of water)
FISH_AIR_LIMIT = const(180)  # ~3 seconds at 60fps


def update_ant(c):
    """Update a single ant's AI."""
    pa = particles
    px, py = int(c.x), int(c.y)

    # Bounds check - push away from edges instead of dying
    if px <= 2:
        c.x = 3
        c.dir = 1  # Face right
        return
    if px >= W - 3:
        c.x = W - 4
        c.dir = -1  # Face left
        return
    if py <= 2:
        c.y = 3
        return
    if py >= H - 3:
        c.alive = False  # Fell off bottom
        return

    idx = py * W + px
    below_idx = (py + 1) * W + px
    below = pa[below_idx]
    below_is_solid = (below & P_D) == P_D_SOLID

    # Apply gravity if no ground below
    if not below_is_solid:
        c.vy = min(c.vy + 0.2, 2.0)
        c.y += c.vy
        return
    else:
        c.vy = 0

    # Check for water around us (death condition)
    water_count = 0
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        ni = (py + dy) * W + (px + dx)
        if (pa[ni] & P_ID) == (P_WATER & P_ID):
            water_count += 1

    # Die if surrounded by water (3+ sides)
    if water_count >= 3:
        c.alive = False
        return

    # Check side for water - turn around
    side_idx = py * W + (px + c.dir)
    if (pa[side_idx] & P_ID) == (P_WATER & P_ID):
        c.dir *= -1
        return

    # Check if buried (sand above) - dig upward to surface
    above_idx = (py - 1) * W + px
    above = pa[above_idx]
    above_id = (above & P_ID) >> 5
    if above_id == 1:  # SAND above - we're buried!
        # Dig upward
        pa[above_idx] = P_AIR
        c.y = py - 1
        return

    # Random hop! (5% chance when on ground)
    if random.random() < 0.05:
        c.vy = -1.5  # Jump up
        c.y += c.vy
        return

    # Random direction change (3% chance) - prevents getting stuck
    if random.random() < 0.03:
        c.dir *= -1

    # Try to move forward
    next_x = px + c.dir
    next_idx = py * W + next_x
    next_p = pa[next_idx]
    next_id = (next_p & P_ID) >> 5

    # Check if air ahead
    if next_id == 0:  # AIR
        # Check if ground below next position
        next_below_idx = (py + 1) * W + next_x
        next_below = pa[next_below_idx]
        if (next_below & P_D) == P_D_SOLID:
            c.x = next_x
        else:
            # No ground ahead - check if we can step down
            next_below2_idx = (py + 2) * W + next_x
            if py + 2 < H - 1 and (pa[next_below2_idx] & P_D) == P_D_SOLID:
                # Can step down one level
                c.x = next_x
                c.y = py + 1
            else:
                # Too steep down, turn around and maybe hop
                c.dir *= -1
                if random.random() < 0.3:
                    c.vy = -1.2
                    c.y += c.vy
    # Solid ahead - try to climb
    elif (next_p & P_D) == P_D_SOLID:
        # Check if we can climb up (air above us and above-forward)
        above_next_idx = (py - 1) * W + next_x
        can_climb = above_id == 0 and (pa[above_next_idx] & P_ID) >> 5 == 0

        if can_climb:
            # Climb up and forward
            c.x = next_x
            c.y = py - 1
        elif next_id == 1:  # SAND - dig through if can't climb
            pa[next_idx] = P_AIR
            c.x = next_x
        else:
            # Wall or can't climb - turn around and hop to escape
            c.dir *= -1
            if random.random() < 0.4:
                c.vy = -1.5
                c.y += c.vy
    else:
        c.dir *= -1


def update_fish(c):
    """Update a single fish's AI."""
    pa = particles
    px, py = int(c.x), int(c.y)

    # Bounds check
    if px < 1 or px >= W-1 or py < 1 or py >= H-1:
        c.alive = False
        return

    idx = py * W + px
    current_p = pa[idx]
    current_id = (current_p & P_ID) >> 5

    # Check if in water
    in_water = current_id == 2  # WATER

    # Also check if surrounded by water
    water_neighbors = []
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        ny, nx = py + dy, px + dx
        if 0 < ny < H-1 and 0 < nx < W-1:
            ni = ny * W + nx
            if (pa[ni] & P_ID) >> 5 == 2:  # WATER
                water_neighbors.append((ny, nx))
                in_water = True

    if in_water:
        c.timer = 0
        c.vy = 0

        # Slow down - only move ~30% of frames
        if random.random() > 0.3:
            return

        # Occasionally change direction randomly (wandering)
        if random.random() < 0.08:
            c.dir *= -1

        # Bob up or down frequently (25% chance)
        if random.random() < 0.25:
            bob_dir = random.choice([-1, 1])
            new_y = py + bob_dir
            new_idx = new_y * W + px
            if 0 < new_y < H-1 and (pa[new_idx] & P_ID) >> 5 == 2:  # WATER
                c.y = new_y
                return

        # Try to swim horizontally
        next_x = px + c.dir
        next_idx = py * W + next_x
        next_id = (pa[next_idx] & P_ID) >> 5

        if next_id == 2:  # WATER ahead
            c.x = next_x
        else:
            # Blocked - try moving up or down first
            up_idx = (py - 1) * W + px
            down_idx = (py + 1) * W + px
            can_up = py > 1 and (pa[up_idx] & P_ID) >> 5 == 2
            can_down = py < H - 2 and (pa[down_idx] & P_ID) >> 5 == 2

            if can_up and can_down:
                c.y += random.choice([-1, 1])
            elif can_up:
                c.y -= 1
            elif can_down:
                c.y += 1
            else:
                # Completely stuck, flip direction
                c.dir *= -1
    else:
        # Out of water
        c.timer += 1
        c.vy = min(c.vy + 0.1, 1.0)
        c.y += c.vy

        # Die if out too long
        if c.timer >= FISH_AIR_LIMIT:
            c.alive = False


def update_creatures():
    """Update all creatures and handle spawning/death."""
    global creatures
    pa = particles

    # Update each creature
    for c in creatures:
        if not c.alive:
            continue

        if c.ctype == CREATURE_ANT:
            update_ant(c)
        elif c.ctype == CREATURE_FISH:
            update_fish(c)

        # Clamp position (with margin for larger creature sprites)
        c.x = max(5, min(W - 6, c.x))
        c.y = max(5, min(H - 6, c.y))

    # Remove dead creatures, leave corpses
    new_creatures = []
    for c in creatures:
        if c.alive:
            new_creatures.append(c)
        else:
            # Leave corpse (sand particle)
            idx = int(c.y) * W + int(c.x)
            if 0 < idx < W * H:
                pa[idx] = randomColor(P_SAND)

    creatures = new_creatures


def draw_creatures():
    """Draw creatures as shapes on the framebuffer."""
    fb = engine_draw.back_fb()
    for c in creatures:
        if not c.alive:
            continue
        # Convert to screen coords (particle buffer has 1px border)
        sx = int(c.x) - 1
        sy = int(c.y) - 1

        if c.ctype == CREATURE_ANT:
            # Draw ant as filled circle with white border
            col = 0x4208  # Brown
            border = 0xFFFF  # White
            # White border (outline)
            fb.pixel(sx - 2, sy - 2, border)
            fb.pixel(sx + 2, sy - 2, border)
            fb.pixel(sx - 2, sy + 2, border)
            fb.pixel(sx + 2, sy + 2, border)
            for dx in range(-1, 2):
                fb.pixel(sx + dx, sy - 3, border)
                fb.pixel(sx + dx, sy + 3, border)
            for dy in range(-2, 3):
                fb.pixel(sx - 3, sy + dy, border)
                fb.pixel(sx + 3, sy + dy, border)
            # Brown fill
            fb.pixel(sx - 1, sy - 2, col)
            fb.pixel(sx, sy - 2, col)
            fb.pixel(sx + 1, sy - 2, col)
            for dx in range(-2, 3):
                fb.pixel(sx + dx, sy - 1, col)
                fb.pixel(sx + dx, sy, col)
                fb.pixel(sx + dx, sy + 1, col)
            fb.pixel(sx - 1, sy + 2, col)
            fb.pixel(sx, sy + 2, col)
            fb.pixel(sx + 1, sy + 2, col)
        else:
            # Draw fish as triangle pointing in movement direction
            # Orange color
            col = 0xFD20
            if c.dir > 0:  # facing right >
                #     *
                #   ***
                # *****
                #   ***
                #     *
                fb.pixel(sx + 2, sy, col)      # nose tip
                fb.pixel(sx + 1, sy - 1, col)
                fb.pixel(sx + 1, sy, col)
                fb.pixel(sx + 1, sy + 1, col)
                fb.pixel(sx, sy - 1, col)
                fb.pixel(sx, sy, col)
                fb.pixel(sx, sy + 1, col)
                fb.pixel(sx - 1, sy, col)
                fb.pixel(sx - 2, sy, col)      # tail
                fb.pixel(sx + 2, sy - 1, col)  # top edge
                fb.pixel(sx + 2, sy + 1, col)  # bottom edge
            else:  # facing left <
                fb.pixel(sx - 2, sy, col)      # nose tip
                fb.pixel(sx - 1, sy - 1, col)
                fb.pixel(sx - 1, sy, col)
                fb.pixel(sx - 1, sy + 1, col)
                fb.pixel(sx, sy - 1, col)
                fb.pixel(sx, sy, col)
                fb.pixel(sx, sy + 1, col)
                fb.pixel(sx + 1, sy, col)
                fb.pixel(sx + 2, sy, col)      # tail
                fb.pixel(sx - 2, sy - 1, col)  # top edge
                fb.pixel(sx - 2, sy + 1, col)  # bottom edge


shapes = {
    "square": {
        "mass": 1,
        "k": 0.25,
        "friction": 0.25,
        "vertices": {
            "p1": (10, 15),
            "p2": (20, 10),
            "p3": (25, 20),
            "p4": (15, 25)
        },
        "springs": [
            ("p1", "p2", True),
            ("p2", "p3", True),
            ("p3", "p4", True),
            ("p4", "p1", True),
            ("p1", "p3", False),
            ("p2", "p4", False),
        ]
    },
}

vertices = []
springs = []
friction = 1


def loadShape(key):
    global vertices, springs, friction

    vertices = []
    springs = []

    gc.collect()

    shapeData = shapes[key]

    m = shapeData["mass"]
    k = shapeData["k"]
    friction = shapeData["friction"]

    vertexLookup = {}
    vertexData = shapeData["vertices"]
    for vk in vertexData:
        x, y = vertexData[vk]
        vertex = Vertex(x, y, 0, 0, m)
        vertexLookup[vk] = vertex
        vertices.append(vertex)

    for vk1, vk2, visible in shapeData["springs"]:
        v1 = vertexLookup[vk1]
        v2 = vertexLookup[vk2]
        d = dist(v1, v2)
        springs.append(Spring(v1, v2, d, k, visible))

    vertexLookup = None
    gc.collect()


GRAV = const(0.1)
BOUNCE = const(0.25)
DAMP = const(0.1)
MAX_SPEED = const(2)

# Default gravity
DEFAULT_GRAV_X = 0
DEFAULT_GRAV_Y = GRAV

gravX = DEFAULT_GRAV_X
gravY = DEFAULT_GRAV_Y


class Vertex:
    def __init__(self, x, y, dx, dy, mass):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.mass = mass


class Spring:
    def __init__(self, v1, v2, d, k, visible):
        self.v1 = v1
        self.v2 = v2
        self.d = d
        self.k = k
        self.visible = visible


def dist(v1, v2):
    dx = v2.x-v1.x
    dy = v2.y-v1.y
    return math.sqrt(dx*dx + dy*dy)


def shapePhysics():

    for v in vertices:
        px = int(v.x)+1
        py = int(v.y)+1
        p = particles[py*W+px]

        bounce_top = 0
        bounce_bottom = 127
        bounce_left = 0
        bounce_right = 127

        # float up through sand/wall (solids)
        if (p & P_D) == P_D_SOLID:
            bounce_bottom = v.y - 1

        # TODO buoyancy in water?

        cx, cy = int(v.x), int(v.y)

        v.x += v.dx
        v.y += v.dy

        cx2, cy2 = int(v.x), int(v.y)

        # bounce off solids - need to check pixel by pixel
        if cx != cx2 or cy != cy2:
            csx = 1 if cx2 >= cx else -1
            csy = 1 if cy2 >= cy else -1
            while cx != cx2 or cy != cy2:
                if cx != cx2:
                    cx += csx
                if cy != cy2:
                    cy += csy
                if cx < 0 or cx > 127 or cy < 0 or cy > 127:
                    break
                i = (cy+1)*W+(cx+1)
                p2 = particles[i]
                # If we hit solid, check adjacent for bounces
                if (p2 & P_D) == P_D_SOLID:
                    # Horizontal
                    sh = ((particles[i-csx] & P_D) == P_D_SOLID)
                    # Vertical
                    sv = ((particles[i-csy*W] & P_D) == P_D_SOLID)
                    # Diagonal
                    sd = ((particles[i-csy*W-csx] & P_D) == P_D_SOLID)

                    # Bounce Up/Down
                    if sh and (not sv or not sd):
                        if csy > 0:
                            bounce_bottom = cy
                        else:
                            bounce_top = cy
                    # Bounce Left/Right
                    if sv and (not sh or not sd):
                        if csx > 0:
                            bounce_right = cx
                        else:
                            bounce_left = cx



        v.dx += gravX
        v.dy += gravY

        v.dx = max(-MAX_SPEED, min(MAX_SPEED, v.dx))
        v.dy = max(-MAX_SPEED, min(MAX_SPEED, v.dy))

        if v.x < bounce_left:
            v.x = bounce_left
            v.dx = abs(v.dx) * BOUNCE
            v.dy *= friction
        elif v.x > bounce_right:
            v.x = bounce_right
            v.dx = -abs(v.dx) * BOUNCE
            v.dy *= friction
        if v.y < bounce_top:
            v.y = bounce_top
            v.dy = abs(v.dy) * BOUNCE
            v.dx *= friction
        elif v.y > bounce_bottom:
            v.y = bounce_bottom
            v.dy = -abs(v.dy) * BOUNCE
            v.dx *= friction

    for s in springs:
        dx = s.v2.x - s.v1.x
        dy = s.v2.y - s.v1.y
        mag = math.sqrt(dx * dx + dy * dy)

        f = (mag - s.d) * s.k

        if mag == 0:
            continue

        dx /= mag  # Normalize
        dy /= mag  # Normalize

        fx = f * dx - s.v1.dx * DAMP
        fy = f * dy - s.v1.dy * DAMP

        s.v1.dx += fx / s.v1.mass
        s.v1.dy += fy / s.v1.mass
        s.v2.dx -= fx / s.v2.mass
        s.v2.dy -= fy / s.v2.mass


cpx = W//2     # Cursor X
cpy = H//3     # Cursor Y
cdx = 0        # Cursor X Speed
cdy = 0        # Cursor Y Speed
cpick = 0   # Cursor particle selection

CURSOR_ACCEL = const(0.2)
CURSOR_MAX_SPEED = const(2)
CURSOR_DRAG = const(0.8)

loadShape("square")

# Try to load saved game
load_game()

engine.fps_limit(60)

while True:
    if engine.tick():

        # Handle pause menu
        if engine_io.MENU.is_just_pressed:
            pause_menu_active = not pause_menu_active
            pause_menu_selection = 0

        if pause_menu_active:
            # Menu navigation
            if engine_io.UP.is_just_pressed:
                pause_menu_selection = (pause_menu_selection - 1) % len(PAUSE_OPTIONS)
            elif engine_io.DOWN.is_just_pressed:
                pause_menu_selection = (pause_menu_selection + 1) % len(PAUSE_OPTIONS)
            elif engine_io.B.is_just_pressed:
                pause_menu_active = False
            elif engine_io.A.is_just_pressed:
                if pause_menu_selection == 0:  # Resume
                    pause_menu_active = False
                elif pause_menu_selection == 1:  # Save & Quit
                    save_game()
                    engine.end()
                    break
                elif pause_menu_selection == 2:  # Clear
                    for i in range(W * H):
                        particles[i] = P_AIR
                    # Restore walls
                    for px in range(W):
                        particles[px] = P_WALL
                        particles[W*(H-1)+px] = P_WALL
                    for py in range(H):
                        particles[py*W] = P_WALL
                        particles[py*W+(W-1)] = P_WALL
                    creatures.clear()
                    pause_menu_active = False
                elif pause_menu_selection == 3:  # Quit
                    engine.end()
                    break

            # Draw game frame then menu overlay
            render()
            draw_creatures()
            draw_pause_menu()
            continue

        # Cursor Inputs
        cax, cay = 0, 0
        if engine_io.UP.is_pressed:
            cay -= CURSOR_ACCEL
        if engine_io.DOWN.is_pressed:
            cay += CURSOR_ACCEL
        if engine_io.LEFT.is_pressed:
            cax -= CURSOR_ACCEL
        if engine_io.RIGHT.is_pressed:
            cax += CURSOR_ACCEL

        # Cursor Motion
        if cax != 0:
            cdx = max(-CURSOR_MAX_SPEED, min(CURSOR_MAX_SPEED, cdx + cax))
        else:
            cdx *= CURSOR_DRAG
        if cay != 0:
            cdy = max(-CURSOR_MAX_SPEED, min(CURSOR_MAX_SPEED, cdy + cay))
        else:
            cdy *= CURSOR_DRAG
        cpx = max(1, min(W-3, cpx + cdx))
        cpy = max(1, min(H-3, cpy + cdy))

        # Cycle particle selection
        if engine_io.RB.is_just_pressed:
            cpick = (cpick + 1) % len(Picks)
        if engine_io.LB.is_just_pressed:
            cpick = (cpick + len(Picks) - 1) % len(Picks)

        # Rounded to nearest pixel
        cx = int(cpx)
        cy = int(cpy)

        # Draw particles or spawn creatures near cursor
        if engine_io.A.is_pressed:
            p = Picks[cpick]
            p_id = (p & P_ID) >> 5

            # Creature spawning (single creature, not 3x3)
            if p_id == 4:  # ANT
                if len(creatures) < MAX_CREATURES and engine_io.A.is_just_pressed:
                    creatures.append(Creature(cx + 1, cy + 1, CREATURE_ANT))
            elif p_id == 5:  # FISH
                if len(creatures) < MAX_CREATURES and engine_io.A.is_just_pressed:
                    creatures.append(Creature(cx + 1, cy + 1, CREATURE_FISH))
            else:
                # Normal particle spawning
                for y in range(3):
                    for x in range(3):
                        particles[(cy+y)*W+cx+x] = randomColor(p)

        # Remove particles near cursor (and kill creatures)
        if engine_io.B.is_pressed:
            for y in range(3):
                for x in range(3):
                    px, py = cx + x, cy + y
                    # Kill any creatures in this area
                    for c in creatures:
                        if int(c.x) == px and int(c.y) == py:
                            c.alive = False
                    particles[py*W+px] = P_AIR

        # Once each frame, update physics, creatures, and render
        physics()
        update_creatures()
        render()
        draw_creatures()

        # Shape Physics
        shapePhysics()

        fb = engine_draw.back_fb()

        # Overlay shape
        for spring in springs:
            if not spring.visible:
                continue
            v1 = spring.v1
            v2 = spring.v2
            fb.line(int(v1.x), int(v1.y), int(v2.x), int(v2.y), 0xb082)

        # Overlay cursor
        fb.line(cx+1, cy+1, cx+3, cy+3, 0x0000)
        fb.rect(cx+3, cy+3, 5, 5, palettes_raw[4*(Picks[cpick] >> 5)], True)
        fb.rect(cx+3, cy+3, 5, 5, 0x0000, False)
