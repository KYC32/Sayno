"""Two figurines for the study, at the concept stage: Sayno and the visitor.

Each figure is a set of rigid parts hung on a tree of joints (empties): a pose is a handful of
joint rotations, and the web page can later play glTF node animations on the same joints.

    python3 blender/characters.py --sheet renders/char_sheet.png      # both figures, plain ground
    python3 blender/characters.py --faces renders/char_faces.png      # faceless next to dot eyes
    python3 blender/characters.py --study renders/char_study.png [--close] [--mood night]
    python3 blender/characters.py --save blender/characters.blend

By default Sayno has no face and the visitor has dot eyes (--eyes none|visitor|both). Sayno
let a newspaper print a caricature instead of his photograph (p.6), and in twenty years showed
readers nothing but photos of his model bicycles (p.287).

What the book says about him and is used here: thin, a 30-inch waist at fifty (p.64); no
luxury brands; Montblanc and Waterman fountain pens, because he likes to scribble, and a metal
watch (pp.373-374).
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_study as bs  # noqa: E402


def srgb(r, g, b):
    """Linear colour from 0-255 sRGB, so the swatches can be picked by eye."""
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b))


COLORS = {
    "skin": srgb(226, 184, 152),
    "eye": srgb(34, 28, 26),
    # Sayno: plain clothes, nothing with a label on it
    "sayno_hair": srgb(200, 198, 192),
    "brow": srgb(150, 146, 140),
    "cardigan": srgb(70, 78, 100),
    "cardigan_rib": srgb(56, 63, 82),
    "button": srgb(156, 124, 88),
    "shirt": srgb(240, 237, 228),
    "slacks": srgb(104, 99, 94),
    "shoe": srgb(98, 60, 36),
    "sole": srgb(44, 34, 28),
    "steel": srgb(206, 206, 210),
    "dial": srgb(244, 242, 236),
    "pen": srgb(20, 20, 22),
    "gold": srgb(214, 172, 92),
    # the visitor: anyone, so ordinary clothes in a colour that stands out against the wood
    "visitor_hair": srgb(62, 44, 36),
    "sweater": srgb(216, 162, 58),
    "sweater_rib": srgb(192, 138, 44),
    "jeans": srgb(74, 102, 144),
    "jeans_cuff": srgb(126, 154, 192),
    "sneaker": srgb(240, 238, 232),
    "sneaker_sole": srgb(180, 132, 88),
    "envelope": srgb(246, 240, 224),
    "envelope_flap": srgb(226, 216, 192),
    "seal": srgb(172, 42, 36),
    "notebook": srgb(122, 80, 50),
    "page": srgb(246, 240, 226),
}


ANKLE = 0.085                 # ankle joints above the floor


def cmat(name, rough=0.8, metal=0.0):
    return bs.mat("CHR_" + name, color=COLORS[name], rough=rough, metal=metal)


# ---------------------------------------------------------------- shapes

def loft_geom(sections, n=24):
    """Stacked ellipses (z, rx, ry[, cx, cy]) from the bottom up; a zero radius closes an end and an
    open end gets a flat cap. Like build_study.lathe_geom, the faces point outward."""
    v, f, rings = [], [], []
    for s in sections:
        z, rx, ry = s[:3]
        cx, cy = (s[3], s[4]) if len(s) > 3 else (0.0, 0.0)
        if rx < 1e-6:
            rings.append([len(v)])
            v.append((cx, cy, z))
        else:
            rings.append(list(range(len(v), len(v) + n)))
            v += [(cx + rx * math.cos(k / n * math.tau), cy + ry * math.sin(k / n * math.tau), z) for k in range(n)]
    for A, B in zip(rings, rings[1:]):
        for k in range(n):
            k1 = (k + 1) % n
            a0, a1 = (A[0], A[0]) if len(A) == 1 else (A[k], A[k1])
            b0, b1 = (B[0], B[0]) if len(B) == 1 else (B[k], B[k1])
            face = []
            for i in (a0, a1, b1, b0):
                if i not in face:
                    face.append(i)
            if len(face) >= 3:
                f.append(tuple(face))
    if len(rings[0]) > 1:
        f.append(tuple(reversed(rings[0])))
    if len(rings[-1]) > 1:
        f.append(tuple(rings[-1]))
    return v, f


def ellipsoid(cz, rx, ry, rz, rings=12, jaw=1.0, cx=0.0, cy=0.0):
    """Sections of an ellipsoid; jaw < 1 narrows the lower half."""
    out = []
    for i in range(rings + 1):
        phi = -math.pi / 2 + math.pi * i / rings
        c = max(math.cos(phi), 0.0)
        k = 1.0 - (1.0 - jaw) * max(-math.sin(phi), 0.0) if jaw != 1.0 else 1.0
        out.append((cz + rz * math.sin(phi), rx * c * k, ry * c, cx, cy))
    return out


def capsule(length, r0, r1, aspect=1.0, caps=4, flat_end=False):
    """A rounded limb hanging from z=0 to z=-length, radius r0 at the joint and r1 at the end;
    aspect < 1 flattens it front to back. flat_end leaves the far end cut off flat, for a limb
    that ends inside a cuff or a shoe."""
    secs = [(-length, r1, r1 * aspect)] if flat_end else []
    for i in range(0 if flat_end else caps + 1):
        a = -math.pi / 2 + math.pi / 2 * i / caps
        r = r1 * math.cos(a)
        secs.append((-length + r1 * math.sin(a), r, r * aspect))
    for i in range(1, caps + 1):
        a = math.pi / 2 * i / caps
        r = r0 * math.cos(a)
        secs.append((r0 * math.sin(a), r, r * aspect))
    return secs


def hair_geom(rx, ry, rz, cut, n=40, rings=14, part=0.0):
    """A cap over an ellipsoid centred on the origin, from the crown down to a hairline that
    depends on the direction: cut = (front, side, back) polar angles in degrees. part (degrees)
    sweeps the fringe: lower over one eye, higher over the other."""
    front, side, back = (math.radians(a) for a in cut)

    def limit(theta):
        a = math.atan2(math.sin(theta + math.pi / 2), math.cos(theta + math.pi / 2))   # 0 at the front (-y)
        d = abs(a)
        t = min(d / (math.pi / 2), 1.0)
        s = t * t * (3 - 2 * t)
        if d <= math.pi / 2:
            sweep = math.radians(part) * math.sin(a * 2) if d < math.pi / 2 else 0.0
            return front + (side - front) * s + sweep
        t = (d - math.pi / 2) / (math.pi / 2)
        return side + (back - side) * t * t * (3 - 2 * t)

    v = [(0.0, 0.0, rz)]
    for j in range(1, rings + 1):
        for k in range(n):
            th = k / n * math.tau
            ph = j / rings * limit(th)
            v.append((rx * math.sin(ph) * math.cos(th), ry * math.sin(ph) * math.sin(th), rz * math.cos(ph)))
    f = [(1 + k, 1 + (k + 1) % n, 0) for k in range(n)]
    for j in range(rings - 1):
        up, lo = 1 + j * n, 1 + (j + 1) * n
        for k in range(n):
            k1 = (k + 1) % n
            f.append((lo + k, lo + k1, up + k1, up + k))
    return v, f


def solid(name, sections, material, loc=(0, 0, 0), rot=(0, 0, 0), n=24, sharp=60):
    v, f = loft_geom(sections, n)
    return bs._make(name, v, f, material, loc, rot, smooth=True, sharp=math.radians(sharp))


def aim(direction):
    """Euler rotation that turns +z to point along direction."""
    return Vector((0, 0, 1)).rotation_difference(Vector(direction).normalized()).to_euler()


# ---------------------------------------------------------------- figures

class Figure:
    """Joints are empties named <name>_<joint>; parts are parented to them in joint space."""

    def __init__(self, name):
        self.name = name
        self.j = {}
        self.joint("root", None, (0, 0, 0))

    def joint(self, key, parent, loc):
        e = bpy.data.objects.new(f"{self.name}_{key}", None)
        bs._link(e)
        e.empty_display_type, e.empty_display_size = "PLAIN_AXES", 0.04
        if parent:
            e.parent = self.j[parent]
        e.location = loc
        self.j[key] = e
        return e

    def add(self, key, ob):
        ob.parent = self.j[key]
        return ob

    def pose(self, **rot):
        for key, r in rot.items():
            self.j[key].rotation_euler = Euler([math.radians(a) for a in r])

    def place(self, xy, yaw):
        self.j["root"].location = (xy[0], xy[1], 0)
        self.j["root"].rotation_euler = (0, 0, math.radians(yaw))


def torso_surface(sections, x, z, side=-1.0):
    """The y of a loft's surface at (x, z), on the front (side -1) or back (+1)."""
    for a, b in zip(sections, sections[1:]):
        if a[0] <= z <= b[0]:
            t = (z - a[0]) / (b[0] - a[0])
            rx, ry = a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])
            return side * ry * math.sqrt(max(0.0, 1 - (x / rx) ** 2))
    raise ValueError(z)


