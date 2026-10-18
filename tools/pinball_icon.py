"""Usage: python pinball_icon.py ../1Pinball/icon.bmp

Draw the 38x38 Space Pinball menu icon as a 16-bit X1R5G5B5 BMP (same layout as scorched_icon.py)."""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumbysim

S = 38
img = [[(6, 4, 22)] * S for _ in range(S)]


def put(x, y, c):
    if 0 <= x < S and 0 <= y < S:
        img[y][x] = c


def disc(cx, cy, r, c):
    for y in range(S):
        for x in range(S):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                put(x, y, c)


def capsule(x0, y0, x1, y1, r0, r1, c):
    for y in range(S):
        for x in range(S):
            px, py = x + 0.5, y + 0.5
            dx, dy = x1 - x0, y1 - y0
            t = max(0, min(1, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
            qx, qy = x0 + dx * t, y0 + dy * t
            r = r0 + (r1 - r0) * t
            if (px - qx) ** 2 + (py - qy) ** 2 <= r * r:
                put(x, y, c)


# Stars
s = 99
for i in range(26):
    s = (s * 1103515245 + 12345) & 0x7FFFFFFF
    x = (s >> 8) % S
    s = (s * 1103515245 + 12345) & 0x7FFFFFFF
    y = (s >> 8) % 26
    put(x, y, ((90, 90, 130), (170, 170, 220), (255, 255, 255))[(s >> 4) % 3])

# Side walls
for y in range(S):
    put(0, y, (150, 140, 230))
    put(S - 1, y, (150, 140, 230))

# Ringed planet up top
disc(12, 11, 7, (90, 200, 230))
for y in range(S):
    for x in range(S):
        if (x + 0.5 - 12) ** 2 + (y + 0.5 - 11) ** 2 <= 49 and (x - 9) ** 2 + (y - 8) ** 2 > 64:
            put(x, y, (40, 90, 140))
for i in range(120):
    a = i * 2 * math.pi / 120
    x = 12 + 11 * math.cos(a)
    y = 11 + 3 * math.sin(a) - 2 * math.cos(a)
    if not (math.sin(a) < 0 and abs(x - 12) < 7):
        put(int(x), int(y), (230, 190, 120))

# Pop bumpers
for cx, cy, c, ring in ((29, 9, (230, 60, 60), (255, 150, 150)), (26, 21, (60, 130, 255), (150, 220, 255))):
    disc(cx, cy, 5, ring)
    disc(cx, cy, 3.3, c)

# Alien
ALIEN = ("..####..", ".######.", "##o##o##", "########", ".#.##.#.", "#......#")
for ry, row in enumerate(ALIEN):
    for rx, ch in enumerate(row):
        if ch == "#":
            put(5 + rx, 21 + ry, (90, 235, 90))
        elif ch == "o":
            put(5 + rx, 21 + ry, (10, 20, 10))

# Flippers: left one swung up, right one at rest
capsule(5, 33, 16, 27, 2.6, 1.6, (240, 60, 90))
capsule(5, 33, 16, 27, 1.6, 0.7, (240, 240, 250))
capsule(33, 33, 23, 37, 2.6, 1.6, (240, 60, 90))
capsule(33, 33, 23, 37, 1.6, 0.7, (240, 240, 250))

# Ball flying off the left flipper, with a short trail
for k, (tx, ty) in enumerate(((15, 27), (16, 25), (17, 23))):
    put(tx, ty, (80, 80, 120))
disc(19.5, 20.5, 2.6, (110, 115, 140))
disc(19, 20, 1.9, (190, 195, 215))
put(18, 19, (255, 255, 255))

# Write BMP: 56-byte BITMAPV3INFOHEADER with X1R5G5B5 masks, bottom-up rows
rows = b""
for y in range(S - 1, -1, -1):
    for x in range(S):
        r, g, b = img[y][x]
        rows += struct.pack("<H", ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3))
    rows += b"\0" * ((4 - (S * 2) % 4) % 4)
off = 14 + 56
hdr = struct.pack("<IiiHHIIiiII", 56, S, S, 1, 16, 3, len(rows), 3779, 3779, 0, 0)
hdr += struct.pack("<IIII", 0x7C00, 0x03E0, 0x001F, 0)
bmp = b"BM" + struct.pack("<IHHI", off + len(rows), 0, 0, off) + hdr + rows
open(sys.argv[1], "wb").write(bmp)

# Preview PNG via the sim's writer: pack into a 128x128 RGB565 buffer
buf = bytearray(128 * 128 * 2)
mv = memoryview(buf).cast("H")
for y in range(S):
    for x in range(S):
        r, g, b = img[y][x]
        mv[y * 128 + x] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "pinball")
os.makedirs(OUT, exist_ok=True)
thumbysim.write_png(os.path.join(OUT, "icon_preview.png"), buf, scale=3)
print("wrote", sys.argv[1], len(bmp), "bytes")
