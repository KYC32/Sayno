"""Motion clips for the two figurines, baked into the glTF file the web page plays.

    python3 blender/motions.py --glb web/assets/characters.glb   # both figures, a chair, every clip
    python3 blender/motions.py --check renders/motions          # strips of poses per clip, to look at

Every clip is computed rather than keyed by hand. Per frame a few curves say where the feet are,
how high the pelvis is and where a hand holds the notebook or the letter, and two-bone IK turns
that into joint rotations. Arms are always solved the same way (even a swinging arm is aimed by
IK), so any two clips blend without the forearms twisting. Only the joints move: the page walks
and turns each figure's root itself, at the walk_speed stored on the root (glTF extras, along
with where the chair goes behind the figure).

Clips, for both figures unless noted ("loop" ones start and end on the same pose):
    idle       loop  standing, breathing, the weight shifting a little
    walk       loop  walking on the spot
    look       once  head and chest turn to one side and back (Sayno to his left, the visitor to
                     her right, so placed side by side they look at each other)
    nod        once  two nods
    sit_down   once  sitting down on the chair just behind
    sit_idle   loop  sitting, hands on the thighs
    stand_up   once  sit_down backwards
    write      loop  Sayno: standing, writing in his notebook (the concept pose)
    sit_write  loop  Sayno: sitting, writing in his notebook
    hold       loop  the visitor: the letter held in both hands
    offer      once  the visitor: holding the letter out with a small bow, and back
look and nod move only the spine, neck and head, from and back to the standing pose; the page
plays them added on top of whatever else is playing (sitting, writing, walking).
"""
import argparse
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
from bpy_extras import anim_utils
from mathutils import Euler, Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_study as bs  # noqa: E402
import characters as ch  # noqa: E402

FPS = 30
SEAT = 0.38                 # chair seat height; the study's chairs come down to this when the figures move in
BREATH = 4.0                # seconds per breath; every loop but walk lasts one breath
HIDDEN = 1e-4               # the scale of a prop that is put away
CHAIR_BACK = 0.04           # the chair's centre behind the hip joints when sitting
GLTF_TRANSFORM = "@gltf-transform/cli@4.5.1"
UPPER = ("spine", "neck", "head")   # what look and nod move

STYLE = {
    # Sayno: past seventy, a slight stoop, a slower and shorter step, arms swinging less
    "sayno": dict(stoop=5.0, neck=4.0, head=3.0, toe_out=6.0, foot_x=0.008, arm_out=6.0,
                  stride=0.66, period=1.2, beta=0.62, lift=0.045, sink=0.032, bob=0.014, sway=0.013,
                  yaw=5.0, roll=2.5, arm=12.0, lean=2.0, heel=-12.0, toe=20.0, look=1, sit_time=2.0),
    "visitor": dict(stoop=1.0, neck=-1.0, head=4.0, toe_out=4.0, foot_x=0.006, arm_out=5.0,
                    stride=0.76, period=1.0, beta=0.6, lift=0.055, sink=0.03, bob=0.018, sway=0.012,
                    yaw=6.0, roll=3.0, arm=17.0, lean=2.0, heel=-14.0, toe=22.0, look=-1, sit_time=1.6),
}


# ---------------------------------------------------------------- small curves

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def smoother(x):
    x = clamp(x)
    return x * x * x * (x * (6 * x - 15) + 10)


def lerp(a, b, t):
    return a + (b - a) * t


def bump(x):
    """0 at both ends and 1 in the middle, with no corners."""
    return math.sin(math.pi * clamp(x)) ** 2


def hermite(p0, p1, m0, m1, s):
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * m0 + (3 * s2 - 2 * s3) * p1 + (s3 - s2) * m1