def build_figure(s, eyes=False):
    """Legs, torso, arms, head and hair from a spec; returns the Figure."""
    F = Figure(s["name"])
    N = s["name"].upper()
    top, rib, bottom, shoe, sole = (cmat(k) for k in (s["top"], s["rib"], s["bottom"], s["shoe"], s["sole"]))
    skin, hair = cmat("skin", rough=0.6), cmat(s["hair"], rough=0.9)

    # drop lowers everything above the hips and shortens the legs to match: game proportions
    # (a larger head on a shorter body) without moving any of the measurements below
    hz, sz, drop = s["hip_z"], s["spine_z"], s.get("drop", 0.0)
    k = (hz - drop - ANKLE) / (hz - ANKLE)
    thigh, shin = (s["thigh"][0] * k, *s["thigh"][1:]), (s["shin"][0] * k, *s["shin"][1:])
    ak = s.get("arm_scale", 1.0)
    upper, fore = (s["upper"][0] * ak, *s["upper"][1:]), (s["fore"][0] * ak, *s["fore"][1:])
    F.joint("hips", "root", (0, 0, hz - drop))
    F.joint("spine", "hips", (0, 0, sz - hz))
    torso = [(z - sz, rx, ry) for z, rx, ry in s["torso"]]
    F.add("spine", solid(f"{N}_torso", torso, top, n=32))
    F.add("hips", solid(f"{N}_pelvis", [(z - hz, rx, ry) for z, rx, ry in s["pelvis"]], bottom, n=28))

    # legs
    for side, sx in (("R", -1), ("L", 1)):
        F.joint(f"hip_{side}", "hips", (sx * s["hip_x"], 0, 0))
        F.joint(f"knee_{side}", f"hip_{side}", (0, 0, -thigh[0]))
        F.joint(f"ankle_{side}", f"knee_{side}", (0, 0, -shin[0]))
        F.add(f"hip_{side}", solid(f"{N}_thigh_{side}", capsule(*thigh, aspect=0.94), bottom, n=20))
        F.add(f"knee_{side}", solid(f"{N}_shin_{side}", capsule(*shin, aspect=0.96, flat_end=True), bottom, n=20))
        for name, secs, m in s["shoe_parts"](shoe, sole):
            F.add(f"ankle_{side}", solid(f"{N}_{name}_{side}", secs, m, n=24))
    F.shin = shin

    # arms
    shx, shz = s["shoulder"]
    for side, sx in (("R", -1), ("L", 1)):
        F.joint(f"shoulder_{side}", "spine", (sx * shx, 0, shz - sz))
        F.joint(f"elbow_{side}", f"shoulder_{side}", (0, 0, -upper[0]))
        F.joint(f"wrist_{side}", f"elbow_{side}", (0, 0, -fore[0]))
        F.add(f"shoulder_{side}", solid(f"{N}_upper_{side}", capsule(*upper), top, n=18))
        F.add(f"elbow_{side}", solid(f"{N}_fore_{side}", capsule(*fore, flat_end=True), top, n=18))
        L = fore[0]
        for name, z0, z1, r, m in s["cuffs"]:
            e = min(0.004, (z1 - z0) / 4)       # rounded edges, so a sleeve end reads as an opening
            secs = [(-L + z0, r * 0.9, r * 0.9), (-L + z0 + e, r, r), (-L + z1 - e, r * 0.98, r * 0.98),
                    (-L + z1, r * 0.84, r * 0.84)]
            F.add(f"elbow_{side}", solid(f"{N}_{name}_{side}", secs, {"rib": rib, "shirt": cmat("shirt")}[m], n=18))
        F.add(f"wrist_{side}", solid(f"{N}_hand_{side}", ellipsoid(-0.05, 0.021, 0.034, 0.048, rings=8), skin, n=16))
        F.add(f"wrist_{side}", solid(f"{N}_wrist_{side}", [(-0.02, 0.019, 0.024), (0.03, 0.022, 0.026)], skin, n=14))
        thumb = solid(f"{N}_thumb_{side}", capsule(0.026, 0.011, 0.009), skin, loc=(0, -0.026, -0.022),
                      rot=(math.radians(-30), 0, 0), n=10)
        F.add(f"wrist_{side}", thumb)

    # neck and head
    nz, hdz = s["neck_z"], s["head_z"]
    F.joint("neck", "spine", (0, -0.008, nz - sz))
    F.joint("head", "neck", (0, 0, hdz - nz))
    F.add("neck", solid(f"{N}_neck", [(-0.03, 0.04, 0.038), (hdz - nz + 0.03, 0.036, 0.035)], skin, n=16))
    hs = s.get("head_scale", 1.0)
    hx, hy, hzr, hc = s["head"]
    hc += hzr * (hs - 1)              # a larger head grows upward from the chin
    hx, hy, hzr = hx * hs, hy * hs, hzr * hs
    F.add("head", solid(f"{N}_head", ellipsoid(hc, hx, hy, hzr, rings=14, jaw=s.get("jaw", 0.9)), skin, n=32))
    for sx in (-1, 1):
        ear = solid(f"{N}_ear_{'R' if sx < 0 else 'L'}", ellipsoid(0, 0.011 * hs, 0.021 * hs, 0.03 * hs, rings=6), skin,
                    loc=(sx * (hx - 0.004), 0.008, hc - 0.012 * hs), rot=(0, 0, sx * math.radians(-12)), n=12)
        F.add("head", ear)
    grow, cut = s["hair_shape"]
    v, f = hair_geom(hx + grow, hy + grow, hzr + grow, cut, part=s.get("hair_part", 0.0))
    cap = bs._make(f"{N}_hair", v, f, hair, loc=(0, s.get("hair_dy", 0.0), hc + s.get("hair_dz", 0.0)),
                   smooth=True, sharp=math.radians(80))
    mod = cap.modifiers.new("solidify", "SOLIDIFY")
    mod.thickness, mod.offset = 0.016, -1.0
    F.add("head", cap)
    if eyes:
        eye = cmat("eye", rough=0.3)
        for sx in (-1, 1):
            x, z = sx * s["eye"][0] * hs, hc + s["eye"][1] * hs

            def surf(x, z):
                return -hy * math.sqrt(max(0.0, 1 - (x / hx) ** 2 - ((z - hc) / hzr) ** 2))
            F.add("head", solid(f"{N}_eye_{sx}", ellipsoid(0, 0.0095, 0.006, s["eye"][2], rings=6), eye,
                                loc=(x, surf(x, z) + 0.0025, z), rot=(0, 0, sx * math.radians(18)), n=12))
            if s.get("brows"):
                zb = z + 0.032
                F.add("head", solid(f"{N}_brow_{sx}", capsule(0.024, 0.0042, 0.0042), cmat("brow"),
                                    loc=(x + 0.012, surf(x, zb) + 0.003, zb), rot=(0, math.radians(90 + sx * 4), 0), n=8))
    F.torso = s["torso"]
    return F


