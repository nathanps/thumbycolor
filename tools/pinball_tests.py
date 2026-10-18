"""Drive Pinball headlessly on desktop Python.

  small ints  - no integer literal of 2**30 or more (the device has no big integers)
  tables      - full-height picture of every table (tools/out/pinball/tables)
  features    - puts the ball straight into each ramp, hole, kickback, gate and multiball
  scripted    - a game on each table with automatic flippers, saving screenshots
  soak        - many games per table, failing on crashes, stuck balls, balls escaping
                the table or sinking into walls

Usage: python pinball_tests.py [all|tables|features|scripted|soak] [soak_seeds] [frames]
"""
import io
import os
import random
import struct
import sys
import tokenize
import traceback
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import thumbysim  # noqa: E402

GAME = os.path.join(HERE, "..", "1Pinball", "main.py")
OUT = os.path.join(HERE, "out", "pinball")
which = sys.argv[1] if len(sys.argv) > 1 else "all"
N_TABLES = 5


def small_ints():
    """The device has no big integers: a literal of 2**30 or more is a syntax error there,
    even outside viper. Desktop Python and mpy-cross accept them, so check here."""
    ok = True
    with open(GAME) as f:
        src = f.read()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.NUMBER:
            try:
                v = int(tok.string, 0)
            except ValueError:
                continue        # A float
            if v >= 1 << 30:
                print("line %d: %s is too big for the device (2**30 or more)" % (tok.start[0], tok.string))
                ok = False
    print("small ints:", "OK" if ok else "FAILED")
    return ok


def play_balls(g):
    return [b for b in g["balls"] if b.mode == 0]


def auto_flip(g, pressed, st):
    """Flip when a ball comes down onto a flipper, like a (fairly good) player would."""
    G = g["G"]
    for f, btn in ((g["lflip"], "LB"), (g["rflip"], "RB")):
        hold = st.get("hold_" + btn, 0)
        if hold > 0:
            st["hold_" + btn] = hold - 1
            pressed.add(btn)
            continue
        for b in play_balls(g):
            rx = (b.x - f.px) * f.side
            ry = b.y - f.py
            if -2 < rx < 24 and -12 < ry < 8 and b.vy > -0.5:
                # Sometimes miss on purpose, so balls drain now and then
                rng = st.get("rng")
                key = "skip_" + btn
                if rng is not None and st.get(key, 0) < G.frame:
                    if rng.random() < st["miss"]:
                        st[key] = G.frame + 40
                        break
                    st[key] = G.frame + 1
                elif rng is not None:
                    break
                # Wait for the ball to roll partway along so shots go different ways
                if rx > st.get("aim", 10):
                    st["hold_" + btn] = 9
                    pressed.add(btn)
                    break


def deep_overlap(g, b):
    """True if the ball centre is well inside a wall (it should never be)."""
    table = g["table"]
    kinds = g["kinds"]
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dx * dx + dy * dy > 4:
                continue
            x = int(b.x) + dx
            y = int(b.y) + dy
            if 0 <= x < 128 and 0 <= y < g["TH"]:
                if kinds[table[y * 128 + x]]:
                    px = x + 0.5 - b.x
                    py = y + 0.5 - b.y
                    if px * px + py * py < 1.8 * 1.8:
                        return True
    return False


