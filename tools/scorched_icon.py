"""Usage: python scorched_icon.py ../1ScorchedThumb/icon.bmp

Draw the 38x38 Scorched Thumb menu icon as a 16-bit X1R5G5B5 BMP (same header layout as Labubu's)."""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumbysim

S = 38
img = [[(0, 0, 0)] * S for _ in range(S)]

def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def put(x, y, c):
    if 0 <= x < S and 0 <= y < S:
        img[y][x] = c

# Dusk sky
for y in range(S):
    for x in range(S):
        img[y][x] = lerp((25, 15, 60), (245, 130, 70), y / (S - 1))

# Hills
def ground(x):
    return int(27 + 4 * math.sin(x * 0.17 + 0.6) + 2 * math.sin(x * 0.45))
heights = [ground(x) for x in range(S)]
for x in range(4, 11):
    heights[x] = heights[7]
for x in range(27, 34):
    heights[x] = heights[30]
for x in range(S):
    for y in range(heights[x], S):
        f = (y - 20) / 18
        c = lerp((150, 105, 60), (55, 30, 20), max(0, min(1, f)))
        if y < heights[x] + 1:
            c = lerp(c, (255, 255, 230), 0.3)
        elif (x * 7 + y * 13) % 9 == 0:
            c = tuple(v * 4 // 5 for v in c)
        img[y][x] = c

def tank(cx, gy, col, ang):
    for x in range(cx - 3, cx + 4):
        put(x, gy - 1, (40, 40, 45)); put(x, gy - 2, (40, 40, 45))
        put(x, gy - 3, col); put(x, gy - 4, col)
    for x in (cx - 2, cx, cx + 2):
        put(x, gy - 1, (110, 110, 120))
    for x in range(cx - 1, cx + 2):
        put(x, gy - 5, col); put(x, gy - 6, col)
    a = math.radians(ang)
    for k in range(1, 6):
        put(int(round(cx + math.cos(a) * k)), int(round(gy - 5 - math.sin(a) * k)), (210, 210, 220))

# Shot arc from the red tank to the blue one
rx, bx = 7, 30
ry, by = heights[rx], heights[bx]
ex = bx - 8
ey = heights[ex] - 2
pts = []
for i in range(0, 101):
    t = i / 100
    x = rx + 4 + (ex - rx - 4) * t
    y = (ry - 9) + (ey - (ry - 9)) * t - 15 * math.sin(math.pi * t)
    pts.append((int(x), int(y)))
for i, (x, y) in enumerate(pts):
    if i < 90 and i % 3 == 0:
        put(x, y, (255, 90, 70))

tank(rx, ry, (255, 70, 60), 55)
tank(bx, by, (70, 160, 255), 125)

# Explosion right next to the blue tank
for y in range(ey - 6, ey + 7):
    for x in range(ex - 6, ex + 7):
        d = math.hypot(x - ex, y - ey)
        if d <= 4.5:
            put(x, y, (255, 170, 40) if d > 3 else ((255, 240, 120) if d > 1.5 else (255, 255, 255)))

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

# Preview PNG (8x) via the sim's writer: pack into a 128x128 RGB565 buffer
buf = bytearray(128 * 128 * 2)
mv = memoryview(buf).cast("H")
for y in range(S):
    for x in range(S):
        r, g, b = img[y][x]
        mv[y * 128 + x] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
thumbysim.write_png(os.path.join(OUT, "icon_preview.png"), buf, scale=3)
print("wrote", sys.argv[1], len(bmp), "bytes")