def oxford(shoe, sole):
    """A plain leather shoe, toe towards -y; the ankle joint is 0.085 above the floor."""
    up = [(-0.072, 0.050, 0.122, 0, -0.037), (-0.05, 0.050, 0.121, 0, -0.036), (-0.028, 0.046, 0.106, 0, -0.026),
          (-0.008, 0.040, 0.078, 0, -0.008), (0.010, 0.036, 0.052, 0, 0.004)]
    base = [(-0.085, 0.052, 0.126, 0, -0.037), (-0.072, 0.053, 0.127, 0, -0.037)]
    return [("shoe", up, shoe), ("sole", base, sole)]


def sneaker(shoe, sole):
    up = [(-0.064, 0.054, 0.126, 0, -0.036), (-0.04, 0.054, 0.124, 0, -0.035), (-0.018, 0.049, 0.108, 0, -0.024),
          (0.002, 0.043, 0.080, 0, -0.006), (0.022, 0.039, 0.056, 0, 0.006)]
    base = [(-0.085, 0.056, 0.130, 0, -0.037), (-0.062, 0.057, 0.131, 0, -0.037)]
    return [("shoe", up, shoe), ("sole", base, sole)]


SAYNO = dict(
    name="sayno", top="cardigan", rib="cardigan_rib", bottom="slacks", shoe="shoe", sole="sole",
    hair="sayno_hair", hip_z=0.82, spine_z=0.92, neck_z=1.31, head_z=1.345, hip_x=0.078,
    torso=[(0.79, 0.143, 0.101), (0.83, 0.143, 0.101), (0.90, 0.137, 0.094), (0.98, 0.131, 0.089),
           (1.07, 0.139, 0.095), (1.15, 0.150, 0.101), (1.21, 0.156, 0.099), (1.25, 0.148, 0.091),
           (1.28, 0.118, 0.075), (1.30, 0.074, 0.057), (1.312, 0.05, 0.045)],
    pelvis=[(0.73, 0.06, 0.05), (0.76, 0.118, 0.084), (0.84, 0.124, 0.088)],
    thigh=(0.36, 0.058, 0.052), shin=(0.375, 0.051, 0.047),
    shoe_parts=oxford, shoulder=(0.162, 1.222), upper=(0.27, 0.046, 0.041), fore=(0.235, 0.041, 0.036),
    cuffs=[("cuff", -0.03, -0.004, 0.0395, "rib"), ("shirt_cuff", -0.004, 0.012, 0.0345, "shirt")],
    head=(0.106, 0.114, 0.138, 0.11), jaw=0.86, hair_shape=(0.009, (50, 92, 118)), eye=(0.038, -0.012, 0.014),
    brows=True, drop=0.07, head_scale=1.12, arm_scale=0.95,
)