def keys(points, t):
    """A curve through (time, value) points, easing in and out of each."""
    if t <= points[0][0]:
        return points[0][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t <= t1:
            return lerp(v0, v1, ease((t - t0) / (t1 - t0)))
    return points[-1][1]


def waves(t):
    """Breath, weight shift and a slow drift of the gaze, all one breath long."""
    a = math.tau * t / BREATH
    return math.sin(a), math.sin(a + 1.1), math.sin(a + 2.3)


def E(x=0.0, y=0.0, z=0.0):
    return Euler((math.radians(x), math.radians(y), math.radians(z))).to_quaternion()


def rx(deg, v):
    return Matrix.Rotation(math.radians(deg), 3, "X") @ v


# ---------------------------------------------------------------- the rig

class Rig:
    """Forward and inverse kinematics on a Figure's joints, in the figure's own space (root at the
    origin, facing -y). Nothing in Blender changes until a pose is applied or keyed."""

    def __init__(self, F, spec, style):
        self.F, self.spec, self.st = F, spec, style
        n = len(F.name) + 1
        self.keys = list(F.j)
        self.parent = {k: (F.j[k].parent.name[n:] if F.j[k].parent else None) for k in self.keys}
        self.rest = {k: F.j[k].location.copy() for k in self.keys}
        self.thigh, self.shin = -self.rest["knee_R"].z, -self.rest["ankle_R"].z
        self.upper, self.fore = -self.rest["elbow_R"].z, -self.rest["wrist_R"].z
        self.thigh_r = spec["thigh"][1] * 0.94
        zs = SEAT + 0.068                     # the hip joints just above the cushion
        self.seat = (math.sqrt(self.thigh ** 2 - (zs - ch.ANKLE - self.shin) ** 2), zs)   # shins upright
        self.props = {}                       # name -> object whose scale shows or hides it
        self.worst = 0.0                      # longest leg reach asked for, as a share of the leg
        self.reset()

    def reset(self):
        self.q = {k: Quaternion() for k in self.keys}
        self.t = {k: self.rest[k].copy() for k in self.keys}
        self.shown = {}

    def frame(self, k):
        """Joint k's frame before its own rotation: its parent's world matrix moved to k."""
        p = self.parent[k]
        return (self.mw(p) if p else Matrix.Identity(4)) @ Matrix.Translation(self.t[k])

    def mw(self, k):
        return self.frame(k) @ self.q[k].to_matrix().to_4x4()

    def leg(self, side, ankle, pitch=0.0, yaw=0.0):
        """Ankle joint to `ankle`, the foot pitched (toe down positive) and turned (degrees)."""
        T = self.frame(f"hip_{side}").inverted() @ Vector(ankle)
        L1, L2 = self.thigh, self.shin
        psi = math.atan2(-T.x, -T.z)                   # roll the leg's plane out to the target
        down = math.hypot(T.x, T.z)
        reach = math.hypot(T.y, down)
        self.worst = max(self.worst, reach / (L1 + L2))
        D = min(max(reach, abs(L1 - L2) + 1e-4), (L1 + L2) * 0.9995)
        aim = math.atan2(T.y, down)
        a = math.acos(clamp((L1 * L1 + D * D - L2 * L2) / (2 * L1 * D), -1.0, 1.0))
        th = aim - a                                   # the knee in front of the hip-ankle line
        ky, kd = L1 * math.sin(th), L1 * math.cos(th)
        ts = math.atan2(D * math.sin(aim) - ky, D * math.cos(aim) - kd)
        self.q[f"hip_{side}"] = (Matrix.Rotation(psi, 3, "Y") @ Matrix.Rotation(th, 3, "X")).to_quaternion()
        self.q[f"knee_{side}"] = Quaternion((1, 0, 0), ts - th)
        foot = Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, "X")
        par = self.frame(f"ankle_{side}").to_3x3().normalized()
        self.q[f"ankle_{side}"] = (par.inverted() @ foot).to_quaternion()

    def arm(self, side, wrist, R, pole):
        """Wrist joint to `wrist`, turned to R (world); the elbow bends out towards pole."""
        S = self.frame(f"shoulder_{side}")
        s, Sr = S.translation, S.to_3x3().normalized()
        L1, L2 = self.upper, self.fore
        to = Vector(wrist) - s
        d = min(max(to.length, abs(L1 - L2) + 1e-4), (L1 + L2) * 0.999)
        t = to.normalized()
        p = Vector(pole) - Vector(pole).dot(t) * t
        if p.length < 1e-6:
            p = Vector((0.0, 1.0, 0.0)) - t.y * t
        p.normalize()
        a = math.acos(clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1.0, 1.0))
        u = math.cos(a) * t + math.sin(a) * p
        f = (d * t - L1 * u).normalized()
        x = u.cross(f)
        x = x.normalized() if x.length > 1e-6 else u.orthogonal().normalized()
        z = -u
        Ru = Matrix((x, z.cross(x), z)).transposed()
        self.q[f"shoulder_{side}"] = (Sr.inverted() @ Ru).to_quaternion()
        fl = Ru.inverted() @ f
        self.q[f"elbow_{side}"] = Quaternion((1, 0, 0), math.atan2(fl.y, -fl.z))
        par = self.frame(f"wrist_{side}").to_3x3().normalized()
        self.q[f"wrist_{side}"] = (par.inverted() @ R).to_quaternion()

    def snapshot(self):
        return dict(q={k: self.q[k].copy() for k in self.keys if k != "root"}, hips=self.t["hips"].copy(),
                    props={k: self.shown.get(k, False) for k in self.props})


# ---------------------------------------------------------------- hands

