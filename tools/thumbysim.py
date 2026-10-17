"""Headless stand-in for the Thumby Color engine so a game's main.py can run on desktop CPython.

Usage: run_game(main_path, driver, max_frames, out_dir)
  driver(frame, game_globals) -> (set_of_pressed_button_names, list_of_snapshot_names)
"""
import builtins
import os
import random
import struct
import sys
import types
import zlib

SCREEN = 128

# --- MicroPython builtins -------------------------------------------------
builtins.const = lambda x: x
_mp = types.ModuleType("micropython")
_mp.viper = lambda f: f
_mp.native = lambda f: f
_mp.const = lambda x: x
builtins.micropython = _mp
sys.modules["micropython"] = _mp
builtins.ptr8 = lambda b: b
builtins.ptr16 = lambda b: memoryview(b).cast("B").cast("H")
builtins.ptr32 = lambda b: memoryview(b).cast("B").cast("i")

_back = bytearray(SCREEN * SCREEN * 2)
_front = bytearray(SCREEN * SCREEN * 2)


class FrameBuffer:
    """Subset of MicroPython framebuf.FrameBuffer for RGB565."""

    def __init__(self, data, w, h):
        self.data = data
        self.w = w
        self.h = h

    @property
    def mv(self):
        return memoryview(self.data).cast("H")

    def pixel(self, x, y, c=None):
        x = int(x); y = int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            if c is None:
                return self.mv[y * self.w + x]
            self.mv[y * self.w + x] = c & 0xFFFF

    def fill(self, c):
        self.mv[:] = memoryview(struct.pack("<H", c & 0xFFFF) * (self.w * self.h)).cast("H")

    def fill_rect(self, x, y, w, h, c):
        x = int(x); y = int(y); w = int(w); h = int(h)
        mv = self.mv
        for yy in range(max(0, y), min(self.h, y + h)):
            for xx in range(max(0, x), min(self.w, x + w)):
                mv[yy * self.w + xx] = c & 0xFFFF

    def rect(self, x, y, w, h, c, f=False):
        if f:
            return self.fill_rect(x, y, w, h, c)
        self.hline(x, y, w, c); self.hline(x, y + h - 1, w, c)
        self.vline(x, y, h, c); self.vline(x + w - 1, y, h, c)

    def hline(self, x, y, w, c):
        self.fill_rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.fill_rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c):
        x0 = int(x0); y0 = int(y0); x1 = int(x1); y1 = int(y1)
        dx = abs(x1 - x0); dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.pixel(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy; x0 += sx
            if e2 <= dx:
                err += dx; y0 += sy

    def ellipse(self, x, y, xr, yr, c, f=False, m=15):
        x = int(x); y = int(y); xr = max(0, int(xr)); yr = max(0, int(yr))
        for yy in range(-yr, yr + 1):
            for xx in range(-xr, xr + 1):
                v = (xx * xx) / max(1, xr * xr) + (yy * yy) / max(1, yr * yr)
                if (f and v <= 1.0) or (not f and 0.75 <= v <= 1.0):
                    self.pixel(x + xx, y + yy, c)

    def text(self, s, x, y, c):
        # Approximates the 8x8 font with the game's own 3x5 glyph scaled 2x where possible
        font = _GAME.get("FONT")
        for ch in str(s):
            code = ord(ch.upper()) - 32
            if font is not None and 0 <= code < 96:
                # 5 glyph rows stretched to 8 pixels tall (heights 2,1,2,1,2), 2 pixels wide
                row_y = (0, 2, 3, 5, 6)
                row_h = (2, 1, 2, 1, 2)
                for ry in range(5):
                    bits = font[code * 5 + ry]
                    for rx in range(3):
                        if (bits >> (2 - rx)) & 1:
                            self.fill_rect(x + 1 + rx * 2, y + row_y[ry], 2, row_h[ry], c)
            x += 8


_GAME = {}
_back_fb = FrameBuffer(_back, SCREEN, SCREEN)

# --- engine modules ---------------------------------------------------------
engine_main = types.ModuleType("engine_main")

engine_draw = types.ModuleType("engine_draw")
engine_draw.back_fb_data = lambda: _back
engine_draw.back_fb = lambda: _back_fb


class Button:
    def __init__(self, name):
        self.name = name
        self.is_pressed = False
        self.is_just_pressed = False
        self.is_just_released = False

    def set(self, down):
        self.is_just_pressed = down and not self.is_pressed
        self.is_just_released = (not down) and self.is_pressed
        self.is_pressed = down


engine_io = types.ModuleType("engine_io")
BUTTONS = {}
for _n in ("UP", "DOWN", "LEFT", "RIGHT", "A", "B", "LB", "RB", "MENU"):
    BUTTONS[_n] = Button(_n)
    setattr(engine_io, _n, BUTTONS[_n])


class _Channel:
    gain = 1.0


engine_audio = types.ModuleType("engine_audio")
engine_audio.play = lambda snd, ch, loop: _Channel()
engine_audio.stop = lambda ch: None
engine_audio.set_volume = lambda v: None

engine_resources = types.ModuleType("engine_resources")


class WaveSoundResource:
    def __init__(self, path):
        self.path = path


class ToneSoundResource:
    frequency = 1000.0


engine_resources.WaveSoundResource = WaveSoundResource
engine_resources.ToneSoundResource = ToneSoundResource

engine_save = types.ModuleType("engine_save")
SAVE = {}
engine_save._init_saves_dir = lambda p: None
engine_save.set_location = lambda p: None
engine_save.save = lambda k, v: SAVE.__setitem__(k, v)
engine_save.load = lambda k, d=None: SAVE.get(k, d)
engine_save.delete = lambda k: SAVE.pop(k, None)


class StopSim(Exception):
    pass


engine = types.ModuleType("engine")
_state = {"frame": 0, "driver": None, "max": 0, "out": ".", "snaps": []}


def write_png(path, data, scale=3):
    mv = memoryview(data).cast("H")
    rows = []
    for y in range(SCREEN):
        row = bytearray([0])
        for x in range(SCREEN):
            c = mv[y * SCREEN + x]
            r = ((c >> 11) & 0x1F) * 255 // 31
            g = ((c >> 5) & 0x3F) * 255 // 63
            b = (c & 0x1F) * 255 // 31
            row += bytes((r, g, b)) * scale
        for _ in range(scale):
            rows.append(bytes(row))
    raw = b"".join(rows)
    w = h = SCREEN * scale

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def _tick():
    st = _state
    # "Send" what the game drew last frame, then clear like the real engine
    _front[:] = _back
    for name in st["pending_snaps"]:
        p = os.path.join(st["out"], name + ".png")
        write_png(p, _front)
        st["snaps"].append(p)
    st["pending_snaps"] = []
    _back[:] = bytes(len(_back))

    st["frame"] += 1
    if st["frame"] > st["max"]:
        raise StopSim()
    g = sys._getframe(1).f_globals
    _GAME.update(g)
    pressed, snaps = st["driver"](st["frame"], g)
    for n, b in BUTTONS.items():
        b.set(n in pressed)
    st["pending_snaps"] = list(snaps)
    return True


engine.tick = _tick
engine.fps_limit = lambda f: None
engine.end = lambda: None

for _m in (engine_main, engine, engine_io, engine_draw, engine_audio, engine_resources, engine_save):
    sys.modules[_m.__name__] = _m


def run_game(main_path, driver, max_frames, out_dir, seed=1):
    import runpy
    random.seed(seed)
    os.makedirs(out_dir, exist_ok=True)
    _state.update(frame=0, driver=driver, max=max_frames, out=out_dir, snaps=[], pending_snaps=[])
    old = os.getcwd()
    os.chdir(os.path.dirname(os.path.abspath(main_path)))
    try:
        runpy.run_path(main_path, run_name="__main__")
    except StopSim:
        pass
    finally:
        os.chdir(old)
    return _state["snaps"]