VISITOR = dict(
    name="visitor", top="sweater", rib="sweater_rib", bottom="jeans", shoe="sneaker", sole="sneaker_sole",
    hair="visitor_hair", hip_z=0.78, spine_z=0.87, neck_z=1.255, head_z=1.29, hip_x=0.08,
    torso=[(0.765, 0.150, 0.108), (0.80, 0.153, 0.110), (0.88, 0.146, 0.103), (0.97, 0.146, 0.103),
           (1.06, 0.153, 0.107), (1.12, 0.157, 0.105), (1.17, 0.150, 0.097), (1.205, 0.124, 0.080),
           (1.235, 0.078, 0.060), (1.25, 0.05, 0.046)],
    pelvis=[(0.69, 0.06, 0.05), (0.72, 0.124, 0.09), (0.80, 0.13, 0.094)],
    thigh=(0.345, 0.062, 0.055), shin=(0.35, 0.054, 0.049),
    shoe_parts=sneaker, shoulder=(0.158, 1.168), upper=(0.255, 0.048, 0.043), fore=(0.22, 0.043, 0.038),
    cuffs=[("cuff", -0.035, 0.002, 0.042, "rib")],
    head=(0.116, 0.122, 0.146, 0.12), jaw=0.9, hair_shape=(0.016, (72, 100, 120)), hair_dy=0.006, hair_part=10,
    eye=(0.042, -0.018, 0.016), drop=0.075, head_scale=1.15, arm_scale=0.95,
)


