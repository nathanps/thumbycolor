"""Measure how close each CPU level lands to the nearest enemy, in a 4-CPU game.

Usage: python scorched_accuracy.py [frames]
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumbysim
GAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "1ScorchedThumb", "main.py")
stats = {}
frame_ref = [0]
st = {"patched": False, "since": 0, "last": None}

def driver(frame, g):
    G = g.get("G")
    pressed = set()
    if G is None:
        return pressed, []
    if G.state == 3:
        frame_ref[0] = frame
    if not st["patched"]:
        orig = g["boom"]
        def boom(x, y, r, dmg, owner, dirt):
            if owner is not None and not dirt and st.get("turnkey") != (frame_ref[0], id(owner)):
                st["turnkey"] = (frame_ref[0], id(owner))
                foes = [p for p in G.players if p.alive and p is not owner]
                if foes:
                    d = min(abs(p.x - x) for p in foes)
                    stats.setdefault(owner.ctype, []).append(d)
                    if owner.ctype == 3 and d > 12:
                        t = owner.ai_target
                        print("  hard miss d=%d pred=%s actual=%d wpn=%s angle=%d power=%d/%d target_dx=%d streak=%d wind=%d" % (
                            d, getattr(owner, 'pred', '?'), x, getattr(owner, 'fired_wpn', '?'), owner.angle, owner.power, owner.max_power(),
                            (t.x - owner.x) if t else 0, owner.ai_streak, G.wind))
            return orig(x, y, r, dmg, owner, dirt)
        g["boom"] = boom
        ofire = g["fire"]
        def fire(p):
            p.fired_wpn = p.wsel if p.inv[p.wsel] != 0 else 0
            # Where would a perfect, tank-free shot land?
            a = math.radians(p.angle); sp = p.power * g["V_MAX"] / 1000
            tx, ty = p.barrel_tip(p.angle, 7)
            g["sim_ax"][0] = int(G.wind * g["WIND_K"] / 4 * 65536)
            p.pred = g["sim_shot"](int(tx*65536), int(ty*65536), int(math.cos(a)*sp*65536), int(-math.sin(a)*sp*65536))
            return ofire(p)
        g["fire"] = fire
        st["patched"] = True
    s = G.state
    if s != st["last"]:
        st["last"] = s; st["since"] = 0
    st["since"] += 1
    t = st["since"]
    if s == 0 and t % 10 == 5: pressed.add("A")
    if s == 1:
        seq = {3: "RIGHT", 6: "DOWN", 8: "DOWN", 10: "DOWN", 12: "LEFT", 14: "UP", 16: "UP", 18: "UP", 20: "UP", 22: "A"}
        if t in seq: pressed.add(seq[t])
    if s in (7, 8) and t % 40 == 35: pressed.add("A")
    return pressed, []

thumbysim.SAVE.update({"n": 4, "r": 3, "ty1": 1, "ty2": 2, "ty3": 3})
thumbysim.run_game(GAME, driver, int(sys.argv[1]) if len(sys.argv) > 1 else 20000, os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "acc"), seed=7)
for lvl in sorted(stats):
    d = sorted(stats[lvl])
    n = len(d)
    print("CPU level %d: shots=%d median miss=%dpx  within 6px=%d%%  within 12px=%d%%" % (
        lvl, n, d[n // 2], 100 * sum(1 for v in d if v <= 6) // n, 100 * sum(1 for v in d if v <= 12) // n))
