import engine_main

import engine
import engine_io
import engine_draw
import engine_audio
from engine_nodes import Sprite2DNode, CameraNode
from engine_resources import TextureResource, WaveSoundResource

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

# Particle IDs (already shifted into the ID bits, compare against p & P_ID)
I_AIR = const(0 << 5)
I_SAND = const(1 << 5)
I_WATER = const(2 << 5)
I_WALL = const(3 << 5)
I_FUSE = const(4 << 5)
I_BOMB = const(5 << 5)
I_FIRE = const(6 << 5)
I_LIT = const(7 << 5)

# Particle definitions
#   - Each type of particle consists of an ID, static flag, density value, and color value
#   - By using bitwise OR, they can be composed by combining each category value
#   - FIRE and LIT are not static, but have their own rules in physics() instead of falling
P_AIR = const(I_AIR | P_S_STATIC | P_D_GAS)
P_SAND = const(I_SAND | P_D_SOLID)
P_WATER = const(I_WATER | P_D_LIQUID)
P_WALL = const(I_WALL | P_S_STATIC | P_D_SOLID)
P_FUSE = const(I_FUSE | P_S_STATIC | P_D_SOLID)   # Burns slowly along its length
P_BOMB = const(I_BOMB | P_S_STATIC | P_D_SOLID)   # Explodes when fire touches it
P_FIRE = const(I_FIRE | P_D_GAS)                  # Rises, flickers, burns out
P_LIT = const(I_LIT | P_D_SOLID)                  # A fuse that is burning

# Creature type constants
CREATURE_ANT = const(0)
CREATURE_FISH = const(1)
MAX_CREATURES = const(20)

# Creature tools aren't particles, so they use values outside the particle range
TOOL_ANT = const(-1)
TOOL_FISH = const(-2)

# Tools to pick from with LB/RB: (name, particle or creature tool, cursor color)
Tools = [
    ("SAND", P_SAND, 0xe736),
    ("WATER", P_WATER, 0x63d7),
    ("WALL", P_WALL, 0xa513),
    ("FUSE", P_FUSE, 0x5B66),
    ("BOMB", P_BOMB, 0xC926),
    ("FIRE", P_FIRE, 0xFD20),
    ("ANT", TOOL_ANT, 0x4208),
    ("FISH", TOOL_FISH, 0xFD20),
]

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
particles = bytearray(W*H)  # Particle type
state = bytearray(W*H)      # Particle state (moved, bias)

# Random number state shared by the viper functions (they can't call random cheaply)
rng = bytearray(4)
rng[0] = random.getrandbits(8)
rng[1] = random.getrandbits(8)

# Explosions that happened this frame, for sound/shake/creatures: [count, x0, y0, x1, y1, ...]
MAX_BOOMS = const(8)
booms = bytearray(1 + 2*MAX_BOOMS)
BOOM_R = const(9)       # Explosion radius in pixels


def reset_particles():
    """Fill the screen with air, with the extra along the edges as walls."""
    for i in range(W * H):
        particles[i] = P_AIR
    for px in range(W):
        particles[px] = P_WALL
        particles[W*(H-1)+px] = P_WALL
    for py in range(H):
        particles[py*W] = P_WALL
        particles[py*W+(W-1)] = P_WALL


reset_particles()


# Creature class for ants and fish
class Creature:
    def __init__(self, x, y, ctype):
        self.x = x
        self.y = y
        self.ctype = ctype
        self.dir = random.choice([-1, 1])
        self.alive = True
        self.burnt = False   # Burnt creatures don't leave a corpse
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
    engine_save.save("particles", particles)
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

        # Older saves stored the particles as a hex string
        if isinstance(saved_particles, str):
            saved_particles = bytearray.fromhex(saved_particles)
        if len(saved_particles) != len(particles):
            return False
        for i in range(len(particles)):
            particles[i] = saved_particles[i]
        saved_particles = None
        gc.collect()

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
        return True
    except Exception:
        # If loading fails, start fresh
        reset_particles()
        creatures = []
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
def explode(x: int, y: int):
    """Blow up everything (except walls) in a circle around x, y and fill it with fire."""
    pa = ptr8(particles)
    sa = ptr8(state)
    rs = ptr32(rng)
    bq = ptr8(booms)
    r = rs[0]

    # Remember the explosion for sound, screen shake and creatures
    n = bq[0]
    if n < MAX_BOOMS:
        bq[1 + n*2] = x
        bq[2 + n*2] = y
        bq[0] = n + 1

    x0 = x - BOOM_R
    if x0 < 1:
        x0 = 1
    x1 = x + BOOM_R
    if x1 > W-2:
        x1 = W-2
    y0 = y - BOOM_R
    if y0 < 1:
        y0 = 1
    y1 = y + BOOM_R
    if y1 > H-2:
        y1 = H-2

    yy = y0
    while yy <= y1:
        dy = yy - y
        xx = x0
        while xx <= x1:
            dx = xx - x
            r = (r * 1664525 + 1013904223) & 0x3fffffff
            rb = r >> 16
            # Jitter the edge so the blast isn't a perfect circle
            if dx*dx + dy*dy <= BOOM_R*BOOM_R - (rb & 15):
                i = W * yy + xx
                if (pa[i] & P_ID) != I_WALL:
                    if (rb >> 4) & 3:
                        pa[i] = P_FIRE | ((rb >> 6) & 3)
                    else:
                        pa[i] = P_AIR
                    sa[i] |= S_M_MOVED
            xx += 1
        yy += 1

    rs[0] = r


