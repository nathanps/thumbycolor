"""Drive Scorched Thumb headlessly on desktop Python: a scripted human game that saves
screenshots to tools/out, then CPU-only soak games that catch crashes and stuck states.

Usage: python scorched_tests.py [all|practice|edge|scripted|soak] [soak_games] [frames_per_game]
"""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import thumbysim  # noqa: E402

GAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ScorchedThumb", "main.py")
OUT = os.path.join(HERE, "out")
which = sys.argv[1] if len(sys.argv) > 1 else "all"


def scripted():
    """Title -> setup -> human vs CPU, with snapshots at interesting moments."""
    log = []
    st = {"phase": "title", "t": 0, "seen": set(), "shots": 0, "last_state": None}

    def driver(frame, g):
        G = g.get("G")
        pressed = set()
        snaps = []
        st["t"] += 1
        ph = st["phase"]
        if ph == "title":
            if st["t"] == 40:
                snaps.append("01_title")
            if st["t"] == 45:
                pressed.add("A")
                st["phase"] = "setup"
                st["t"] = 0
        elif ph == "setup":
            # Make it a 3 player game: P1 human, P2 CPU medium, P3 human
            seq = {3: "RIGHT", 6: "DOWN", 9: "DOWN", 12: "DOWN", 15: "DOWN", 17: "DOWN",
                   19: "LEFT", 21: "LEFT", 24: "A"}
            if st["t"] in seq:
                pressed.add(seq[st["t"]])
            if st["t"] == 27:
                snaps.append("02_setup")
            if st["t"] == 30:
                pressed.add("DOWN")
            if st["t"] == 33:
                pressed.add("A")
                st["phase"] = "play"
                st["t"] = 0
        elif ph == "hof":
            # Back on the title: open the hall of fame
            if st["t"] == 20:
                snaps.append("14_title_menu")
            if st["t"] in (24, 27):
                pressed.add("DOWN")      # Past Target Practice to Hall of Fame
            if st["t"] == 30:
                pressed.add("A")
            if st["t"] == 40:
                snaps.append("15_hall_of_fame")
                st["phase"] = "done"
        elif ph == "play":
            s = G.state
            if s != st["last_state"]:
                log.append((frame, s, G.turn))
                st["last_state"] = s
                st["state_t"] = 0
            st["state_t"] = st.get("state_t", 0) + 1
            name = None
            p = G.players[G.turn] if G.players else None
            if s == 2 and st["state_t"] == 20 and "turn" not in st["seen"]:
                st["seen"].add("turn"); name = "03_turn_banner"
            if s == 3 and p and not p.is_cpu():
                # Exercise the controls a bit, then aim with the CPU's solver and fire
                t = st["state_t"]
                if t < 25:
                    pressed.add("UP")
                elif t < 35:
                    pressed.add("LEFT")
                elif t == 36:
                    if "aim" not in st["seen"]:
                        st["seen"].add("aim"); name = "04_aim"
                elif t == 40:
                    gen = g["cpu_plan"](p)
                    for _ in gen:
                        pass
                    p.angle = p.ai_angle
                    p.power = p.ai_power
                    st["shots"] += 1
                    # Try each special weapon in turn
                    p.wsel = [1, 3, 5, 4, 2, 6, 7, 8, 0][st["shots"] % 9]
                    if p.inv[p.wsel] == 0:
                        p.wsel = 0
                elif t == 42:
                    pressed.add("A")
            if s == 3 and p and p.is_cpu() and st["state_t"] == 10 and "cpu" not in st["seen"]:
                st["seen"].add("cpu"); name = "05_cpu_thinking"
            if s == 4 and st["state_t"] == 40 and len(st["seen"]) < 12:
                k = "fly%d" % st["shots"]
                if k not in st["seen"]:
                    st["seen"].add(k); name = "06_fly_%d" % st["shots"]
            if s == 5 and st["state_t"] == 6:
                k = "boom%d" % frame
                if len([x for x in st["seen"] if x.startswith("boom")]) < 4:
                    st["seen"].add(k); name = "07_boom_%d" % frame
            if s == 6 and st["state_t"] == 4:
                k = [x for x in st["seen"] if x.startswith("settle")]
                if len(k) < 3:
                    st["seen"].add("settle%d" % frame); name = "08_settle_%d" % frame
            if s == 7:
                if st["state_t"] == 40:
                    name = "09_round_end_%d" % G.round_no
                if st["state_t"] == 45:
                    pressed.add("A")
            if s == 8:
                if st["state_t"] == 40:
                    name = "10_game_end"
                if st["state_t"] == 45:
                    pressed.add("A")
                    st["phase"] = "hof"
                    st["t"] = 0
            if s == 9:
                # Shop: buy a missile and a big bomb, then leave
                t = st["state_t"] % 40
                if t == 12:
                    pressed.add("A")
                elif t == 16:
                    pressed.add("DOWN")
                elif t == 20:
                    pressed.add("A")
                elif t == 24 and "shop" not in st["seen"]:
                    st["seen"].add("shop"); name = "13_shop"
                elif t == 30:
                    pressed.add("B")
            if any(q.chute for q in G.players) and "chute" not in st["seen"]:
                st["seen"].add("chute"); name = "11_parachute"
            if len(G.shots) >= 4 and "multi" not in st["seen"] and st["state_t"] > 3:
                st["seen"].add("multi"); name = "12_many_shots"
            if name:
                snaps.append(name)
        return pressed, snaps

    thumbysim.SAVE.clear()
    snaps = thumbysim.run_game(GAME, driver, 30000, OUT)
    print("scripted: %d snapshots, phase=%s, human shots=%d" % (len(snaps), st["phase"], st["shots"]))
    print("state log (first 40):", log[:40])
    return snaps