def hang(side, swing=0.0, out=5.0, bend=10.0, curl=8.0):
    """A free arm from angles in the chest's frame (degrees): swung forward, out to the side,
    the elbow bent forward; the hand follows the forearm, palm in, fingers curled a little."""
    sx = -1 if side == "R" else 1

    def target(r):
        S = r.frame(f"shoulder_{side}")
        Sr, s = S.to_3x3().normalized(), S.translation
        sw, ou, be, cu = (math.radians(a) for a in (swing, out, bend, curl))
        u = Vector((sx * math.sin(ou) * math.cos(sw), -math.sin(sw), -math.cos(ou) * math.cos(sw))).normalized()
        fwd = Vector((0.0, -1.0, 0.0))
        p = (fwd - fwd.dot(u) * u).normalized()
        f = (u * math.cos(be) + p * math.sin(be)).normalized()
        q = (fwd - fwd.dot(f) * f).normalized()
        fingers = Sr @ (f * math.cos(cu) + q * math.sin(cu))
        u, f = Sr @ u, Sr @ f
        elbow = s + r.upper * u
        wrist = elbow + r.fore * f
        line = (wrist - s).normalized()
        pole = elbow - (s + (elbow - s).dot(line) * line)
        return wrist, ch.hand_frame(fingers, Sr @ Vector((-sx, 0.0, 0.0)), side), pole
    return target


def on_thigh(side, along=0.58):
    """The hand resting on the top of the thigh, sitting."""
    sx = -1 if side == "R" else 1

    def target(r):
        K = r.mw(f"hip_{side}")
        Kr = K.to_3x3().normalized()
        up = Kr @ Vector((0.0, -1.0, 0.0))            # the front of the thigh, which faces up when sitting
        fingers = (Kr @ Vector((-sx * 0.22, 0.0, -1.0))).normalized()
        R = ch.hand_frame(fingers, -up, side)
        centre = K @ Vector((0.0, -r.thigh_r, -along * r.thigh)) + up * 0.022
        return centre - R @ Vector((0.0, 0.0, -0.05)), R, Vector((sx * 1.0, 0.7, -0.2))
    return target


def held(side, M, local, pole):
    """The wrist where a prop held at M (world 4x4) puts it: local is the wrist in the prop's space."""
    def target(r):
        W = M @ local
        return W.translation.copy(), W.to_3x3().normalized(), Vector(pole)
    return target


def mixed(a, b, w):
    """Between two hand targets."""
    def target(r):
        wa, Ra, pa = a(r)
        wb, Rb, pb = b(r)
        R = Ra.to_quaternion().slerp(Rb.to_quaternion(), w).to_matrix()
        return wa.lerp(wb, w), R, pa.lerp(pb, w)
    return target


def wrist_in(point, fingers, palm, side):
    """A wrist's place in a prop's space, from where the palm centre goes and how the hand turns."""
    R = ch.hand_frame(Vector(fingers), Vector(palm), side)
    return Matrix.Translation(Vector(point) - R @ Vector((0.0, 0.0, -0.05))) @ R.to_4x4()


NOTEBOOK_WRIST = wrist_in(*ch.NOTEBOOK_GRIP, "L")
LETTER_WRIST = {"R": wrist_in((-0.083, -0.012, -0.004), (0.35, 0.94, 0.0), (1, 0, 0), "R"),
                "L": wrist_in((0.083, -0.012, -0.004), (-0.35, 0.94, 0.0), (-1, 0, 0), "L")}
# the pen held as in the concept pose, kept relative to the notebook so it writes at any angle
_n0 = Vector((0.05, 0.62, 0.78)).normalized()
PEN_IN_BOOK = (ch.basis((-1, 0, 0.05), _n0).transposed()
               @ ch.turn_to(ch.PEN_BACK, Vector((-0.45, 0.42, 0.79)), (0, 0, -1), Vector((0.2, -0.5, -0.84))))
LETTER_N = (Vector((0.0, -0.93, 0.36)).normalized(), Vector((0.0, -0.99, 0.12)).normalized())


# ---------------------------------------------------------------- poses (what a frame asks for)

def feet(r, apart=0.0, turn=0.0):
    out = {}
    for side, sx in (("R", -1), ("L", 1)):
        x = r.rest[f"hip_{side}"].x + sx * (r.st["foot_x"] + apart)
        out[side] = (Vector((x, 0.0, ch.ANKLE)), 0.0, sx * (r.st["toe_out"] + turn))
    return out


def standing(r, t=0.0):
    st = r.st
    b, w, g = waves(t)
    return dict(hips_t=r.rest["hips"] + Vector((0.006 * w, 0.0, -0.007 + 0.0012 * b)),
                rot=dict(hips=(0, 0, 1.0 * w), spine=(st["stoop"] - 0.8 * b, 0, -1.0 * w),
                         neck=(st["neck"] + 0.35 * b, 0, 0), head=(st["head"] + 0.3 * b, 0, 1.4 * g)),
                feet=feet(r), arms={s: hang(s, swing=-1.5 + 0.5 * b, out=st["arm_out"], bend=9.0) for s in "RL"},
                props={})