@micropython.viper
def physics():
    # Viper pointers for quick access to the buffers
    pa = ptr8(particles)
    sa = ptr8(state)
    rs = ptr32(rng)
    r = rs[0]

    for py in range(1, H-1):
        for i in range(W-2):
            # Every other row, reverse processing order to reduce left-right bias
            # (this trick may not be needed anymore, since I added a bias state?)
            if py & 0b1:
                px = 1 + i
            else:
                px = (W-2) - i

            mi = W * py + px   # middle index (particle/state being processed)

            mmp, mms = pa[mi], sa[mi]   # middle particle, middle state

            # Skip processing this particle if flagged static (air, wall, fuse, bomb) or already moved this frame
            if mmp & P_S_STATIC or mms & S_M_MOVED:
                continue

            pid = mmp & P_ID

            # FIRE: lights fuses, sets off bombs, goes out in water, rises and burns out
            if pid == I_FIRE:
                r = (r * 1664525 + 1013904223) & 0x3fffffff
                rb = r >> 16
                doused = 0
                boomed = 0
                k = 0
                while k < 4:
                    if k == 0:
                        nx, ny = px, py - 1
                    elif k == 1:
                        nx, ny = px, py + 1
                    elif k == 2:
                        nx, ny = px - 1, py
                    else:
                        nx, ny = px + 1, py
                    ni = W * ny + nx
                    q = pa[ni] & P_ID
                    if q == I_WATER:
                        doused = 1
                    elif q == I_FUSE:
                        pa[ni] = P_LIT | (pa[ni] & P_C)
                        sa[ni] |= S_M_MOVED
                    elif q == I_BOMB:
                        rs[0] = r
                        explode(nx, ny)
                        r = rs[0]
                        boomed = 1
                        break
                    k += 1
                if boomed:
                    continue
                if doused or (rb & 15) == 0:
                    pa[mi] = P_AIR
                    continue
                c = (rb >> 4) & 3   # flicker
                # Drift up (straight, or up-left/up-right) about half the time
                if (rb >> 6) & 1:
                    d = (rb >> 7) & 3
                    if d == 0:
                        ti = mi - W - 1
                    elif d == 1:
                        ti = mi - W + 1
                    else:
                        ti = mi - W
                    if (pa[ti] & P_ID) == I_AIR and not sa[ti] & S_M_MOVED:
                        pa[ti] = P_FIRE | c
                        sa[ti] |= S_M_MOVED
                        pa[mi] = P_AIR
                        continue
                pa[mi] = P_FIRE | c
                continue

            # LIT FUSE: sparkles, then burns away and lights the fuse/bombs next to it
            if pid == I_LIT:
                r = (r * 1664525 + 1013904223) & 0x3fffffff
                rb = r >> 16
                c = (rb >> 3) & 3
                # Water puts a burning fuse out
                if ((pa[mi-W] & P_ID) == I_WATER or (pa[mi+W] & P_ID) == I_WATER
                        or (pa[mi-1] & P_ID) == I_WATER or (pa[mi+1] & P_ID) == I_WATER):
                    pa[mi] = P_FUSE | c
                    continue
                if (rb & 7) != 0:
                    pa[mi] = P_LIT | c
                    continue
                pa[mi] = P_FIRE | c
                sa[mi] |= S_M_MOVED
                dy = -1
                while dy <= 1:
                    dx = -1
                    while dx <= 1:
                        ni = mi + dy * W + dx
                        q = pa[ni] & P_ID
                        if q == I_FUSE:
                            pa[ni] = P_LIT | (pa[ni] & P_C)
                            sa[ni] |= S_M_MOVED
                        elif q == I_BOMB:
                            rs[0] = r
                            explode(px + dx, py + dy)
                            r = rs[0]
                        dx += 1
                    dy += 1
                continue

            mmpd = mmp & P_D            # middle particle density
            mmsb = mms & S_B            # middle state bias flag

            # Use bias flag to determine priority (1, 2) when deciding middle sideways movement
            if mmpd == P_D_LIQUID:
                if mmsb:
                    msi1, msi2 = mi-1, mi+1     # middle side index 1 & 2
                else:
                    msi1, msi2 = mi+1, mi-1     # middle side index 1 & 2
                msp1, mss1 = pa[msi1], sa[msi1]  # m side 1 particle & state
                msp2, mss2 = pa[msi2], sa[msi2]  # m side 2 particle & state

            di = mi + W                # down index (pixel below)
            dmp, dms = pa[di], sa[di]   # down particle, down state

            # Use bias flag to determine priority (1, 2) when deciding down sideways movement
            if mmsb:
                dsi1, dsi2 = di-1, di+1     # down side index 1 & 2
            else:
                dsi1, dsi2 = di+1, di-1     # down side index 1 & 2
            dsp1, dss1 = pa[dsi1], sa[dsi1]  # d side 1 particle & state
            dsp2, dss2 = pa[dsi2], sa[dsi2]  # d side 2 particle & state

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

    rs[0] = r

    # Reset moved flag for all to be ready for next frame
    for i in range(W*H):
        sa[i] &= S_M_INV_MOVED