def soak(seed, frames):
    """All-CPU game, pressing A at the end screens. Catches crashes and stuck states."""
    st = {"last": None, "since": 0, "rounds": 0, "games": 0, "turns": 0, "max_stuck": 0, "title_t": 0}

    def driver(frame, g):
        G = g.get("G")
        pressed = set()
        if G is None:
            return pressed, []
        s = G.state
        if s != st["last"]:
            if s == 3:
                st["turns"] += 1
            if s == 7:
                st["rounds"] += 1
            if s == 8:
                st["games"] += 1
            st["last"] = s
            st["since"] = 0
        st["since"] += 1
        st["max_stuck"] = max(st["max_stuck"], st["since"]) if s not in (0, 1) else st["max_stuck"]
        if st["since"] > 3000 and s not in (0, 1):
            raise RuntimeError("stuck in state %d for 3000 frames" % s)
        if s == 0 and st["since"] % 10 == 5:
            pressed.add("A")
        if s == 1:
            # Setup: four CPUs (hard, easy, medium, hard) then start
            seq = {3: "RIGHT", 6: "DOWN", 8: "DOWN", 10: "DOWN"}
            t = st["since"]
            if t in seq:
                pressed.add(seq[t])
            if t == 12:
                pressed.add("LEFT")      # P1 HUMAN -> CPU:H
            if t == 14:
                pressed.add("UP")
            if t == 16:
                pressed.add("UP")
            if t == 18:
                pressed.add("UP")
            if t == 20:
                pressed.add("UP")        # wraps to START
            if t == 22:
                pressed.add("A")
        if s in (7, 8) and st["since"] % 40 == 35:
            pressed.add("A")
        return pressed, []

    thumbysim.SAVE.clear()
    thumbysim.SAVE.update({"n": 4, "r": 2, "ty1": 1, "ty2": 2, "ty3": 3})
    try:
        thumbysim.run_game(GAME, driver, frames, os.path.join(OUT, "soak"), seed=seed)
        ok = True
    except Exception:
        traceback.print_exc()
        ok = False
    print("soak seed=%d ok=%s turns=%d rounds=%d games=%d longest_state=%d" %
          (seed, ok, st["turns"], st["rounds"], st["games"], st["max_stuck"]))
    return ok


def edge_shot():
    """A tank at the very edge firing outward with no power and no wind used to hang mid-flight."""
    st = {"since": 0, "last": None, "fired": False, "fly_frames": 0, "left_fly": False}

    def driver(frame, g):
        G = g.get("G")
        pressed = set()
        if G is None:
            return pressed, []
        s = G.state
        if s != st["last"]:
            if st["last"] == 4 and st["fired"]:
                st["left_fly"] = True
            st["last"] = s
            st["since"] = 0
        st["since"] += 1
        t = st["since"]
        if s == 0 and t == 5:
            pressed.add("A")
        if s == 1 and t == 3:
            pressed.add("UP")
        if s == 1 and t == 6:
            pressed.add("A")
        if s == 9 and t == 15:
            pressed.add("B")
        if s == 3 and not st["fired"] and t == 5 and not G.players[G.turn].is_cpu():
            p = G.players[G.turn]
            p.x = 4
            p.y = g["ground_below"](4, 0)
            p.angle = 180
            p.power = 0
            G.wind = 0
            pressed.add("A")
            st["fired"] = True
        if s == 4 and st["fired"]:
            st["fly_frames"] += 1
        return pressed, []

    thumbysim.SAVE.clear()
    thumbysim.SAVE.update({"n": 2, "ty1": 2})
    thumbysim.run_game(GAME, driver, 1500, os.path.join(OUT, "edge"))
    ok = st["fired"] and st["left_fly"]
    print("edge shot: fired=%s left_flight=%s frames_in_flight=%d ok=%s" %
          (st["fired"], st["left_fly"], st["fly_frames"], ok))
    return ok