def seated(r, t=0.0):
    st = r.st
    b, w, g = waves(t)
    ys, zs = r.seat
    return dict(hips_t=Vector((0.0, ys, zs + 0.0012 * b)),
                rot=dict(hips=(-6, 0, 0.6 * w), spine=(st["stoop"] + 6 - 0.8 * b, 0, -0.6 * w),
                         neck=(st["neck"] + 0.35 * b, 0, 0), head=(st["head"] + 1 + 0.3 * b, 0, 1.4 * g)),
                feet=feet(r, apart=0.012, turn=4.0), arms={s: on_thigh(s) for s in "RL"}, props={})


HEEL = Vector((0.0, 0.07, -ch.ANKLE))       # where the heel meets the floor, from the ankle joint
BALL = Vector((0.0, -0.125, -ch.ANKLE))     # where the foot rolls over before it leaves the floor


def stance(st, u):
    """Ankle (y, z) and foot pitch while a foot is down (u from 0, the heel strike, to beta): the
    floor slides back under the figure at one stride per cycle."""
    S, beta = st["stride"], st["beta"]
    flat = Vector((0.0, -beta * S / 2 + S * u, ch.ANKLE))
    u1, u2 = 0.1, beta - 0.2
    if u < u1:
        th = st["heel"] * (1 - ease(u / u1))
        a = flat + HEEL - rx(th, HEEL)
    elif u <= u2:
        th, a = 0.0, flat
    else:
        th = st["toe"] * ease((u - u2) / (beta - u2))
        a = flat + BALL - rx(th, BALL)
    return a.y, a.z, th


def foot_cycle(st, u):
    beta = st["beta"]
    if u <= beta:
        return stance(st, u)
    s, span, e = (u - beta) / (1 - beta), 1 - beta, 1e-4
    y0, z0, th0 = stance(st, beta)
    ya, za, _ = stance(st, beta - e)
    y1, z1, th1 = stance(st, 0.0)
    yb, zb, _ = stance(st, e)
    y = hermite(y0, y1, (y0 - ya) / e * span, (yb - y1) / e * span, s)
    z = hermite(z0, z1, (z0 - za) / e * span, (zb - z1) / e * span, s) + st["lift"] * math.sin(math.pi * s) ** 2
    th = lerp(th0, th1, smoother(s / 0.7))
    return y, z, th


def walking(r, u):
    st = r.st
    fs = {}
    for side, sx, ph in (("R", -1, 0.0), ("L", 1, 0.5)):
        y, z, pitch = foot_cycle(st, (u + ph) % 1.0)
        x = r.rest[f"hip_{side}"].x + sx * st["foot_x"]
        fs[side] = (Vector((x, y, z)), pitch, sx * st["toe_out"] * 0.6)
    c, s = math.cos(math.tau * u), math.sin(math.tau * u)
    low = (1 - math.cos(2 * math.tau * (u - 0.25))) / 2      # 0 over the standing foot, 1 between steps
    yaw, roll = st["yaw"] * c, st["roll"] * s
    swing = st["arm"] * math.cos(math.tau * (u - 0.07))
    arms = {}
    for side, sw in (("R", -swing), ("L", swing)):
        arms[side] = hang(side, swing=sw - 2.0, out=st["arm_out"], bend=10 + 10 * max(0.0, sw) / st["arm"])
    return dict(hips_t=r.rest["hips"] + Vector((-st["sway"] * s, 0.0, -st["sink"] - st["bob"] * low)),
                rot=dict(hips=(st["lean"], roll, yaw), spine=(st["stoop"] + 1.0, -1.1 * roll, -1.6 * yaw),
                         neck=(st["neck"] - 1.0, 0.0, 0.35 * yaw), head=(st["head"] - 1.0 + 1.5 * low, 0.1 * roll, 0.25 * yaw)),
                feet=fs, arms=arms, props={})


def add(rot, k, d):
    rot[k] = tuple(a + b for a, b in zip(rot[k], d))


def sitting_down(r, s):
    """s from 0 (standing, as idle starts) to 1 (sitting, as sit_idle starts)."""
    A, B = standing(r), seated(r)
    wy, wz, wr = smoother((s - 0.06) / 0.74), smoother((s - 0.12) / 0.70), smoother((s - 0.08) / 0.86)
    lean = bump((s - 0.03) / 0.86)
    ha, hb = A["hips_t"], B["hips_t"]
    rot = {k: tuple(lerp(a, b, wr) for a, b in zip(A["rot"][k], B["rot"][k])) for k in A["rot"]}
    add(rot, "hips", (24 * lean, 0, 0))
    add(rot, "spine", (9 * lean, 0, 0))
    add(rot, "neck", (-8 * lean, 0, 0))
    add(rot, "head", (-9 * lean, 0, 0))
    fs = {k: (A["feet"][k][0].lerp(B["feet"][k][0], wr), 0.0, lerp(A["feet"][k][2], B["feet"][k][2], wr)) for k in "RL"}
    wa = smoother((s - 0.48) / 0.44)
    arms = {k: mixed(hang(k, swing=-1.5 + 26 * lean, out=r.st["arm_out"] + 4 * lean, bend=9 + 28 * lean),
                     B["arms"][k], wa) for k in "RL"}
    return dict(hips_t=Vector((lerp(ha.x, hb.x, wr), lerp(ha.y, hb.y, wy), lerp(ha.z, hb.z, wz))),
                rot=rot, feet=fs, arms=arms, props={})