palettes_raw = [
    0x2965, 0x2965, 0x2965, 0x2965,  # AIR (ID 0)
    0xe736, 0xd6d5, 0xdef6, 0xf7b8,  # SAND (ID 1)
    0x63d7, 0x63d7, 0x63d7, 0x63d7,  # WATER (ID 2)
    0xa513, 0xa4f2, 0x94b1, 0x9490,  # WALL (ID 3)
    0x5B66, 0x4AE4, 0x63A7, 0x5345,  # FUSE (ID 4) - green cord
    0xC926, 0xB0E4, 0xD967, 0xA8A3,  # BOMB (ID 5) - red TNT
    0xFF8F, 0xFD00, 0xFA80, 0xFFFB,  # FIRE (ID 6) - yellow/orange/red/white
    0xFFFF, 0xFEE7, 0xFDA0, 0xFF96,  # LIT FUSE (ID 7) - sparks
]
palettes = bytearray([((v >> (8*i)) & 0xFF)
                     for v in palettes_raw for i in range(2)])


@micropython.native
def randomColor(pick):
    c = random.randrange(0, 4)
    return (pick & 0b11111100) | c


@micropython.viper
def render(oy: int):
    # oy shifts the picture up/down for screen shake

    # Viper pointers for quick access to the buffers
    buf = ptr16(engine_draw.back_fb_data())
    pa = ptr8(particles)
    pal = ptr16(palettes)

    for sy in range(128):
        o = sy * 128   # screen index
        py = sy - oy + 1
        if py < 1 or py > H-2:
            for sx in range(128):
                buf[o + sx] = 0
            continue
        row = W * py + 1
        for sx in range(128):
            p = pa[row + sx]    # particle
            buf[o + sx] = pal[(p >> 5)*4 + (p & P_C)]


# Fish air timer (frames before death when out of water)
FISH_AIR_LIMIT = const(180)  # ~3 seconds at 60fps


