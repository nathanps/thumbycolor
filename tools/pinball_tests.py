"""Drive Pinball headlessly on desktop Python: a scripted game that saves screenshots to
tools/out/pinball, then soak games with automatic flippers that catch crashes, stuck balls
and balls escaping the table.

Usage: python pinball_tests.py [all|scripted|soak] [soak_games] [frames_per_game]
"""
import io
import math
import os
import random
import sys
import tokenize
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import thumbysim  # noqa: E402

GAME = os.path.join(HERE, "..", "1Pinball", "main.py")
OUT = os.path.join(HERE, "out", "pinball")
which = sys.argv[1] if len(sys.argv) > 1 else "all"


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


def auto_flip(g, pressed, st):
    """Flip when the ball comes down onto a flipper, like a (fairly good) player would."""
    b = g["ball"]
    G = g["G"]
    if G.bstate != 1:
        return
    for f, btn in ((g["lflip"], "LB"), (g["rflip"], "RB")):
        rx = (b.x - f.px) * f.side
        ry = b.y - f.py
        hold = st.setdefault("hold_" + btn, 0)
        if hold > 0:
            st["hold_" + btn] = hold - 1
            pressed.add(btn)
        elif -2 < rx < 24 and -12 < ry < 8 and b.vy > -0.5:
            # Sometimes miss on purpose (soak games), so balls drain now and then
            rng = st.get("rng")
            if rng is not None and st.get("skip", 0) < G.frame:
                if rng.random() < st["miss"]:
                    st["skip"] = G.frame + 40
                    continue
                st["skip"] = G.frame + 1
            elif rng is not None:
                continue
            # Wait for the ball to roll partway along so shots go different ways
            if rx > st.get("aim", 10):
                st["hold_" + btn] = 9
                pressed.add(btn)


def deep_overlap(g):
    """True if the ball centre is well inside a wall (it should never be)."""
    b = g["ball"]
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


def scripted():
    """Title -> start -> charge and launch -> play with auto flippers until game over."""
    st = {"phase": "title", "t": 0, "seen": set(), "aim": 8, "rng": random.Random(7), "miss": 0.15}
    stats = {"overlap": 0, "max_speed": 0}

    def driver(frame, g):
        G = g.get("G")
        pressed = set()
        snaps = []
        st["t"] += 1
        ph = st["phase"]
        if ph == "title":
            if st["t"] == 50:
                snaps.append("01_title")
            if st["t"] == 55:
                pressed.add("A")
                st["phase"] = "play"
                st["t"] = 0
            return pressed, snaps
        if ph == "over":
            if st["t"] == 70:
                snaps.append("20_game_over")
            if st["t"] == 75:
                pressed.add("B")
            if st["t"] == 90:
                snaps.append("21_title_hiscore")
                st["phase"] = "done"
            return pressed, snaps
        if ph == "done":
            return pressed, snaps

        b = g["ball"]
        t = st["t"]
        if G.state == 2:
            st["phase"] = "over"
            st["t"] = 0
            return pressed, snaps
        if G.bstate == 0:
            # Charge for a bit, then let go
            st["serve_t"] = st.get("serve_t", 0) + 1
            if st["serve_t"] == 30 and "serve" not in st["seen"]:
                st["seen"].add("serve")
                snaps.append("02_serve")
            if 40 < st["serve_t"] < 40 + 20 + (frame % 25):
                pressed.add("DOWN")
            if st["serve_t"] == 55 and "charge" not in st["seen"]:
                st["seen"].add("charge")
                snaps.append("03_charging")
        else:
            st["serve_t"] = 0
        auto_flip(g, pressed, st)
        if frame % 500 == 0:
            st["aim"] = (st["aim"] + 7) % 18 + 2
        sp = math.hypot(b.vx, b.vy)
        stats["max_speed"] = max(stats["max_speed"], sp)
        if G.bstate == 1 and deep_overlap(g):
            stats["overlap"] += 1
        # Snapshots at interesting moments
        if G.bstate == 1:
            for name, cond in (("04_launch_lane", b.x > 114 and b.y < 150),
                               ("05_top_arch", b.y < 30 and b.x > 80),
                               ("06_lanes", b.y < 30 and b.x < 80),
                               ("07_bumpers", 40 < b.y < 95),
                               ("08_aliens", 105 < b.y < 140),
                               ("09_middle", 140 < b.y < 185),
                               ("10_flippers", b.y > 200 and (pressed & {"LB", "RB"}))):
                if cond and name not in st["seen"]:
                    st["seen"].add(name)
                    snaps.append(name)
        if G.msg_t == 60 and G.msg and len([s for s in st["seen"] if s.startswith("msg")]) < 6:
            k = "msg_" + G.msg.replace(" ", "_").replace("!", "")
            if k not in st["seen"]:
                st["seen"].add(k)
                snaps.append("11_" + k)
        if t == 3000 and "pause" not in st["seen"]:
            st["seen"].add("pause")
            pressed.add("MENU")
        if t == 3010:
            snaps.append("12_pause")
        if t == 3015:
            pressed.add("A")
        if t in (1200, 1203, 2400, 2402):
            pressed.add("UP")
        if t == 1204:
            snaps.append("13_nudge")
        return pressed, snaps

    thumbysim.SAVE.clear()
    snaps = thumbysim.run_game(GAME, driver, 40000, OUT)
    g = thumbysim._GAME
    G = g["G"]
    print("scripted: %d snapshots, phase %s, score %d, hi %s, bank clears %d, mult %d" %
          (len(snaps), st["phase"], G.score, thumbysim.SAVE.get("hi"), G.bank_clears, G.mult))
    print("  overlaps %d, max speed %.2f, unsticks %d, escapes %d" %
          (stats["overlap"], stats["max_speed"], G.unsticks, G.escapes))
    ok = st["phase"] == "done" and stats["overlap"] == 0 and G.escapes == 0
    return ok