def looking(r, t):
    """Turning to look to one side, held, and back (3 s)."""
    d = r.st["look"]
    head = keys([(0, 0), (0.1, -0.04), (0.6, 1.05), (0.85, 1.0), (2.1, 1.0), (2.75, 0.0)], t)
    neck = keys([(0.12, 0), (0.7, 1.0), (2.15, 1.0), (2.8, 0.0)], t)
    chest = keys([(0.25, 0), (0.95, 1.0), (2.05, 1.0), (2.9, 0.0)], t)
    tilt = keys([(0.8, 0), (1.25, 1.0), (1.85, 1.0), (2.3, 0.0)], t)
    ack = keys([(1.35, 0), (1.55, 1.0), (1.8, 0.0)], t)
    it = standing(r)
    it["post"] = dict(spine=(0, 0, d * 18 * chest), neck=(0, 0, d * 14 * neck),
                      head=(-2 * head + 5 * ack, -d * 5 * tilt, d * 38 * head))
    return it


def nodding(r, t):
    """Two nods (1.6 s)."""
    h = keys([(0, 0), (0.24, 15), (0.52, 2), (0.78, 11), (1.12, 0)], t)
    it = standing(r)
    it["post"] = dict(spine=(0.12 * h, 0, 0), neck=(0.35 * h, 0, 0), head=(h, 0, 0))
    return it


def nib(t):
    """The nib on the notebook (notebook space) over a 4 s loop: two lines of the right-hand page,
    lifting between words and between lines."""
    x0, x1, lines = 0.014, 0.092, (0.021, 0.004)
    t_line, t_back = 1.45, 0.35

    def on_line(y, tau):
        x = lerp(x0, x1, tau)
        wig = 0.0016 * math.sin(math.tau * 5.5 * tau * t_line)
        lift = 0.003 * max(0.0, math.sin(math.tau * 2.6 * tau * t_line)) ** 8
        return Vector((x, y - 0.002 + wig, 0.0045 + lift))

    def jump(a, b, tau):
        return a.lerp(b, ease(tau)) + Vector((0.0, 0.0, 0.007 * bump(tau)))
    a0, a1 = on_line(lines[0], 0.0), on_line(lines[0], 1.0)
    b0, b1 = on_line(lines[1], 0.0), on_line(lines[1], 1.0)
    if t < t_line:
        return on_line(lines[0], t / t_line)
    t -= t_line
    if t < t_back:
        return jump(a1, b0, t / t_back)
    t -= t_back
    if t < t_line:
        return on_line(lines[1], t / t_line)
    t -= t_line
    return jump(b1, a0, smoother((t - 0.25) / (BREATH - 2 * t_line - t_back - 0.25)))


def writing(r, t, sitting):
    """Sayno writing in his notebook, standing (the concept pose) or sitting."""
    it = seated(r, t) if sitting else standing(r, t)
    b = waves(t)[0]
    if sitting:
        ys, zs = r.seat
        c = Vector((0.025, ys - 0.215, zs + 0.13 + 0.0012 * b))
        n = Vector((0.0, 0.52, 0.85))
        it["rot"].update(spine=(r.st["stoop"] + 14 - 0.8 * b, 0, 0), neck=(12 + 0.35 * b, 0, 0), head=(16, 0, -3))
    else:
        zc = it["hips_t"].z + r.rest["spine"].z + 0.13
        c = Vector((0.035, -0.255, zc + 0.0012 * b))
        n = Vector((0.05, 0.62, 0.78))
        it["rot"].update(spine=(4 - 0.8 * b, 0, 0), neck=(9 + 0.35 * b, 0, 0), head=(16, 0, -4))
    B = Matrix.Translation(c) @ ch.basis((-1, 0, 0.05), n.normalized()).to_4x4()
    p = nib(t)
    add(it["rot"], "head", (0, 0, -30 * (p.x - 0.053)))         # the eyes follow the pen a little
    R = B.to_3x3() @ PEN_IN_BOOK
    point = B @ p - R @ ch.PEN_NIB

    def pen(r_):
        return point, R, Vector((-1, 0.7, -0.8))
    it["arms"] = {"L": held("L", B, NOTEBOOK_WRIST, (1, 0.6, -1)), "R": pen}
    it["props"] = {"notebook": True, "pen": True}
    return it


