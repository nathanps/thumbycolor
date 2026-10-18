"""Check every Target Practice level: each target can be hit by some shot and none is buried.
Also saves a picture of each whole level to tools/out/levels.

Usage: python scorched_levels.py
"""
import os
import struct
import sys
import zlib

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import thumbysim  # noqa: E402
from scorched_tests import practice_aim  # noqa: E402

GAME = os.path.join(TOOLS, "..", "1ScorchedThumb", "main.py")
OUT = os.path.join(TOOLS, "out", "levels")
os.makedirs(OUT, exist_ok=True)
results = []


def world_png(path, g, G):
    W, H = 256, 128
    terrain, pal = g["terrain"], memoryview(g["palette"]).cast("H")
    img = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            img[y][x] = pal[(terrain[y * W + x] << 7) + y]
    for t in G.targets:
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if dx * dx + dy * dy <= 9 and 0 <= t.x + dx < W and 0 <= t.cy + dy < H:
                    img[t.cy + dy][t.x + dx] = 0xF800 if t.kind == 0 else 0xFFFF
    p = G.players[0]
    for dy in range(-5, 0):
        for dx in range(-3, 4):
            img[p.y + dy][p.x + dx] = 0x001F
    rows = []
    for y in range(H):
        row = bytearray([0])
        for x in range(W):
            c = img[y][x]
            r = ((c >> 11) & 0x1F) * 255 // 31
            gg = ((c >> 5) & 0x3F) * 255 // 63
            b = (c & 0x1F) * 255 // 31
            row += bytes((r, gg, b)) * 2
        rows.append(bytes(row))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W * 2, H * 2, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)


def driver(frame, g):
    G = g.get("G")
    if G is None or frame < 3:
        return set(), []
    for lv in range(len(g["TP_LEVELS"])):
        g["start_practice"](lv)
        p = G.players[0]
        world_png(os.path.join(OUT, "level_%02d.png" % (lv + 1)), g, G)
        bad = []
        for t in G.targets:
            inside = 0 <= t.cy < 128 and g["terrain"][t.cy * 256 + t.x] != 0
            ang, pw = practice_aim(g, G, p, t)
            # Re-score the chosen shot: distance from target at closest approach / landing
            import math
            a = math.radians(ang)
            sp = pw * g["V_MAX"] / 1000
            x, y = p.barrel_tip(ang, 7)
            vx, vy = math.cos(a) * sp, -math.sin(a) * sp
            ax = G.wind * g["WIND_K"] / 4
            ay = g["GRAVITY"] / 4
            best = 1e9
            for _ in range(2400):
                vx += ax
                vy += ay
                x += vx / 4
                y += vy / 4
                d = ((x - t.x) ** 2 + (y - t.cy) ** 2) ** 0.5
                best = min(best, d)
                if x < 0 or x >= 256:
                    break
                iy = int(y)
                if y >= 0 and (iy >= 126 or g["terrain"][iy * 256 + int(x)]):
                    break
            limit = 4 if t.kind == 0 else 8
            if inside or best > limit:
                bad.append((t.kind, t.x, t.cy, "inside" if inside else "miss %.1f" % best))
        results.append((lv + 1, len(G.targets), G.wind, bad))
    raise thumbysim.StopSim()


thumbysim.SAVE.clear()
thumbysim.run_game(GAME, driver, 10, OUT)
for lv, n, wind, bad in results:
    print("level %2d: %d targets wind %3d  %s" % (lv, n, wind, "OK" if not bad else bad))