def move_y(c):
    """Move a creature by its vy one pixel at a time so it can't fall through thin floors."""
    pa = particles
    px = int(c.x)
    y = int(c.y)
    target = c.y + c.vy
    ty = int(target)
    step = 1 if ty > y else -1
    while y != ty:
        ny = y + step
        if ny < 1 or ny > H-2 or (pa[ny*W+px] & P_D) == P_D_SOLID:
            c.y = y
            c.vy = 0
            return
        y = ny
    c.y = target


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
        c.vy = 0
        return

    below_idx = (py + 1) * W + px
    below = pa[below_idx]
    below_is_solid = (below & P_D) == P_D_SOLID

    # Apply gravity if no ground below
    if not below_is_solid:
        c.vy = min(c.vy + 0.2, 2.0)
        move_y(c)
        return
    else:
        c.vy = 0

    # Check for water around us (death condition)
    water_count = 0
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        ni = (py + dy) * W + (px + dx)
        if (pa[ni] & P_ID) == I_WATER:
            water_count += 1

    # Die if surrounded by water (3+ sides)
    if water_count >= 3:
        c.alive = False
        return

    # Check side for water - turn around
    side_idx = py * W + (px + c.dir)
    if (pa[side_idx] & P_ID) == I_WATER:
        c.dir *= -1
        return

    # Check if buried (sand above) - dig upward to surface
    above_idx = (py - 1) * W + px
    above_id = pa[above_idx] & P_ID
    if above_id == I_SAND:  # SAND above - we're buried!
        # Dig upward
        pa[above_idx] = P_AIR
        c.y = py - 1
        return

    # Random hop! (5% chance when on ground)
    if random.random() < 0.05:
        c.vy = -1.5  # Jump up
        move_y(c)
        return

    # Random direction change (3% chance) - prevents getting stuck
    if random.random() < 0.03:
        c.dir *= -1

    # Try to move forward
    next_x = px + c.dir
    next_idx = py * W + next_x
    next_p = pa[next_idx]
    next_id = next_p & P_ID

    # Check if air ahead
    if next_id == I_AIR:
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
                    move_y(c)
    # Solid ahead - try to climb
    elif (next_p & P_D) == P_D_SOLID:
        # Check if we can climb up (air above us and above-forward)
        above_next_idx = (py - 1) * W + next_x
        can_climb = above_id == I_AIR and (pa[above_next_idx] & P_ID) == I_AIR

        if can_climb:
            # Climb up and forward
            c.x = next_x
            c.y = py - 1
        elif next_id == I_SAND:  # dig through if can't climb
            pa[next_idx] = P_AIR
            c.x = next_x
        else:
            # Wall or can't climb - turn around and hop to escape
            c.dir *= -1
            if random.random() < 0.4:
                c.vy = -1.5
                move_y(c)
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

    # In water if on a water pixel or next to one
    in_water = (pa[py * W + px] & P_ID) == I_WATER
    if not in_water:
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if (pa[(py + dy) * W + px + dx] & P_ID) == I_WATER:
                in_water = True
                break

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
            if 0 < new_y < H-1 and (pa[new_idx] & P_ID) == I_WATER:
                c.y = new_y
                return

        # Try to swim horizontally
        next_x = px + c.dir
        next_idx = py * W + next_x
        next_id = pa[next_idx] & P_ID

        if next_id == I_WATER:
            c.x = next_x
        else:
            # Blocked - try moving up or down first
            up_idx = (py - 1) * W + px
            down_idx = (py + 1) * W + px
            can_up = py > 1 and (pa[up_idx] & P_ID) == I_WATER
            can_down = py < H - 2 and (pa[down_idx] & P_ID) == I_WATER

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
        move_y(c)

        # Die if out too long
        if c.timer >= FISH_AIR_LIMIT:
            c.alive = False


def creature_on_fire(c):
    """True if the creature's body is touching fire."""
    pa = particles
    idx = int(c.y) * W + int(c.x)
    if (pa[idx] & P_ID) == I_FIRE:
        return True
    # Ants are drawn standing on their pixel, so check their head too
    if c.ctype == CREATURE_ANT and c.y > 4 and (pa[idx - 3*W] & P_ID) == I_FIRE:
        return True
    return False


def update_creatures():
    """Update all creatures and handle spawning/death."""
    global creatures
    pa = particles

    # Update each creature
    for c in creatures:
        if not c.alive:
            continue

        if creature_on_fire(c):
            c.alive = False
            c.burnt = True
            continue

        if c.ctype == CREATURE_ANT:
            update_ant(c)
        elif c.ctype == CREATURE_FISH:
            update_fish(c)

        # Keep inside the walls
        c.x = max(2, min(W - 3, c.x))
        c.y = max(2, min(H - 2, c.y))

    # Remove dead creatures, leave corpses
    new_creatures = []
    for c in creatures:
        if c.alive:
            new_creatures.append(c)
        elif not c.burnt:
            # Leave corpse (sand particle)
            idx = int(c.y) * W + int(c.x)
            pa[idx] = randomColor(P_SAND)

    creatures = new_creatures


def draw_creatures(oy):
    """Draw creatures as shapes on the framebuffer."""
    fb = engine_draw.back_fb()
    for c in creatures:
        if not c.alive:
            continue
        # Convert to screen coords (particle buffer has 1px border)
        sx = int(c.x) - 1
        sy = int(c.y) - 1 + oy

        if c.ctype == CREATURE_ANT:
            # Draw ant as filled circle with white border, standing on its pixel
            sy -= 3
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


# Explosion effects
try:
    boom_sound = WaveSoundResource("boom.wav")