def holding(r, t=0.0, ext=0.0, bow=0.0):
    """The visitor holding the letter in both hands; ext holds it out, bow bows over it."""
    it = standing(r, t)
    b = waves(t)[0]
    zc = it["hips_t"].z + r.rest["spine"].z + 0.12
    c = Vector((0.0, -0.215 - 0.2 * ext - 0.04 * bow, zc + 0.04 * ext - 0.045 * bow + 0.0012 * b))
    n = LETTER_N[0].slerp(LETTER_N[1], ext)
    M = Matrix.Translation(c) @ ch.basis((1, 0, 0), n).to_4x4()
    it["hips_t"] = it["hips_t"] + Vector((0.0, 0.018 * bow, -0.006 * bow))
    add(it["rot"], "hips", (9 * bow, 0, 0))
    add(it["rot"], "spine", (7 * bow, 0, 0))
    add(it["rot"], "neck", (3 * bow, 0, 0))
    add(it["rot"], "head", (6 - 6 * ext + 4 * bow, 0, 0))
    it["arms"] = {s: held(s, M, LETTER_WRIST[s], (sx * 0.8, 0.5, -1.0)) for s, sx in (("R", -1), ("L", 1))}
    it["props"] = {"letter": True}
    return it


def offering(r, t):
    """Holding the letter out with a small bow, and back (3.2 s)."""
    ext = keys([(0.25, 0), (1.05, 1.0), (2.15, 1.0), (2.95, 0.0)], t)
    bow = keys([(0.45, 0), (1.15, 1.0), (1.85, 1.0), (2.6, 0.0)], t)
    return holding(r, 0.0, ext, bow)


def solve(r, it):
    r.reset()
    r.t["hips"] = Vector(it["hips_t"])
    for k, e in it["rot"].items():
        r.q[k] = E(*e)
    for k, e in it.get("post", {}).items():
        r.q[k] = r.q[k] @ E(*e)
    for side, (pos, pitch, yaw) in it["feet"].items():
        r.leg(side, pos, pitch, yaw)
    for side, target in it["arms"].items():
        r.arm(side, *target(r))
    r.shown = dict(it.get("props", {}))
    return r.snapshot()


# ---------------------------------------------------------------- clips

class Clip:
    def __init__(self, name, frames, loop, upper=False):
        self.name, self.frames, self.loop, self.upper = name, frames, loop, upper


def frames(seconds):
    return round(seconds * FPS)


def bake(r, who):
    st = r.st
    out = []

    def clip(name, fn, seconds, loop, upper=False):
        n = frames(seconds)
        out.append(Clip(name, [solve(r, fn(f / n if name == "walk" else f / FPS)) for f in range(n + 1)], loop, upper))

    clip("idle", lambda t: standing(r, t), BREATH, True)
    clip("walk", lambda u: walking(r, u), st["period"], True)
    clip("look", lambda t: looking(r, t), 3.0, False, upper=True)
    clip("nod", lambda t: nodding(r, t), 1.6, False, upper=True)
    clip("sit_down", lambda t: sitting_down(r, t / st["sit_time"]), st["sit_time"], False)
    clip("sit_idle", lambda t: seated(r, t), BREATH, True)
    out.append(Clip("stand_up", out[-2].frames[::-1], False))
    if who == "sayno":
        clip("write", lambda t: writing(r, t, False), BREATH, True)
        clip("sit_write", lambda t: writing(r, t, True), BREATH, True)
    else:
        clip("hold", lambda t: holding(r, t), BREATH, True)
        clip("offer", lambda t: offering(r, t), 3.2, False)
    return out


# ---------------------------------------------------------------- the scene