def practice_aim(g, G, p, t):
    """Search angle and power so a shot passes through (balloon) or lands on (ground) target t."""
    import math
    W, H, terrain = g["W"], g["H"], g["terrain"]
    ax = G.wind * g["WIND_K"] / 4
    ay = g["GRAVITY"] / 4
    tx, ty = t.x, t.cy

    def score(ang, pw):
        a = math.radians(ang)
        sp = pw * g["V_MAX"] / 1000
        x, y = p.barrel_tip(ang, 7)
        vx, vy = math.cos(a) * sp, -math.sin(a) * sp
        best = 1e9
        for _ in range(2400):
            vx += ax
            vy += ay
            x += vx / 4
            y += vy / 4
            if t.kind == 0:
                d = (x - tx) ** 2 + (y - ty) ** 2
                if d < best:
                    best = d
            if x < 0 or x >= W:
                return best if t.kind == 0 else 1e9
            iy = int(y)
            if y >= 0 and (iy >= 126 or terrain[iy * W + int(x)]):
                if t.kind == 1:
                    return (x - tx) ** 2 + (y - ty) ** 2
                return best
        return best

    best = (1e18, 45, 500)
    for ang in range(15, 88, 3):
        for pw in range(100, 1001, 15):
            sc = score(ang, pw)
            if sc < best[0]:
                best = (sc, ang, pw)
    _, a0, p0 = best
    for ang in range(a0 - 3, a0 + 4):
        for pw in range(p0 - 15, p0 + 16, 3):
            sc = score(ang, pw)
            if sc < best[0]:
                best = (sc, ang, pw)
    return best[1], best[2]


def practice():
    """Play the first few target practice levels with an aim solver."""
    st = {"phase": "title", "t": 0, "seen": set(), "levels_done": 0, "last": None, "since": 0}

    def driver(frame, g):
        G = g.get("G")
        pressed = set()
        snaps = []
        if G is None:
            return pressed, snaps
        s = G.state
        if s != st["last"]:
            st["last"] = s
            st["since"] = 0
        st["since"] += 1
        t = st["since"]
        if s == 0:
            if t == 10:
                pressed.add("DOWN")
            if t == 15:
                snaps.append("16_title_practice")
            if t == 20:
                pressed.add("A")
        elif s == 11:
            if t == 15 and "sel" not in st["seen"]:
                st["seen"].add("sel")
                snaps.append("17_level_select")
            if t == 20:
                if st["levels_done"] >= 4:
                    snaps.append("21_level_select_after")
                    st["phase"] = "done"
                else:
                    pressed.add("A")
        elif s == 2:
            if t == 20 and "banner" not in st["seen"]:
                st["seen"].add("banner")
                snaps.append("18_practice_banner")
        elif s == 3:
            if t == 6:
                p = G.players[0]
                live = [q for q in G.targets if q.alive]
                live.sort(key=lambda q: abs(q.x - p.x))
                p.angle, p.power = practice_aim(g, G, p, live[0])
                if "aim" not in st["seen"]:
                    st["seen"].add("aim")
                    snaps.append("19_practice_aim")
            if t == 8:
                pressed.add("A")
        elif s == 12:
            if t == 40:
                snaps.append("20_level_done_%d" % (G.tp_level + 1))
            if t == 45:
                st["levels_done"] += 1
                pressed.add("A" if st["levels_done"] < 4 else "B")
        return pressed, snaps

    thumbysim.SAVE.clear()
    thumbysim.run_game(GAME, driver, 9000, OUT)
    stars = [thumbysim.SAVE.get("tp%d" % i, 0) for i in range(12)]
    ok = st["phase"] == "done" and all(v > 0 for v in stars[:4])
    print("practice: levels finished=%d stars=%s ok=%s" % (st["levels_done"], stars, ok))
    return ok


if __name__ == "__main__":
    if which in ("all", "practice"):
        practice()
    if which in ("all", "edge"):
        edge_shot()
    if which in ("all", "scripted"):
        scripted()
    if which in ("all", "soak"):
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        fr = int(sys.argv[3]) if len(sys.argv) > 3 else 25000
        for sd in range(1, n + 1):
            soak(sd, fr)