def soak(seed, frames):
    """Games with auto flippers and random nudges; no drawing, to run fast."""
    st = {"aim": 6 + seed % 10, "rng": random.Random(seed), "miss": 0.12, "games": 0, "balls": 0, "ball_frames": [], "bf": 0,
          "scores": [], "overlap": 0, "events": {}, "stuck": 0, "last": None, "still": 0}

    def driver(frame, g):
        G = g["G"]
        pressed = set()
        if frame == 1:
            g["draw_play"] = lambda fb: None
            g["draw_table"] = lambda fb: None
            handle = g["handle_events"]

            def counting():
                for k in G.events:
                    st["events"][k] = st["events"].get(k, 0) + 1
                handle()
            g["handle_events"] = counting
        if G.state == 0:
            if frame % 10 == 0:
                pressed.add("A")
            return pressed, []
        if G.state == 2:
            if G.timer == 1:
                st["games"] += 1
                st["scores"].append(G.score)
            if G.timer > 62 and frame % 4 == 0:
                pressed.add("A")
            return pressed, []
        b = g["ball"]
        if G.bstate == 0:
            if frame % 60 < 30:
                pressed.add("DOWN")
            st["bf"] = 0
        elif G.bstate == 1:
            st["bf"] += 1
            auto_flip(g, pressed, st)
            if frame % 777 == 0:
                st["aim"] = (st["aim"] + 5) % 18 + 2
            if frame % 613 == 0:
                pressed.add("UP")
            if deep_overlap(g):
                st["overlap"] += 1
            if not (0 <= b.x <= 128) or b.y < 0:
                raise AssertionError("ball escaped at %.1f, %.1f" % (b.x, b.y))
            # Stuck: hasn't moved 3 pixels in 6 seconds while not cradled
            p = (int(b.x), int(b.y))
            if st["last"] and abs(p[0] - st["last"][0]) < 3 and abs(p[1] - st["last"][1]) < 3:
                st["still"] += 1
                if st["still"] == 360 and not (b.y > 200 and pressed & {"LB", "RB"}):
                    st["stuck"] += 1
                    print("  stuck ball at", p, "seed", seed, "frame", frame)
            else:
                st["still"] = 0
                st["last"] = p
        elif G.bstate == 2 and st["bf"]:
            st["ball_frames"].append(st["bf"])
            st["bf"] = 0
        return pressed, []

    thumbysim.SAVE.clear()
    err = None
    try:
        thumbysim.run_game(GAME, driver, frames, os.path.join(OUT, "soak"), seed=seed)
    except Exception:
        err = traceback.format_exc()
    G = thumbysim._GAME["G"]
    st["unsticks"] = G.unsticks
    st["escapes"] = G.escapes
    st["bank_clears"] = G.bank_clears
    return st, err


if __name__ == "__main__":
    ok = small_ints()
    if which in ("all", "scripted"):
        ok = scripted() and ok
    if which in ("all", "soak"):
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
        frames = int(sys.argv[3]) if len(sys.argv) > 3 else 15000
        bf = []
        for seed in range(1, n + 1):
            st, err = soak(seed, frames)
            bf += st["ball_frames"]
            print("soak seed %d: games %d, scores %s, overlaps %d, stuck %d, unsticks %d, escapes %d, "
                  "bank clears %d" % (seed, st["games"], st["scores"], st["overlap"], st["stuck"],
                                      st["unsticks"], st["escapes"], st["bank_clears"]))
            print("  hits:", sorted(st["events"].items()))
            if err:
                print(err)
                ok = False
            if st["overlap"] or st["stuck"] or st["escapes"]:
                ok = False
        if bf:
            print("average ball life %.1f s over %d balls" % (sum(bf) / len(bf) / 60, len(bf)))
    print("OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)