except Exception:
    boom_sound = None
shake = 0           # Frames of screen shake left
boom_cooldown = 0   # Frames before the boom sound can play again


def handle_booms():
    """Sound, shake, and knock things around for any explosions this frame."""
    global shake, boom_cooldown
    if boom_cooldown > 0:
        boom_cooldown -= 1
    n = booms[0]
    if n == 0:
        return
    booms[0] = 0
    shake = 10
    if boom_sound is not None and boom_cooldown == 0:
        engine_audio.play(boom_sound, 0, False)
        boom_cooldown = 8
    reach = BOOM_R + 3
    for k in range(n):
        bx = booms[1 + k*2]
        by = booms[2 + k*2]
        # Creatures caught in the blast are gone
        for c in creatures:
            if abs(c.x - bx) <= reach and abs(c.y - by) <= reach:
                c.alive = False
                c.burnt = True
        # Fling the floating square away from the blast
        for v in vertices:
            dx = v.x - (bx - 1)
            dy = v.y - (by - 1)
            d = math.sqrt(dx*dx + dy*dy)
            if 0 < d < 30:
                push = (30 - d) / 10
                v.dx += dx / d * push
                v.dy += dy / d * push


cpx = W//2     # Cursor X
cpy = H//3     # Cursor Y
cdx = 0        # Cursor X Speed
cdy = 0        # Cursor Y Speed
cpick = 0   # Cursor tool selection
tool_label_timer = 90   # Frames to show the tool name for (shown at start too)

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
                    reset_particles()
                    creatures.clear()
                    pause_menu_active = False
                elif pause_menu_selection == 3:  # Quit
                    engine.end()
                    break

            # Draw game frame then menu overlay
            render(0)
            draw_creatures(0)
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
        # The 3x3 brush covers cx..cx+2, so stop before it reaches the edge walls
        cpx = max(1, min(W-4, cpx + cdx))
        cpy = max(1, min(H-4, cpy + cdy))

        # Cycle tool selection
        if engine_io.RB.is_just_pressed:
            cpick = (cpick + 1) % len(Tools)
            tool_label_timer = 60
        if engine_io.LB.is_just_pressed:
            cpick = (cpick + len(Tools) - 1) % len(Tools)
            tool_label_timer = 60

        # Rounded to nearest pixel
        cx = int(cpx)
        cy = int(cpy)

        tool_name, tool, tool_color = Tools[cpick]

        # Draw particles or spawn creatures near cursor
        if engine_io.A.is_pressed:
            # Creature spawning (single creature, not 3x3)
            if tool == TOOL_ANT or tool == TOOL_FISH:
                if len(creatures) < MAX_CREATURES and engine_io.A.is_just_pressed:
                    ctype = CREATURE_ANT if tool == TOOL_ANT else CREATURE_FISH
                    creatures.append(Creature(cx + 1, cy + 1, ctype))
            elif tool == P_FIRE:
                # Fire only goes into empty space, and lights whatever it touches
                for y in range(3):
                    for x in range(3):
                        i = (cy+y)*W + cx+x
                        q = particles[i] & P_ID
                        if q == I_AIR:
                            particles[i] = randomColor(P_FIRE)
                        elif q == I_FUSE:
                            particles[i] = P_LIT | (particles[i] & P_C)
                        elif q == I_BOMB:
                            explode(cx+x, cy+y)
            else:
                # Normal particle spawning
                for y in range(3):
                    for x in range(3):
                        particles[(cy+y)*W+cx+x] = randomColor(tool)

        # Remove particles near cursor (and kill creatures)
        if engine_io.B.is_pressed:
            for c in creatures:
                if abs(c.x - (cx + 1)) <= 2 and abs(c.y - (cy + 1)) <= 3:
                    c.alive = False
            for y in range(3):
                for x in range(3):
                    particles[(cy+y)*W+cx+x] = P_AIR

        # Once each frame, update physics, creatures, and render
        physics()
        handle_booms()
        update_creatures()

        oy = 0
        if shake > 0:
            amp = (shake + 2) // 3
            oy = random.randint(-amp, amp)
            shake -= 1
        render(oy)
        draw_creatures(oy)

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
        fb.rect(cx+3, cy+3, 5, 5, tool_color, True)
        fb.rect(cx+3, cy+3, 5, 5, 0x0000, False)

        # Show the tool name for a moment after switching
        if tool_label_timer > 0:
            tool_label_timer -= 1
            fb.rect(1, 1, len(tool_name) * 8 + 4, 11, 0x0000, True)
            fb.text(tool_name, 3, 3, tool_color)