# ---------------------------------------------------------------- posing

def update():
    bpy.context.view_layer.update()


def basis(x, normal):
    """Rotation whose z is normal and whose x runs as close to x as it can."""
    z = Vector(normal).normalized()
    x = Vector(x)
    x = (x - x.dot(z) * z).normalized()
    return Matrix((x, z.cross(x), z)).transposed()


def turn_to(a_local, a_world, b_local, b_world):
    """Rotation taking a_local exactly onto a_world and b_local as near b_world as it can."""
    def fr(a, b):
        a = Vector(a).normalized()
        c = a.cross(Vector(b)).normalized()
        return Matrix((a, c, a.cross(c))).transposed()
    return fr(a_world, b_world) @ fr(a_local, b_local).transposed()


def hand_frame(fingers, palm, side):
    """World rotation for a hand from where its fingers point and where its palm faces. The
    hands hang palm-in with the thumb forward, so the palm is +x on the right hand, -x on the left."""
    return turn_to((0, 0, -1), fingers, (1 if side == "R" else -1, 0, 0), palm)


def orient(joint, world_rot):
    update()
    parent = joint.parent.matrix_world.to_3x3().normalized()
    joint.rotation_euler = (parent.inverted() @ world_rot).to_euler()


def reach(F, side, target, pole):
    """Turn the shoulder and bend the elbow so the wrist lands on target (world), the elbow
    pointing towards pole (a world direction)."""
    update()
    sh, el, wr = F.j[f"shoulder_{side}"], F.j[f"elbow_{side}"], F.j[f"wrist_{side}"]
    L1, L2 = -el.location.z, -wr.location.z
    S, T = sh.matrix_world.translation.copy(), Vector(target)
    d = min((T - S).length, (L1 + L2) * 0.999)
    t = (T - S).normalized()
    p = Vector(pole) - Vector(pole).dot(t) * t
    p.normalize()
    a = math.acos(max(-1.0, min(1.0, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
    u = math.cos(a) * t + math.sin(a) * p
    f = (S + d * t - (S + L1 * u)).normalized()
    z = -u
    x = u.cross(f)
    x = x.normalized() if x.length > 1e-6 else u.orthogonal().normalized()
    R = Matrix((x, z.cross(x), z)).transposed()
    parent = sh.parent.matrix_world.to_3x3().normalized()
    sh.rotation_euler = (parent.inverted() @ R).to_euler()
    fl = R.inverted() @ f
    el.rotation_euler = (math.atan2(fl.y, -fl.z), 0, 0)


def hold(F, side, point, local_point, world_rot, pole=None):
    """Turn the hand to world_rot and bring the arm round so local_point (wrist space) lands on point."""
    wrist = Vector(point) - world_rot @ Vector(local_point)
    reach(F, side, wrist, pole or ((-1 if side == "R" else 1) * 0.8, 0.5, -1.0))
    orient(F.j[f"wrist_{side}"], world_rot)


def attach(ob, joint):
    """Re-parent, keeping where it is."""
    update()
    mw = ob.matrix_world.copy()
    ob.parent = joint
    ob.matrix_world = mw


# ---------------------------------------------------------------- what they wear and carry

PEN_NIB = Vector((0.0, -0.022, -0.104))                      # the nib, in right-hand (wrist) space
PEN_BACK = Vector((-0.42, -0.5, 0.76)).normalized()          # from the nib back over the web of the hand


def sayno_props(F):
    """Cardigan front, shirt collar, buttons and pockets; a metal watch; a fountain pen and a notebook."""
    N, sz = "SAYNO", SAYNO["spine_z"]
    secs = [(z - sz, rx, ry) for z, rx, ry in F.torso]
    shirt, rib, btn = cmat("shirt", rough=0.85), cmat("cardigan_rib"), cmat("button", rough=0.5)
    za, zt, w = 1.08 - sz, 1.272 - sz, 0.056

    def front(x, z, lift=0.0):
        return (x, torso_surface(secs, x, z) - lift, z)

    rows, cols = 9, 7
    v = [front(w * j / (rows - 1) * (2 * i / (cols - 1) - 1), za + (zt - za) * j / (rows - 1), 0.0025)
         for j in range(rows) for i in range(cols)]
    f = [(j * cols + i, j * cols + i + 1, (j + 1) * cols + i + 1, (j + 1) * cols + i)
         for j in range(rows - 1) for i in range(cols - 1)]
    F.add("spine", bs._make(f"{N}_shirt_front", v, f, shirt, smooth=True))
    for sx in (-1, 1):
        edge = [front(sx * w * (z - za) / (zt - za), z, 0.004) for z in [za + (zt - za) * t / 8 for t in range(9)]]
        F.add("spine", bs.tube(f"{N}_placket_{sx}", edge, 0.0085, rib, n=8))
    line = [front(0, z, 0.004) for z in [0.795 - sz + (za - 0.795 + sz) * t / 6 for t in range(7)]]
    F.add("spine", bs.tube(f"{N}_placket_mid", line, 0.0085, rib, n=8))
    for k, z in enumerate((1.05, 0.985, 0.92, 0.855)):
        p = front(0, z - sz, 0.012)
        F.add("spine", bs.cyl(f"{N}_button_{k}", 0.0085, 0.006, p, btn, n=12, rot=(math.pi / 2, 0, 0)))
    for sx in (-1, 1):
        x, z = sx * 0.072, 0.875 - sz
        y = torso_surface(secs, x, z)
        ry_, rx_ = 0.093, 0.136
        slope = (ry_ * x / rx_ ** 2) / math.sqrt(max(1e-6, 1 - (x / rx_) ** 2))
        F.add("spine", bs.box(f"{N}_pocket_{sx}", (0.07, 0.006, 0.075), (x, y - 0.002, z), rib, bevel=0.002,
                              rot=(0, 0, math.atan(slope))))
    # shirt collar round the neck
    F.add("neck", solid(f"{N}_collar", [(-0.028, 0.058, 0.05, 0, -0.004), (0.012, 0.047, 0.042, 0, -0.004)], shirt, n=24))

    # metal watch on the left wrist, face on the back of the wrist
    steel, dial = cmat("steel", rough=0.3, metal=1.0), cmat("dial", rough=0.4)
    F.add("wrist_L", solid(f"{N}_watch_band", [(-0.019, 0.03, 0.033), (-0.003, 0.03, 0.033)], steel, n=20))
    F.add("wrist_L", bs.cyl(f"{N}_watch_case", 0.019, 0.009, (0.03, 0, -0.011), steel, n=20, rot=(0, math.pi / 2, 0)))
    F.add("wrist_L", bs.cyl(f"{N}_watch_dial", 0.015, 0.002, (0.0352, 0, -0.011), dial, n=20, rot=(0, math.pi / 2, 0)))

    # fountain pen in the right hand: black, gold nib, band and clip (drawn a little large to read)
    pen, gold = cmat("pen", rough=0.18), cmat("gold", rough=0.25, metal=1.0)
    L = 0.17
    body = [(-L / 2, 0.0, 0.0), (-L / 2 + 0.003, 0.0058, 0.0058), (-L / 2 + 0.01, 0.0082, 0.0082),
            (0.03, 0.0082, 0.0082), (0.048, 0.0071, 0.0071), (0.056, 0.0062, 0.0062)]
    nib = [(0.056, 0.0052, 0.0034), (L / 2, 0.0004, 0.0003)]
    loc = PEN_NIB + PEN_BACK * (L / 2)
    rot = aim(-PEN_BACK)
    parts = {}
    for name, secs_, m in (("pen", body, pen), ("pen_nib", nib, gold),
                           ("pen_band", [(-0.004, 0.0088, 0.0088), (0.004, 0.0088, 0.0088)], gold),
                           ("pen_top", [(-L / 2 - 0.002, 0.0, 0.0), (-L / 2 + 0.002, 0.0048, 0.0048),
                                        (-L / 2 + 0.008, 0.006, 0.006)], gold)):
        parts[name] = F.add("wrist_R", solid(f"{N}_{name}", secs_, m, loc=loc, rot=rot, n=14))
    clip = bs.box(f"{N}_pen_clip", (0.003, 0.002, 0.055), (0, -0.0092, -0.05), gold, bevel=0.0007, segs=1)
    clip.parent = parts["pen"]

    # a small notebook, open: leather cover and two pages with a few lines already written
    book = bpy.data.objects.new(f"{N}_notebook", None)
    bs._link(book)
    book.parent = F.j["root"]
    cover, page, ink = cmat("notebook", rough=0.7), cmat("page", rough=0.9), cmat("eye", rough=0.5)
    bits = [bs.box(f"{N}_nb_cover", (0.24, 0.165, 0.005), (0, 0, -0.0065), cover, bevel=0.002, segs=2)]
    for sx in (-1, 1):
        bits.append(bs.box(f"{N}_nb_page_{sx}", (0.112, 0.152, 0.008), (sx * 0.058, 0, -0.0005), page,
                           bevel=0.0015, segs=1, rot=(0, sx * math.radians(-3), 0)))
    lines = bs.Batch(f"{N}_nb_ink")
    for k, wl in enumerate((0.08, 0.072, 0.085, 0.05, 0.078, 0.064, 0.03)):
        lines.box((wl, 0.0024, 0.0008), (0.058 - 0.04 + wl / 2 - 0.0, 0.055 - k * 0.017, 0.0042), ink,
                  rot=(0, math.radians(-3), 0))
    for k, wl in enumerate((0.07, 0.04)):
        lines.box((wl, 0.0024, 0.0008), (-0.058 - 0.04 + wl / 2, 0.055 - k * 0.017, 0.0042), ink,
                  rot=(0, math.radians(3), 0))
    bits.append(lines.make())
    for b in bits:
        b.parent = book
    F.notebook = book
    return F


def visitor_props(F):
    """Crew neck and hem ribbing, rolled jeans, and the letter."""
    N, sz = "VISITOR", VISITOR["spine_z"]
    rib = cmat("sweater_rib")
    F.add("spine", solid(f"{N}_hem", [(0.762 - sz, 0.154, 0.112), (0.81 - sz, 0.156, 0.113)], rib, n=32))
    F.add("neck", solid(f"{N}_crew", [(-0.024, 0.066, 0.058, 0, -0.002), (0.004, 0.056, 0.05, 0, -0.004)], rib, n=24))
    cuff = cmat("jeans_cuff")
    for side in "RL":
        L = F.shin[0]
        F.add(f"knee_{side}", solid(f"{N}_jean_cuff_{side}", [(-L + 0.012, 0.056, 0.054), (-L + 0.045, 0.057, 0.055)],
                                    cuff, n=20))
    env, flap, seal = cmat("envelope", rough=0.9), cmat("envelope_flap", rough=0.9), cmat("seal", rough=0.45)
    letter = bpy.data.objects.new(f"{N}_letter", None)
    bs._link(letter)
    letter.parent = F.j["root"]
    for ob in (bs.box(f"{N}_envelope", (0.18, 0.122, 0.006), (0, 0, 0), env, bevel=0.0015, segs=1),
               bs._make(f"{N}_envelope_flap", [(-0.088, 0.059, 0.0035), (0.088, 0.059, 0.0035), (0.0, -0.006, 0.0035)],
                        [(0, 2, 1)], flap),
               bs.cyl(f"{N}_seal", 0.0135, 0.004, (0, 0.0, 0.005), seal, n=16)):
        ob.parent = letter
    F.letter = letter
    return F


def make_sayno(eyes=False):
    """Standing, writing in his notebook with the fountain pen."""
    F = sayno_props(build_figure(SAYNO, eyes))
    F.pose(spine=(4, 0, 0), neck=(9, 0, 0), head=(16, 0, -4), hip_R=(-2, 0, 0), hip_L=(3, 0, 0), knee_R=(4, 0, 0))
    update()
    zc = F.j["spine"].matrix_world.translation.z + 0.13
    n = Vector((0.05, 0.62, 0.78)).normalized()                # the page faces him and the ceiling
    F.notebook.matrix_world = Matrix.Translation((0.035, -0.255, zc)) @ basis((1, 0, -0.05), n).to_4x4()
    update()
    B = F.notebook.matrix_world
    Br = B.to_3x3()
    hold(F, "L", B @ Vector((0.07, 0.0, -0.034)), (0, 0, -0.05),
         hand_frame(Br @ Vector((-1, 0.1, 0)), Br @ Vector((0, 0, 1)), "L"), pole=(1, 0.6, -1))
    attach(F.notebook, F.j["wrist_L"])
    nib = B @ Vector((-0.06, 0.012, 0.0045))
    R = turn_to(PEN_BACK, Vector((-0.45, 0.42, 0.79)), (0, 0, -1), Vector((0.2, -0.5, -0.84)))
    hold(F, "R", nib, PEN_NIB, R, pole=(-1, 0.7, -0.8))
    return F


def make_visitor(eyes=False):
    """Standing with the letter in both hands."""
    F = visitor_props(build_figure(VISITOR, eyes))
    F.pose(neck=(-2, 0, 0), head=(5, 0, 0), hip_R=(1, 0, 0), hip_L=(-1, 0, 0))
    update()
    zc = F.j["spine"].matrix_world.translation.z + 0.12
    n = Vector((0, -0.93, 0.36)).normalized()                  # the front of the envelope, forward and up
    F.letter.matrix_world = Matrix.Translation((0, -0.215, zc)) @ basis((1, 0, 0), n).to_4x4()
    update()
    E = F.letter.matrix_world
    Er = E.to_3x3()
    for side, sx in (("R", -1), ("L", 1)):
        fingers = Er @ Vector((-sx * 0.35, 0.94, 0.0))
        palm = Er @ Vector((-sx, 0, 0.0))
        hold(F, side, E @ Vector((sx * 0.083, -0.012, -0.004)), (0, 0, -0.05), hand_frame(fingers, palm, side))
    return F


# ---------------------------------------------------------------- stages

PAPER = (238, 226, 210)


def plain_stage():
    """Paper-coloured world, a shadow-catching floor and three soft lights."""
    scene = bpy.context.scene
    world = bpy.data.worlds.new("WORLD_sheet")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*srgb(*PAPER), 1)
    bg.inputs["Strength"].default_value = 0.55
    scene.world = world
    floor = bs._make("FLOOR", [(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)], [(0, 1, 2, 3)],
                     bs.mat("floor_sheet", color=(0.6, 0.6, 0.6)))
    floor.is_shadow_catcher = True
    for name, loc, energy, size, color, shadow in (
            ("key", (-1.8, -2.6, 4.6), 700, 3.2, (1.0, 0.93, 0.84), True),
            ("fill", (3.4, -2.4, 1.8), 170, 3.0, (0.86, 0.90, 1.0), False),
            ("rim", (0.6, 3.2, 3.0), 300, 1.6, (1.0, 0.95, 0.9), False)):
        ob = bs._light("LGT_" + name, "AREA", loc)
        ob.data.energy, ob.data.size, ob.data.color = energy, size, color
        ob.data.use_shadow = shadow
        ob.rotation_euler = (Vector((0, 0, 0.9)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def camera(name, loc, target, lens=None, ortho=None):
    data = bpy.data.cameras.new(name)
    if ortho:
        data.type, data.ortho_scale = "ORTHO", ortho
    else:
        data.lens = lens
    cam = bpy.data.objects.new(name, data)
    bs._link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bs._mats.clear()
    bs.COLL = None


def rename(F, k):
    """Give one figure's objects a suffix, so the next figure can use the plain names."""
    for ob in list(bpy.data.objects):
        if ob.name.startswith(F.name + "_") or ob.name.startswith(F.name.upper() + "_"):
            ob.name = f"{ob.name}_{k}"


EYES = {"none": (False, False), "visitor": (False, True), "both": (True, True)}   # (Sayno, visitor)


def sheet(eyes="visitor"):
    fresh()
    plain_stage()
    bs.COLL = bs._collection("CHARACTERS")
    s = make_sayno(EYES[eyes][0])
    rename(s, 0)
    s.place((-0.4, 0.0), 24)
    v = make_visitor(EYES[eyes][1])
    v.place((0.4, -0.05), -26)
    camera("CAM_sheet", (0.0, -5.0, 1.45), (0.0, 0.0, 0.8), lens=62)


def faces():
    fresh()
    plain_stage()
    bs.COLL = bs._collection("CHARACTERS")
    for k, (maker, eyes, x) in enumerate(((make_sayno, False, -0.85), (make_sayno, True, -0.29),
                                          (make_visitor, False, 0.29), (make_visitor, True, 0.85))):
        F = maker(eyes)
        rename(F, k)
        F.place((x, 0.0), 14 if x < 0 else -14)
    camera("CAM_faces", (0.0, -4.3, 1.5), (0.0, 0.0, 1.2), lens=70)


def in_study(mood="dusk", eyes="visitor", close=False):
    """Both figures in the study, seen from the game's camera. They stand on a line across the
    screen, each turned a little towards the camera, the way actors cheat out on a stage."""
    fresh()
    bs.build_study(detail=True, mood=mood)
    bs.COLL = bs._collection("CHARACTERS")
    s = make_sayno(EYES[eyes][0])
    rename(s, 0)
    s.place((-0.55, 1.15), -10)
    v = make_visitor(EYES[eyes][1])
    v.place((-1.45, 0.25), 100)
    if close:
        cam = bpy.data.objects["CAM_main"]
        cam.data.ortho_scale = 3.0
        d = (Vector((-0.1, 0.4, 1.0)) - cam.location).normalized()
        target = Vector((-1.0, 0.7, 0.8))
        cam.location = target - d * 14.0


def render(path, samples, res):
    bs.render(path, samples, res)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet")
    ap.add_argument("--faces")
    ap.add_argument("--study")
    ap.add_argument("--close", action="store_true")
    ap.add_argument("--mood", default="dusk", choices=list(bs.MOODS))
    ap.add_argument("--eyes", default="visitor", choices=list(EYES), help="who has dot eyes")
    ap.add_argument("--save")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--res", default="1600x1200")
    a = ap.parse_args(argv)
    res = tuple(int(v) for v in a.res.split("x"))
    if a.sheet:
        sheet(a.eyes)
        render(a.sheet, a.samples, res)
    if a.faces:
        faces()
        render(a.faces, a.samples, res)
    if a.study:
        in_study(a.mood, a.eyes, a.close)
        render(a.study, a.samples, res)
    if a.save:
        sheet(a.eyes)
        bpy.ops.wm.save_as_mainfile(filepath=a.save)


if __name__ == "__main__":
    main()