def write_table_png(path, g, scale=3):
    tbl, pal = g["table"], g["palette"]
    w, h = 128, g["TH"]
    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            c = pal[tbl[y * w + x]]
            row += bytes((((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63,
                          (c & 31) * 255 // 31)) * scale
        for _ in range(scale):
            rows.append(bytes(row))

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 2, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(b"".join(rows), 6)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)


def tables():
    out = os.path.join(OUT, "tables")
    os.makedirs(out, exist_ok=True)
    ok = [True]

    def driver(frame, g):
        if frame == 1:
            for i in range(len(g["TABLES"])):
                g["build_table"](i)
                g["reset_table"]()
                g["update_lamps"]()
                write_table_png(os.path.join(out, "table_%d.png" % i), g)
                T = g["T"]
                if T.next_lamp > 64 or T.next_solid > 256:
                    print("  palette full on table", i)
                    ok[0] = False
        return set(), []
    thumbysim.SAVE.clear()
    thumbysim.run_game(GAME, driver, 2, OUT)
    print("tables: pictures in", out)
    return ok[0]


def features():
    """Put the ball into each feature directly and check it does its job."""
    results = []
    st = {"queue": [], "job": None, "overlap": 0}
    for ti in range(N_TABLES):
        st["queue"].append(("start", ti))
        st["queue"] += [("ramp", ti, k) for k in range(2)]
        st["queue"] += [("hole", ti, k) for k in range(2)]
        st["queue"] += [("kick", ti), ("door", ti), ("multi", ti)]

    def new_job(g):
        G = g["G"]
        T = g["T"]
        balls = g["balls"]
        job = st["queue"].pop(0)
        kind = job[0]
        st["job"] = job
        st["t"] = 0
        st["data"] = {}
        if kind == "start":
            G.table_i = job[1]
            g["build_table"](job[1])
            g["start_game"]()
            st["job"] = None
            return
        # A fresh single ball for each check
        balls[:] = []
        G.multi = False
        G.spawn = 0
        G.save_t = 0
        G.stats = {}
        b = g["Ball"](60.0, 150.0, 0)
        b.in_lane = False
        balls.append(b)
        skip = False
        if kind == "ramp":
            if job[2] < len(T.ramps):
                r = T.ramps[job[2]]
                b.x, b.y = float(r.pts[0][0]), r.pts[0][1] + 20.0
                b.vx, b.vy = 0.0, -4.5
            else:
                skip = True
        elif kind == "hole":
            if job[2] < len(T.holes):
                h = T.holes[job[2]]
                if T.door:
                    T.door.open = True
                b.x, b.y = h.x + 0.3, h.y - 4.5
                b.vx, b.vy = 0.0, 0.8
            else:
                skip = True
        elif kind == "kick":
            if T.kick_lamp >= 0:
                T.kick_lit = True
                b.x, b.y = 7.0, 190.0
                b.vx, b.vy = 0.0, 1.0
            else:
                skip = True
        elif kind == "door":
            if T.door:
                T.door.open = False
                T.door.hits = 0
            else:
                skip = True
        elif kind == "multi":
            if T.holes:
                h = T.holes[0]
                b.mode = 2
                b.hole = h
                b.x, b.y = float(h.x), float(h.y)
                g["start_multiball"](b, h.name)
            else:
                skip = True
        if skip:
            st["job"] = None
            balls[:] = []
            g["serve"]()

    def finish(name, good, why):
        results.append((name, good, why))
        st["job"] = None

    def driver(frame, g):
        G = g["G"]
        T = g["T"]
        balls = g["balls"]
        pressed = set()
        snaps = []
        if frame == 1:
            st["draw"] = g["draw_play"]
        g["draw_play"] = lambda fb: None
        while st["job"] is None:
            if not st["queue"]:
                raise thumbysim.StopSim()
            new_job(g)
        T = g["T"]          # A new table may have just been built
        job = st["job"]
        st["t"] += 1
        t = st["t"]
        d = st["data"]
        kind = job[0]
        ti = G.table_i
        name = "%s %s%s" % (g["TABLES"][ti]["name"], kind, " %d" % job[2] if len(job) > 2 else "")
        for b in balls:
            if b.mode == 0 and deep_overlap(g, b):
                st["overlap"] += 1
        b = balls[0] if balls else None
        if kind == "ramp":
            if b and b.mode == 3 and "ride" not in d:
                d["ride"] = t
            if b and "ride" in d and t == d["ride"] + 12:
                snaps.append("feat_%d_ramp%d_riding" % (ti, job[2]))
            if b and "ride" in d and b.mode == 0:
                d.setdefault("out", t)
                if t > d["out"] + 30:
                    finish(name, True, "rode it, came out at %.0f,%.0f" % (b.x, b.y))
            elif t > 200:
                finish(name, False, "never got onto the ramp")
        elif kind == "hole":
            h = T.holes[job[2]]
            if b and b.mode == 2 and "caught" not in d:
                d["caught"] = t
                snaps.append("feat_%d_hole%d" % (ti, job[2]))
            if "caught" in d and b and b.mode == 0 and abs(b.x - h.x) + abs(b.y - h.y) > 12:
                finish(name, True, "caught and kicked out")
            elif t > 240:
                finish(name, False, "not caught" if "caught" not in d else "never left")
        elif kind == "kick":
            if G.stats.get("kick") and b and b.y < 150:
                finish(name, True, "kicked back up to y %.0f" % b.y)
            elif t > 200:
                finish(name, False, "no kick" if not G.stats.get("kick") else "kick too weak")
        elif kind == "door":
            if t % 50 == 1 and b and not T.door.open:
                b.mode = 0
                b.x, b.y = 57.0, 82.0
                b.vx, b.vy = 0.0, -4.0
            if T.door.open:
                d.setdefault("open", t)
                if t == d["open"] + 2:
                    snaps.append("feat_%d_door_open" % ti)
                    finish(name, True, "opened after %d hits" % G.stats.get("door", 0))
            elif t > 400:
                finish(name, False, "only %d hits" % G.stats.get("door", 0))
        elif kind == "multi":
            n = len(play_balls(g))
            d["max"] = max(d.get("max", 0), n)
            auto_flip(g, pressed, st)
            if t == 220:
                g["draw_play"] = st["draw"]
                snaps.append("feat_%d_multiball" % ti)
            want = g["TABLES"][ti]["mb"]
            if t > 300 and d["max"] >= want:
                finish(name, True, "%d balls at once" % d["max"])
            elif t > 1200:
                finish(name, False, "only %d balls at once" % d["max"])
        if snaps:
            g["draw_play"] = st["draw"]
        return pressed, snaps

    thumbysim.SAVE.clear()
    ok = True
    try:
        thumbysim.run_game(GAME, driver, 60000, OUT)
    except Exception:
        traceback.print_exc()
        ok = False
    for name, good, why in results:
        print("  %-26s %s %s" % (name, "ok  " if good else "FAIL", why))
        ok = ok and good
    if st["overlap"]:
        print("  balls sank into walls %d times" % st["overlap"])
        ok = False
    print("features:", "OK" if ok else "FAILED", "(%d checks)" % len(results))
    return ok


def scripted(ti, frames=9000):
    """A game on table ti, picked from the title screen, with screenshots of new things."""
    st = {"phase": "title", "t": 0, "seen": set(), "aim": 8, "rng": random.Random(7 + ti), "miss": 0.15}
    stats = {"overlap": 0}
    tag = "t%d_" % ti

    def driver(frame, g):
        G = g["G"]
        pressed = set()
        snaps = []
        st["t"] += 1
        t = st["t"]
        if st["phase"] == "title":
            if t <= ti * 3 and t % 3 == 0:
                pressed.add("RIGHT")
            if t == ti * 3 + 40:
                snaps.append(tag + "01_title")
            if t == ti * 3 + 45:
                pressed.add("A")
                st["phase"] = "play"
            return pressed, snaps
        if st["phase"] == "over":
            if t == st["over_t"] + 70:
                snaps.append(tag + "20_game_over")
            return pressed, snaps
        if G.state == 2:
            st["phase"] = "over"
            st["over_t"] = t
            return pressed, snaps
        balls = g["balls"]
        if any(b.mode == 1 for b in balls):
            st["serve_t"] = st.get("serve_t", 0) + 1
            if st["serve_t"] == 30 and "serve" not in st["seen"]:
                st["seen"].add("serve")
                snaps.append(tag + "02_serve")
            if 40 < st["serve_t"] < 60 + (frame % 25):
                pressed.add("DOWN")
        else:
            st["serve_t"] = 0
        auto_flip(g, pressed, st)
        if frame % 500 == 0:
            st["aim"] = (st["aim"] + 7) % 18 + 2
        for b in balls:
            if b.mode == 0 and deep_overlap(g, b):
                stats["overlap"] += 1
        # A screenshot the first time each kind of thing happens
        for k in sorted(G.stats):
            if k not in st["seen"]:
                st["seen"].add(k)
                st["pending"] = tag + "05_" + k
                st["pending_t"] = t + 4
        if st.get("pending") and t >= st["pending_t"]:
            snaps.append(st.pop("pending"))
        live = play_balls(g)
        if live and "falling" not in st["seen"] and live[0].vy > 2.5 and 90 < live[0].y < 150:
            st["seen"].add("falling")
            snaps.append(tag + "03_falling_camera")
        if len(live) > 1 and "multi_shot" not in st["seen"]:
            st["seen"].add("multi_shot")
            st["multi_t"] = t + 90
        if st.get("multi_t") == t:
            snaps.append(tag + "04_multiball")
        if ti == 0 and t == 3000:
            pressed.add("MENU")
        if ti == 0 and t == 3010:
            snaps.append(tag + "12_pause")
        if ti == 0 and t == 3015:
            pressed.add("A")
        return pressed, snaps

    thumbysim.SAVE.clear()
    thumbysim.run_game(GAME, driver, frames, OUT)
    g = thumbysim._GAME
    G = g["G"]
    print("scripted %-13s score %7d, %s, overlaps %d, unsticks %d, escapes %d, stats %s" %
          (g["TABLES"][ti]["name"], G.score, st["phase"], stats["overlap"], G.unsticks, G.escapes,
           dict(sorted(G.stats.items()))))
    return stats["overlap"] == 0 and G.escapes == 0 and G.unsticks == 0


def soak(ti, seed, frames):
    """Games with auto flippers and random nudges; no drawing, to run fast."""
    st = {"aim": 6 + seed % 10, "rng": random.Random(seed * 10 + ti), "miss": 0.12, "games": 0,
          "scores": [], "overlap": 0, "stuck": 0, "stats": {}, "bf": 0, "ball_frames": [],
          "max_balls": 0}

    def driver(frame, g):
        G = g["G"]
        pressed = set()
        if frame == 1:
            g["draw_play"] = lambda fb: None
            g["draw_table"] = lambda fb: None
            G.table_i = ti
            g["build_table"](ti)
            g["reset_table"]()
        if G.state == 0:
            st["u"] = 0
            if frame % 10 == 0:
                pressed.add("A")
            return pressed, []
        if G.state == 2:
            st["u"] = 0
            if G.timer == 1:
                st["games"] += 1
                st["scores"].append(G.score)
                for k, v in G.stats.items():
                    st["stats"][k] = st["stats"].get(k, 0) + v
            if G.timer > 62 and frame % 4 == 0:
                pressed.add("A")
            return pressed, []
        balls = g["balls"]
        if any(b.mode == 1 for b in balls) and frame % 60 < 30:
            pressed.add("DOWN")
        live = play_balls(g)
        st["max_balls"] = max(st["max_balls"], len(live))
        if G.bstate == 1 and not any(b.mode == 1 for b in balls):
            st["bf"] += 1
        elif G.bstate == 2 and st["bf"]:
            st["ball_frames"].append(st["bf"])
            st["bf"] = 0
        auto_flip(g, pressed, st)
        if frame % 777 == 0:
            st["aim"] = (st["aim"] + 5) % 18 + 2
        if frame % 613 == 0:
            pressed.add("UP")
        for b in live:
            if deep_overlap(g, b):
                st["overlap"] += 1
            if not (0 <= b.x <= 128) or b.y < 0:
                raise AssertionError("ball escaped at %.1f, %.1f" % (b.x, b.y))
            # Stuck: hasn't moved 3 pixels in 6 seconds while not cradled
            last = getattr(b, "_last", None)
            p = (int(b.x), int(b.y))
            if last and abs(p[0] - last[0]) < 3 and abs(p[1] - last[1]) < 3:
                b._still = getattr(b, "_still", 0) + 1
                if b._still == 360 and not (b.y > 200 and pressed & {"LB", "RB"}):
                    st["stuck"] += 1
                    print("  stuck ball at", p, "table", ti, "seed", seed, "frame", frame)
            else:
                b._still = 0
                b._last = p
        # The game shoves a ball that sits still for 4 seconds; each one is a trap to fix
        if G.unsticks != st.get("u", 0):
            st["u"] = G.unsticks
            st["unstuck"] = st.get("unstuck", 0) + 1
            b = live[0] if live else None
            print("  game unstuck a ball near", (int(b.x), int(b.y)) if b else "?",
                  "table", ti, "seed", seed)
        return pressed, []

    thumbysim.SAVE.clear()
    err = None
    try:
        thumbysim.run_game(GAME, driver, frames, os.path.join(OUT, "soak"), seed=seed)
    except Exception:
        err = traceback.format_exc()
    G = thumbysim._GAME["G"]
    if G.state != 2:
        for k, v in G.stats.items():
            st["stats"][k] = st["stats"].get(k, 0) + v
    st["unsticks"] = st.get("unstuck", 0)
    st["escapes"] = G.escapes
    return st, err


if __name__ == "__main__":
    ok = small_ints()
    if which in ("all", "tables"):
        ok = tables() and ok
    if which in ("all", "features"):
        ok = features() and ok
    if which in ("all", "scripted"):
        for ti in range(N_TABLES):
            ok = scripted(ti) and ok
    if which in ("all", "soak"):
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        frames = int(sys.argv[3]) if len(sys.argv) > 3 else 15000
        for ti in range(N_TABLES):
            bf = []
            total = {}
            mb = 0
            for seed in range(1, n + 1):
                st, err = soak(ti, seed, frames)
                bf += st["ball_frames"]
                mb = max(mb, st["max_balls"])
                for k, v in st["stats"].items():
                    total[k] = total.get(k, 0) + v
                if err:
                    print(err)
                    ok = False
                if st["overlap"] or st["stuck"] or st["escapes"] or st["unsticks"]:
                    print("  table %d seed %d: overlaps %d, stuck %d, escapes %d, unsticks %d" %
                          (ti, seed, st["overlap"], st["stuck"], st["escapes"], st["unsticks"]))
                    ok = False
            life = sum(bf) / len(bf) / 60 if bf else 0
            print("soak table %d: %d balls drained, average ball %.1f s, most balls at once %d, hits %s" %
                  (ti, len(bf), life, mb, dict(sorted(total.items()))))
    print("OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)