def chair(name="chair"):
    """A plain wooden chair like the study's, its seat at SEAT, facing -y (its back towards +y)."""
    wd, cu = bs.mat("chair", rough=0.55), bs.mat("cushion", rough=0.7)
    sz = SEAT - 0.035 - 0.0175
    parts = [bs.box("CHAIR_seat", (0.46, 0.42, 0.035), (0, 0, sz), wd, bevel=0.01, segs=3),
             bs.box("CHAIR_cushion", (0.40, 0.36, 0.035), (0, 0.01, sz + 0.035), cu, bevel=0.014, segs=3)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(bs.cyl(f"CHAIR_leg_{sx}{sy}", 0.016, sz - 0.0175, (sx * 0.19, sy * 0.17, (sz - 0.0175) / 2),
                                wd, n=12, r2=0.021))
        parts.append(bs.cyl(f"CHAIR_rung_y{sx}", 0.008, 0.34, (sx * 0.19, 0, 0.11), wd, n=10, rot=(math.pi / 2, 0, 0)))
    for sy in (-1, 1):
        parts.append(bs.cyl(f"CHAIR_rung_x{sy}", 0.008, 0.38, (0, sy * 0.17, 0.15), wd, n=10, rot=(0, math.pi / 2, 0)))
    yb, zb = 0.17, sz + 0.0175
    back = [bs.box(f"CHAIR_post_{sx}", (0.035, 0.035, 0.45), (sx * 0.19, yb, zb + 0.225), wd, bevel=0.006) for sx in (-1, 1)]
    back += [bs.box("CHAIR_crest", (0.44, 0.03, 0.085), (0, yb, zb + 0.41), wd, bevel=0.01, segs=3),
             bs.box("CHAIR_rail", (0.38, 0.022, 0.03), (0, yb, zb + 0.12), wd, bevel=0.005)]
    back += [bs.cyl(f"CHAIR_spindle_{k}", 0.009, 0.25, (k * 0.09, yb, zb + 0.255), wd, n=10) for k in (-1, 0, 1)]
    bs.turn(back, (0, yb, zb), (math.radians(-8), 0, 0))
    return bs.group(name, parts + back)


def build():
    """Both figures with dot eyes, their props on their hands, at the origin."""
    ch.fresh()
    bpy.context.scene.render.fps = FPS
    bs.COLL = bs._collection("CHARACTERS")
    rigs = {}
    for who, spec, props in (("sayno", ch.SAYNO, ch.sayno_props), ("visitor", ch.VISITOR, ch.visitor_props)):
        F = props(ch.build_figure(spec, eyes=True))
        r = Rig(F, spec, STYLE[who])
        for k in r.keys:
            F.j[k].rotation_mode = "QUATERNION"
        if who == "sayno":
            r.props = {"notebook": F.notebook, "pen": F.pen}
            F.notebook.parent = F.j["wrist_L"]
            F.notebook.matrix_parent_inverse = Matrix.Identity(4)
            F.notebook.matrix_basis = NOTEBOOK_WRIST.inverted()
        else:
            r.props = {"letter": F.letter}
            F.letter.parent = F.j["wrist_R"]
            F.letter.matrix_parent_inverse = Matrix.Identity(4)
            F.letter.matrix_basis = LETTER_WRIST["R"].inverted()
        rigs[who] = r
    return rigs


def apply(r, snap, at=(0.0, 0.0)):
    """Put a pose on the Blender objects (for renders; the export keys them instead)."""
    r.F.j["root"].location = (at[0], at[1], 0.0)
    for k, q in snap["q"].items():
        r.F.j[k].rotation_quaternion = q
    r.F.j["hips"].location = snap["hips"]
    for k, shown in snap["props"].items():
        r.props[k].scale = (1.0,) * 3 if shown else (HIDDEN,) * 3


# ---------------------------------------------------------------- check renders

def check(rigs, clips, out_dir, per=6):
    """A strip of poses for every clip, from a three-quarter view, plus walks from the side."""
    from PIL import Image, ImageDraw
    W, H = 260, 340
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene                 # Cycles, few samples: there is no GPU for Workbench here
    scene.render.engine = "CYCLES"
    scene.cycles.device, scene.cycles.samples, scene.cycles.use_denoising = "CPU", 6, True
    scene.render.resolution_x, scene.render.resolution_y = W, H
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    ch.plain_stage()
    floor = bpy.data.objects["FLOOR"]
    seat = chair("CHECK_chair")
    data = bpy.data.cameras.new("CHECK_cam")
    data.type, data.ortho_scale = "ORTHO", 2.1
    cam = bpy.data.objects.new("CHECK_cam", data)
    bs._link(cam)
    scene.camera = cam
    owned = {who: [o for o in bpy.data.objects if o.name.lower().startswith(who + "_")] for who in rigs}

    def aim(view):
        target = Vector((0.0, -0.05, 0.78))
        d = {"front": Vector((-1.6, -3.6, 1.3)), "side": Vector((-4.0, -0.4, 0.9))}[view]
        cam.location = target + d
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()

    for who, r in rigs.items():
        for other, objs in owned.items():
            for o in objs:
                o.hide_render = other != who
        for clip in clips[who]:
            for view in (("front", "side") if clip.name in ("walk", "sit_down") else ("front",)):
                aim(view)
                n = len(clip.frames) - 1
                picks = [round(i * n / (per - (0 if clip.loop else 1))) for i in range(per)]
                tiles = []
                for f in picks:
                    apply(r, clip.frames[min(f, n)])
                    sitting = clip.name.startswith("sit") or clip.name == "stand_up"
                    seat.hide_render = not sitting
                    for o in seat.children:
                        o.hide_render = not sitting
                    seat.location = (0.0, r.seat[0] + CHAIR_BACK, 0.0)
                    path = out_dir / "_tile.png"
                    scene.render.filepath = str(path)
                    bpy.ops.render.render(write_still=True)
                    im = Image.open(path).convert("RGB")
                    ImageDraw.Draw(im).text((8, 6), f"{clip.name} {f / (n if clip.name == 'walk' else FPS):.2f}", fill=(40, 30, 20))
                    tiles.append(im)
                sheet = Image.new("RGB", (W * len(tiles), H), "white")
                for i, im in enumerate(tiles):
                    sheet.paste(im, (W * i, 0))
                sheet.save(out_dir / f"{who}_{clip.name}_{view}.png")
        (out_dir / "_tile.png").unlink(missing_ok=True)
    for o in (floor, seat, cam, *seat.children, *[o for o in bpy.data.objects if o.name.startswith("LGT_")]):
        bpy.data.objects.remove(o)


# ---------------------------------------------------------------- export

def key_clips(r, clips):
    """One slotted action per clip, on an NLA track named <figure>_<clip> on every joint it moves:
    the glTF exporter turns same-named tracks into one animation."""
    who = r.F.name
    for clip in clips:
        name = f"{who}_{clip.name}"
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        targets = [k for k in r.keys if k != "root" and (not clip.upper or k in UPPER)]
        channels = [(r.F.j[k], "rotation_quaternion", [s["q"][k] for s in clip.frames]) for k in targets]
        if not clip.upper:
            channels.append((r.F.j["hips"], "location", [s["hips"] for s in clip.frames]))
            for k, ob in r.props.items():
                v = 1.0 if clip.frames[0]["props"][k] else HIDDEN
                channels.append((ob, "scale", [Vector((v, v, v))] * len(clip.frames)))
        slots = {}
        for ob, path, values in channels:
            if path == "rotation_quaternion":           # keep neighbouring keys on the same side
                values = [v.copy() for v in values]
                for a, b in zip(values, values[1:]):
                    if a.dot(b) < 0:
                        b.negate()
            if ob.name not in slots:
                slots[ob.name] = act.slots.new(id_type="OBJECT", name=ob.name)
            bag = anim_utils.action_ensure_channelbag_for_slot(act, slots[ob.name])
            for i in range(len(values[0])):
                fc = bag.fcurves.new(path, index=i)
                fc.keyframe_points.add(len(values))
                fc.keyframe_points.foreach_set("co", [c for f, v in enumerate(values) for c in (f, v[i])])
                fc.update()
        for obname, slot in slots.items():
            ob = bpy.data.objects[obname]
            ad = ob.animation_data or ob.animation_data_create()
            track = ad.nla_tracks.new()
            track.name = name
            strip = track.strips.new(name, 0, act)
            strip.action_slot = slot
            ad.action = None


def export(rigs, clips, out, keep_raw=None):
    for who, r in rigs.items():
        key_clips(r, clips[who])
        root = r.F.j["root"]
        st = r.st
        root["walk_speed"] = round(st["stride"] / st["period"], 4)
        root["chair_offset"] = [0.0, 0.0, -round(r.seat[0] + CHAIR_BACK, 4)]    # three.js axes: behind the figure
        for k in r.keys:
            r.F.j[k].rotation_quaternion = Quaternion()
            r.F.j[k].location = r.rest[k]
        for ob in r.props.values():
            ob.scale = (HIDDEN,) * 3
    chair("chair")
    bpy.context.scene.frame_set(0)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    raw, mid = tmp / "raw.glb", tmp / "resampled.glb"
    bpy.ops.export_scene.gltf(filepath=str(raw), export_format="GLB", use_selection=False, export_apply=True,
                              export_lights=False, export_cameras=False, export_yup=True, export_texcoords=False,
                              export_normals=True, export_tangents=False, export_attributes=False,
                              export_extras=True, export_animations=True, export_animation_mode="NLA_TRACKS",
                              export_force_sampling=True, export_frame_step=1,
                              export_optimize_animation_size=False, export_optimize_animation_keep_anim_object=True,
                              export_anim_slide_to_zero=True)
    if keep_raw:
        shutil.copy(raw, keep_raw)
    subprocess.run(["npx", "--yes", GLTF_TRANSFORM, "resample", str(raw), str(mid)], check=True)
    subprocess.run(["npx", "--yes", GLTF_TRANSFORM, "meshopt", str(mid), str(out), "--level", "medium"], check=True)
    print(f"exported {out} ({out.stat().st_size // 1024} KB; raw {raw.stat().st_size // 1024} KB)")
    shutil.rmtree(tmp)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb")
    ap.add_argument("--check")
    ap.add_argument("--only", help="comma-separated clip names, for --check")
    ap.add_argument("--keep-raw", help="also save the glTF as Blender exported it, before glTF-Transform")
    a = ap.parse_args(argv)
    rigs = build()
    clips = {who: bake(r, who) for who, r in rigs.items()}
    for who, r in rigs.items():
        print(f"{who}: longest leg reach {r.worst:.3f} of the leg; seat at y {r.seat[0]:.3f}, z {r.seat[1]:.3f}")
    if a.check:
        only = set(a.only.split(",")) if a.only else None
        check(rigs, {w: [c for c in cs if not only or c.name in only] for w, cs in clips.items()}, a.check)
    if a.glb:
        export(rigs, clips, a.glb, a.keep_raw)


if __name__ == "__main__":
    main()
