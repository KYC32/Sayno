"""Build Sayno's study as a diorama with Blender's Python API.

The same file runs in two places:

- Here, with the `bpy` package, to render mood previews or save a .blend:
      python3 blender/build_study.py --mood dusk --out renders/dusk.png
      python3 blender/build_study.py --save blender/study.blend
  blender/export_glb.py imports it with detail=True, bakes the procedural surfaces and
  ambient occlusion into textures and exports the web model.
- In a hosted Blender (Higgsfield 3D Jutsu), pasted into a scene edit and run as
  build_study(), with plain colours so the scene's own GLB viewer shows them.

Every clickable object is an empty (letter, calendar, desk_papers, ...) whose children are its
parts; the web app finds them by these names. Everything else is the room.
"""
import argparse
import math
import random
import sys

import bpy
from mathutils import Euler, Matrix, Vector

DETAIL = False                # procedural surface detail for baking; plain colours otherwise
rng = random.Random(7)        # layout
tag_rng = random.Random(11)   # per-part texture offsets, kept apart so the layout never depends on DETAIL
COLL = None                   # collection new objects go into

ROOM, WALL_H, T = 6.0, 3.2, 0.2
X0, Y1 = -3.0, 3.0            # inner faces of the left and back walls
XF, YF = 3.06, -3.06          # open front edges of the floor
S = 0.81                      # desk surface height

# ---------------------------------------------------------------- materials

PALETTE = {
    "plinth": (0.17, 0.11, 0.07),
    "floor_a": (0.50, 0.32, 0.18), "floor_b": (0.45, 0.28, 0.15), "floor_c": (0.55, 0.36, 0.21),
    "plaster": (0.86, 0.79, 0.68),
    "wainscot": (0.31, 0.37, 0.36),
    "trim": (0.88, 0.83, 0.72),
    "frame": (0.22, 0.14, 0.08),
    "desk": (0.31, 0.18, 0.10),
    "desk_dark": (0.20, 0.12, 0.07),
    "shelf": (0.34, 0.21, 0.12),
    "cabinet": (0.43, 0.28, 0.16),
    "chair": (0.36, 0.22, 0.12),
    "cushion": (0.52, 0.30, 0.18),
    "plywood": (0.74, 0.58, 0.38),
    "steel": (0.42, 0.44, 0.44),
    "slot": (0.05, 0.05, 0.05),
    "paper": (0.92, 0.89, 0.80),
    "paper_old": (0.84, 0.78, 0.62),
    "manila": (0.80, 0.66, 0.42),
    "ink": (0.06, 0.06, 0.08),
    "pen_blue": (0.14, 0.24, 0.62),
    "rule": (0.62, 0.66, 0.74),
    "brass": (0.72, 0.52, 0.22),
    "black_metal": (0.05, 0.05, 0.06),
    "leather": (0.13, 0.24, 0.18),
    "lampshade": (0.16, 0.34, 0.24),
    "bulb": (1.0, 0.75, 0.42),
    "armchair": (0.30, 0.36, 0.30),
    "throw": (0.60, 0.22, 0.16),
    "porcelain": (0.92, 0.90, 0.86),
    "tea": (0.35, 0.18, 0.06),
    "shade2": (0.88, 0.80, 0.62),
    "rug": (0.50, 0.19, 0.14), "rug_edge": (0.80, 0.68, 0.46), "rug_accent": (0.17, 0.23, 0.33),
    "pot": (0.64, 0.37, 0.24), "soil": (0.15, 0.10, 0.07),
    "leaf": (0.15, 0.30, 0.14), "leaf_light": (0.22, 0.38, 0.17), "stem": (0.30, 0.30, 0.16),
    "curtain": (0.86, 0.80, 0.67),
    "pin": (0.72, 0.12, 0.10),
    "label": (0.90, 0.86, 0.74),
    "band_gold": (0.72, 0.56, 0.26),
}
BOOK_COLORS = [(0.45, 0.14, 0.12), (0.16, 0.25, 0.38), (0.24, 0.34, 0.22), (0.62, 0.48, 0.26),
               (0.30, 0.20, 0.14), (0.72, 0.64, 0.50), (0.20, 0.20, 0.22), (0.52, 0.30, 0.18),
               (0.36, 0.10, 0.14), (0.40, 0.46, 0.50)]
MAG_COLORS = [(0.70, 0.20, 0.15), (0.85, 0.80, 0.70), (0.20, 0.30, 0.50), (0.15, 0.15, 0.17),
              (0.75, 0.55, 0.20), (0.30, 0.45, 0.55)]
DETAIL_KIND = {
    "plinth": "wood", "floor_a": "wood", "floor_b": "wood", "floor_c": "wood", "desk": "wood",
    "desk_dark": "wood", "shelf": "wood", "cabinet": "wood", "chair": "wood", "plywood": "wood",
    "frame": "wood", "plaster": "plaster", "wainscot": "paint", "trim": "paint", "paper": "paper",
    "paper_old": "paper", "manila": "paper", "label": "paper", "leather": "leather", "cushion": "leather",
    "armchair": "fabric", "throw": "plaid", "shade2": "fabric", "curtain": "fabric", "rug": "fabric",
    "rug_edge": "fabric", "rug_accent": "fabric", "steel": "metal", "brass": "metal", "pot": "plaster",
    "leaf": "leaf", "leaf_light": "leaf", "porcelain": "paper",
}

_mats = {}


def mat(name, color=None, rough=0.75, metal=0.0, emit=0.0, detail=None):
    """One material per name. The web app looks some up by name (bulb, lampshade, shade2)."""
    if name in _mats:
        return _mats[name]
    color = color or PALETTE[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*color, 1)
        bsdf.inputs["Emission Strength"].default_value = emit
    kind = detail or DETAIL_KIND.get(name)
    if DETAIL and kind:
        _detail(m, kind, color)
    _mats[name] = m
    return m


def _sock(sockets, ident):
    return next(s for s in sockets if s.identifier == ident)


def _detail(m, kind, color):
    """Procedural surface variation, read through each part's own coordinates ("pc") and
    random value ("pr"). Only used for baking; glTF cannot carry these nodes."""
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]
    pc = N.new("ShaderNodeAttribute")
    pc.attribute_name = "pc"
    pr = N.new("ShaderNodeAttribute")
    pr.attribute_name = "pr"

    def vec(stretch):
        mp = N.new("ShaderNodeVectorMath")
        mp.operation = "MULTIPLY"
        L.new(pc.outputs["Vector"], mp.inputs[0])
        mp.inputs[1].default_value = stretch
        return mp.outputs["Vector"]

    def noise(scale, detail=3.0, stretch=(1, 1, 1), rough=0.55):
        n = N.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        L.new(vec(stretch), n.inputs["Vector"])
        return n.outputs["Fac"]

    def wave(kind_, scale, distortion, stretch=(1, 1, 1), direction="X"):
        w = N.new("ShaderNodeTexWave")
        w.wave_type = kind_
        if kind_ == "RINGS":
            w.rings_direction = direction
        else:
            w.bands_direction = direction
        w.inputs["Scale"].default_value = scale
        w.inputs["Distortion"].default_value = distortion
        w.inputs["Detail"].default_value = 2.0
        L.new(vec(stretch), w.inputs["Vector"])
        return w.outputs["Fac"]

    def grey(fac, lo, hi, a=0.0, b=1.0, constant=False):
        r = N.new("ShaderNodeValToRGB")
        if constant:
            r.color_ramp.interpolation = "CONSTANT"
        e0, e1 = r.color_ramp.elements
        e0.position, e1.position = a, b
        e0.color = (lo, lo, lo, 1)
        e1.color = (hi, hi, hi, 1)
        L.new(fac, r.inputs["Fac"])
        return r.outputs["Color"]

    def mul(a, b):
        mx = N.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.blend_type = "MULTIPLY"
        mx.inputs[0].default_value = 1.0
        L.new(a, _sock(mx.inputs, "A_Color"))
        L.new(b, _sock(mx.inputs, "B_Color"))
        return _sock(mx.outputs, "Result_Color")

    if kind == "wood":
        f = mul(grey(wave("RINGS", 3.0, 4.0, (0.35, 7, 7)), 0.84, 1.1),
                grey(noise(1.5, 4, (0.25, 9, 9)), 0.88, 1.1, 0.3, 0.7))
        f = mul(f, grey(pr.outputs["Fac"], 0.9, 1.1))
    elif kind == "fabric":
        f = mul(grey(noise(40, 6, rough=0.65), 0.9, 1.06), grey(noise(4, 2), 0.95, 1.04))
    elif kind == "plaid":
        stripes = mul(grey(wave("BANDS", 9, 0, (1, 1, 1), "X"), 0.75, 1.0, 0.45, 0.55),
                      grey(wave("BANDS", 9, 0, (1, 1, 1), "Y"), 0.8, 1.0, 0.45, 0.55))
        f = mul(stripes, grey(noise(40, 5), 0.92, 1.05))
    elif kind == "plaster":
        f = mul(grey(noise(2.5, 3), 0.93, 1.05), grey(noise(45, 4), 0.96, 1.03))
    elif kind == "paint":
        f = grey(noise(10, 3), 0.95, 1.04)
    elif kind == "paper":
        f = grey(noise(30, 4), 0.96, 1.02)
    elif kind == "leather":
        f = mul(grey(noise(25, 6, rough=0.7), 0.84, 1.08), grey(noise(3, 2), 0.94, 1.05))
    elif kind == "metal":
        f = grey(noise(12, 5), 0.82, 1.1)
    elif kind == "leaf":
        f = mul(grey(noise(18, 3), 0.88, 1.1), grey(pr.outputs["Fac"], 0.85, 1.15))
    else:
        return
    rgb = N.new("ShaderNodeRGB")
    rgb.outputs[0].default_value = (*color, 1)
    L.new(mul(rgb.outputs[0], f), bsdf.inputs["Base Color"])


# ---------------------------------------------------------------- geometry helpers

BOX_FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def box_verts(sx, sy, sz):
    x, y, z = sx / 2, sy / 2, sz / 2
    return [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
            (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]


def _tag_part(verts):
    """A part's own coordinates with its longest side along x, offset at random, and a random
    value: wood grain then runs along each board and no two boards look alike."""
    ext = [max(v[i] for v in verts) - min(v[i] for v in verts) for i in range(3)]
    order = sorted(range(3), key=lambda i: -ext[i])
    off = [tag_rng.uniform(0, 40) for _ in range(3)]
    pc = [(v[order[0]] + off[0], v[order[1]] + off[1], v[order[2]] + off[2]) for v in verts]
    return pc, tag_rng.random()


def _link(ob):
    (COLL or bpy.context.scene.collection).objects.link(ob)


def _make(name, verts, faces, materials, loc=(0, 0, 0), rot=(0, 0, 0), bevel=0.0, segs=2,
          smooth=False, sharp=None, mat_index=None, tags=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    for m in (materials if isinstance(materials, (list, tuple)) else [materials]):
        me.materials.append(m)
    if mat_index:
        me.polygons.foreach_set("material_index", mat_index)
    if DETAIL:
        if tags is None:
            pc, pr = _tag_part(verts)
            tags = (pc, [pr] * len(verts))
        a = me.attributes.new("pc", "FLOAT_VECTOR", "POINT")
        a.data.foreach_set("vector", [c for p in tags[0] for c in p])
        b = me.attributes.new("pr", "FLOAT", "POINT")
        b.data.foreach_set("value", tags[1])
    me.update()
    ob = bpy.data.objects.new(name, me)
    _link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = segs
        mod.limit_method = "ANGLE"
        mod.harden_normals = True
        smooth = True
    if smooth:
        me.shade_smooth()
        if sharp is not None:
            me.set_sharp_from_angle(angle=sharp)
    return ob


def box(name, size, loc, material, bevel=0.01, segs=2, rot=(0, 0, 0)):
    return _make(name, box_verts(*size), BOX_FACES, material, loc, rot, bevel, segs)


def cyl_geom(r1, h, n, r2=None):
    r2 = r1 if r2 is None else r2
    ring = [(math.cos(k / n * math.tau), math.sin(k / n * math.tau)) for k in range(n)]
    v = [(r1 * c, r1 * s, -h / 2) for c, s in ring] + [(r2 * c, r2 * s, h / 2) for c, s in ring]
    f = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    f += [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    return v, f


def cyl(name, r, depth, loc, material, n=24, rot=(0, 0, 0), bevel=0.0, segs=2, r2=None):
    v, f = cyl_geom(r, depth, n, r2)
    return _make(name, v, f, material, loc, rot, bevel, segs, smooth=True, sharp=math.radians(50))


def lathe_geom(profile, n):
    """Revolve (radius, height) points around z; a zero radius closes the end. The profile runs
    counter-clockwise (out along the bottom, up the outside), so the faces point outward."""
    v, f, rings = [], [], []
    for r, z in profile:
        if r < 1e-6:
            rings.append([len(v)])
            v.append((0.0, 0.0, z))
        else:
            rings.append(list(range(len(v), len(v) + n)))
            v += [(r * math.cos(k / n * math.tau), r * math.sin(k / n * math.tau), z) for k in range(n)]
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
    return v, f


def lathe(name, profile, loc, material, n=32, rot=(0, 0, 0), sharp=40):
    v, f = lathe_geom(profile, n)
    return _make(name, v, f, material, loc, rot, smooth=True, sharp=math.radians(sharp))


def tube_geom(points, r, n=8, caps=True):
    """A round tube along a polyline, framed by parallel transport so it never twists."""
    P = [Vector(p) for p in points]
    tang = [(P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized() for i in range(len(P))]
    ref = Vector((0, 0, 1)) if abs(tang[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = tang[0].cross(ref).normalized()
    v, f = [], []
    for i, p in enumerate(P):
        if i:
            axis = tang[i - 1].cross(tang[i])
            if axis.length > 1e-9:
                nrm = Matrix.Rotation(tang[i - 1].angle(tang[i]), 3, axis.normalized()) @ nrm
        bi = tang[i].cross(nrm).normalized()
        nrm = bi.cross(tang[i]).normalized()
        rr = r[i] if isinstance(r, (list, tuple)) else r
        for k in range(n):
            a = k / n * math.tau
            v.append(tuple(p + rr * (math.cos(a) * nrm + math.sin(a) * bi)))
    m = len(P)
    for i in range(m - 1):
        for k in range(n):
            k1 = (k + 1) % n
            f.append((i * n + k, i * n + k1, (i + 1) * n + k1, (i + 1) * n + k))
    if caps:
        f.append(tuple(reversed(range(n))))
        f.append(tuple(range((m - 1) * n, m * n)))
    return v, f


def _centred(v):
    c = sum((Vector(p) for p in v), Vector()) / len(v)
    return [tuple(Vector(p) - c) for p in v], tuple(c)


def tube(name, points, r, material, n=8, caps=True):
    v, f = tube_geom(points, r, n, caps)
    v, c = _centred(v)
    return _make(name, v, f, material, loc=c, smooth=True, sharp=math.radians(70))


def sheet(name, rows, material, thickness, sharp=None):
    """A surface through a grid of points (rows of equal length), thickened by Solidify."""
    nr, nc = len(rows), len(rows[0])
    v = [p for row in rows for p in row]
    f = [(j * nc + i, (j + 1) * nc + i, (j + 1) * nc + i + 1, j * nc + i + 1)
         for j in range(nr - 1) for i in range(nc - 1)]
    v, c = _centred(v)
    ob = _make(name, v, f, material, loc=c, smooth=True, sharp=sharp)
    mod = ob.modifiers.new("solidify", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 0.0
    return ob


def prism_xz(name, poly, y0, y1, material, loc=(0, 0, 0)):
    """Extrude a polygon drawn counter-clockwise in the x-z plane (x right, z up) along y."""
    n = len(poly)
    v = [(x, y0, z) for x, z in poly] + [(x, y1, z) for x, z in poly]
    f = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    f += [(i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n)]
    return _make(name, v, f, material, loc, smooth=True, sharp=math.radians(35))


class Batch:
    """Many small parts in one object (books on a shelf, slots in steel, ruled lines)."""

    def __init__(self, name):
        self.name = name
        self.v, self.f, self.mi, self.mats, self.pc, self.pr = [], [], [], [], [], []

    def add(self, verts, faces, material, loc=(0, 0, 0), rot=(0, 0, 0)):
        if material not in self.mats:
            self.mats.append(material)
        R, t, base = Euler(rot).to_matrix(), Vector(loc), len(self.v)
        self.v += [tuple(R @ Vector(p) + t) for p in verts]
        self.f += [tuple(base + i for i in fc) for fc in faces]
        self.mi += [self.mats.index(material)] * len(faces)
        if DETAIL:
            pc, pr = _tag_part(verts)
            self.pc += pc
            self.pr += [pr] * len(verts)

    def box(self, size, loc, material, rot=(0, 0, 0)):
        self.add(box_verts(*size), BOX_FACES, material, loc, rot)

    def make(self, bevel=0.0, segs=1, smooth=False):
        if not self.v:
            return None
        return _make(self.name, self.v, self.f, self.mats, bevel=bevel, segs=segs, smooth=smooth,
                     mat_index=self.mi, tags=(self.pc, self.pr) if DETAIL else None)


def group(name, objs):
    """Parent parts under an empty named for the web app."""
    empty = bpy.data.objects.new(name, None)
    _link(empty)
    for o in objs:
        if o is not None:
            o.parent = empty
    return empty


def turn(objs, pivot, rot):
    """Rotate already placed parts about a pivot."""
    M = (Matrix.Translation(pivot) @ Euler(rot).to_matrix().to_4x4()
         @ Matrix.Translation(-Vector(pivot)))
    for o in objs:
        if o is not None:
            o.matrix_basis = M @ o.matrix_basis


def on(centre, yaw, local):
    """A point given in a part's frame (rotated by yaw about z) in world space."""
    return tuple(Euler((0, 0, yaw)).to_matrix() @ Vector(local) + Vector(centre))


# ---------------------------------------------------------------- the room

def wall_with_window(name, xr, yr, zr, hx, hz, material):
    """A wall slab along x with a rectangular opening, as one clean mesh (no boolean)."""
    xs, zs = [xr[0], hx[0], hx[1], xr[1]], [zr[0], hz[0], hz[1], zr[1]]
    v, f = [], []

    def vid(i, j, side):
        return side * 16 + j * 4 + i

    for side, y in enumerate(yr):
        for j in range(4):
            for i in range(4):
                v.append((xs[i], y, zs[j]))
    for j in range(3):
        for i in range(3):
            if i == 1 and j == 1:
                continue
            f.append((vid(i, j, 0), vid(i + 1, j, 0), vid(i + 1, j + 1, 0), vid(i, j + 1, 0)))
            f.append((vid(i, j, 1), vid(i, j + 1, 1), vid(i + 1, j + 1, 1), vid(i + 1, j, 1)))
    for i in range(3):   # bottom and top
        f.append((vid(i, 0, 0), vid(i, 0, 1), vid(i + 1, 0, 1), vid(i + 1, 0, 0)))
        f.append((vid(i, 3, 0), vid(i + 1, 3, 0), vid(i + 1, 3, 1), vid(i, 3, 1)))
    for j in range(3):   # left and right ends
        f.append((vid(0, j, 0), vid(0, j + 1, 0), vid(0, j + 1, 1), vid(0, j, 1)))
        f.append((vid(3, j, 0), vid(3, j, 1), vid(3, j + 1, 1), vid(3, j + 1, 0)))
    # the reveal around the opening
    f.append((vid(1, 1, 0), vid(2, 1, 0), vid(2, 1, 1), vid(1, 1, 1)))   # sill
    f.append((vid(1, 2, 0), vid(1, 2, 1), vid(2, 2, 1), vid(2, 2, 0)))   # head
    f.append((vid(1, 1, 0), vid(1, 1, 1), vid(1, 2, 1), vid(1, 2, 0)))   # left jamb
    f.append((vid(2, 1, 0), vid(2, 2, 0), vid(2, 2, 1), vid(2, 1, 1)))   # right jamb
    return _make(name, v, f, material, bevel=0.01, segs=2)


def wainscot(prefix, along, u0, u1, plane):
    """Painted panelling to chair height: along "x" for the back wall, "y" for the left wall."""
    paint, trim = mat("wainscot", rough=0.6), mat("trim", rough=0.55)

    def wbox(name, a, b, w0, w1, z0, z1, m, bevel=0.004):
        if along == "x":
            return box(name, (b - a, w1 - w0, z1 - z0), ((a + b) / 2, plane - (w0 + w1) / 2, (z0 + z1) / 2),
                       m, bevel=bevel)
        return box(name, (w1 - w0, b - a, z1 - z0), (plane + (w0 + w1) / 2, (a + b) / 2, (z0 + z1) / 2),
                   m, bevel=bevel)

    wbox(prefix + "_board", u0, u1, 0, 0.012, 0, 0.86, paint, bevel=0)
    wbox(prefix + "_skirting", u0, u1, 0, 0.024, 0, 0.13, paint)
    wbox(prefix + "_rail", u0, u1, 0, 0.022, 0.80, 0.86, paint)
    wbox(prefix + "_cap", u0, u1, 0, 0.036, 0.86, 0.90, trim, bevel=0.008)
    n = max(1, round((u1 - u0) / 0.62))
    for k in range(n + 1):
        u = u0 + (u1 - u0) * k / n
        a, b = max(u0, u - 0.035), min(u1, u + 0.035)
        wbox(f"{prefix}_stile_{k}", a, b, 0, 0.022, 0.13, 0.80, paint)


def build_room():
    """Floor boards on a dark plinth, two plaster walls over panelled wainscot, a window."""
    box("ENV_plinth", (XF + 0.02 - (X0 - T), Y1 + T - (YF - 0.02), 0.2),
        ((XF + 0.02 + X0 - T) / 2, (Y1 + T + YF - 0.02) / 2, -0.12), mat("plinth"), bevel=0.02, segs=3)

    boards = Batch("ENV_floorboards")
    tones = [mat("floor_a", rough=0.6), mat("floor_b", rough=0.6), mat("floor_c", rough=0.6)]
    rows = 30
    pitch = (XF - X0) / rows
    for i in range(rows):
        x, y, first = X0 + pitch * (i + 0.5), YF, True
        while y < Y1 - 0.01:
            length = min(rng.uniform(0.4, 1.6) if first else rng.uniform(1.1, 2.3), Y1 - y)
            first = False
            boards.box((pitch - 0.004, length - 0.004, 0.02), (x, y + length / 2, -0.01), rng.choice(tones))
            y += length
    boards.make(bevel=0.0025, segs=1)

    plaster, cap = mat("plaster", rough=0.9), mat("plinth")
    wall_with_window("ENV_wall_back", (X0 - T, XF - 0.02), (Y1, Y1 + T), (-0.02, WALL_H),
                     (0.9, 2.2), (1.25, 2.45), plaster)
    box("ENV_wall_left", (T, Y1 - (YF + 0.02), WALL_H + 0.02),
        (X0 - T / 2, (Y1 + YF + 0.02) / 2, (WALL_H - 0.02) / 2), plaster, bevel=0.01)
    box("ENV_cap_back", (XF - 0.02 - (X0 - T) + 0.02, T + 0.02, 0.03),
        ((XF - 0.02 + X0 - T) / 2, Y1 + T / 2, WALL_H + 0.015), cap, bevel=0.006)
    box("ENV_cap_left", (T + 0.02, Y1 - (YF + 0.02), 0.03),
        (X0 - T / 2, (Y1 + YF + 0.02) / 2, WALL_H + 0.015), cap, bevel=0.006)
    wainscot("ENV_wains_back", "x", X0, XF - 0.02, Y1)
    wainscot("ENV_wains_left", "y", YF + 0.02, Y1, X0)
    build_window()
    build_clock()


def build_window():
    fm, br = mat("frame", rough=0.6), mat("brass", rough=0.35, metal=0.85)
    x0, x1, z0, z1 = 0.9, 2.2, 1.25, 2.45
    xc = (x0 + x1) / 2
    box("WIN_casing_top", (x1 - x0 + 0.16, 0.025, 0.08), (xc, Y1 - 0.0125, z1 + 0.04), fm, bevel=0.006)
    box("WIN_casing_l", (0.08, 0.025, z1 - z0), (x0 - 0.04, Y1 - 0.0125, (z0 + z1) / 2), fm, bevel=0.006)
    box("WIN_casing_r", (0.08, 0.025, z1 - z0), (x1 + 0.04, Y1 - 0.0125, (z0 + z1) / 2), fm, bevel=0.006)
    box("WIN_sill", (x1 - x0 + 0.24, 0.18, 0.04), (xc, Y1 + 0.01, z0 - 0.02), fm, bevel=0.008, segs=3)
    box("WIN_apron", (x1 - x0 + 0.12, 0.025, 0.08), (xc, Y1 - 0.0125, z0 - 0.08), fm, bevel=0.005)
    ys, w = Y1 + 0.12, 0.055
    box("WIN_sash_top", (x1 - x0, 0.04, w), (xc, ys, z1 - w / 2), fm, bevel=0.004)
    box("WIN_sash_bot", (x1 - x0, 0.04, w), (xc, ys, z0 + w / 2), fm, bevel=0.004)
    box("WIN_sash_l", (w, 0.04, z1 - z0 - 2 * w), (x0 + w / 2, ys, (z0 + z1) / 2), fm, bevel=0.004)
    box("WIN_sash_r", (w, 0.04, z1 - z0 - 2 * w), (x1 - w / 2, ys, (z0 + z1) / 2), fm, bevel=0.004)
    box("WIN_mullion_v", (0.035, 0.036, z1 - z0 - 2 * w), (xc, ys, (z0 + z1) / 2), fm, bevel=0.003)
    box("WIN_mullion_h", (x1 - x0 - 2 * w, 0.036, 0.035), (xc, ys, 1.95), fm, bevel=0.003)

    # curtain rod on brackets, and two linen panels gathered at the sides
    rz, ry = 2.62, Y1 - 0.12
    cyl("WIN_rod", 0.011, 2.0, (xc, ry, rz), br, n=16, rot=(0, math.pi / 2, 0))
    for i, x in enumerate((xc - 1.0, xc + 1.0)):
        lathe(f"WIN_finial_{i}", [(0, 0), (0.016, 0.004), (0.022, 0.02), (0.016, 0.034), (0, 0.04)],
              (x, ry, rz), br, n=16, rot=(0, math.pi / 2 * (1 if x > xc else -1), 0))
    for i, x in enumerate((xc - 0.87, xc + 0.87)):
        box(f"WIN_bracket_{i}", (0.02, 0.12, 0.02), (x, ry + 0.06, rz), br, bevel=0.004)
    cm = mat("curtain", rough=0.95)
    for i, (xa, xb) in enumerate(((0.6, 1.0), (2.1, 2.5))):
        rows, folds, nx, nz = [], 5, 30, 10
        for j in range(nz + 1):
            t = j / nz
            z = 2.6 - (2.6 - 1.08) * t
            amp = 0.014 + 0.016 * t
            row = []
            for k in range(nx + 1):
                s = k / nx
                hem = 0.012 * math.sin(s * folds * math.tau + 1.3) if j == nz else 0.0
                row.append((xa + (xb - xa) * s, ry - 0.005 + amp * math.sin(s * folds * math.tau), z + hem))
            rows.append(row)
        sheet(f"WIN_curtain_{i}", rows, cm, 0.008)


def build_clock():
    """A wall clock on the left wall; the web app turns its hands to the visitor's time."""
    br, face, ink = mat("brass", rough=0.35, metal=0.85), mat("label"), mat("ink")
    cy_, cz = -2.2, 2.0
    rot = (0, math.pi / 2, 0)   # lathe axis z -> +x, out of the wall
    lathe("CLOCK_rim", [(0, 0), (0.165, 0), (0.17, 0.02), (0.163, 0.04), (0.152, 0.042), (0.15, 0.036), (0, 0.036)],
          (X0, cy_, cz), br, n=48, rot=rot)
    lathe("CLOCK_face", [(0, 0.035), (0.151, 0.035), (0.151, 0.037), (0, 0.037)], (X0, cy_, cz), face, n=48,
          rot=rot)
    ticks = Batch("CLOCK_ticks")
    for k in range(12):
        a = k / 12 * math.tau
        big = k % 3 == 0
        ticks.box((0.002, 0.008 if big else 0.005, 0.026 if big else 0.016),
                  (X0 + 0.0378, cy_ + 0.125 * math.sin(a), cz + 0.125 * math.cos(a)), ink, rot=(-a, 0, 0))
    ticks.make()
    # hands point at twelve; each keeps its pivot at the centre so it can be turned
    for name, length, width, off in (("clock_hour", 0.075, 0.009, 0.0385), ("clock_minute", 0.115, 0.006, 0.0395)):
        h = _make(name, box_verts(0.0015, width, length), BOX_FACES, ink, loc=(X0 + off, cy_, cz))
        for v in h.data.vertices:
            v.co.z += length / 2 - 0.015
        h["keep"] = True
    lathe("CLOCK_pin", [(0, 0.037), (0.008, 0.037), (0.008, 0.043), (0, 0.044)], (X0, cy_, cz), br, n=16, rot=rot)


# ---------------------------------------------------------------- the desk

def pull(name, loc, m, w=0.11):
    """A bar handle standing off a drawer front that faces -y."""
    x, y, z = loc
    return [cyl(name + "_bar", 0.0065, w, (x, y - 0.016, z), m, n=12, rot=(0, math.pi / 2, 0)),
            cyl(name + "_p0", 0.0045, 0.02, (x - w / 2 + 0.012, y - 0.006, z), m, n=8, rot=(math.pi / 2, 0, 0)),
            cyl(name + "_p1", 0.0045, 0.02, (x + w / 2 - 0.012, y - 0.006, z), m, n=8, rot=(math.pi / 2, 0, 0))]


def paper_stack(name, x, y, n, mats, size=(0.25, 0.34), spin=0.0, z=S):
    b = Batch(name)
    for _ in range(n):
        th = rng.uniform(0.006, 0.016)
        b.box((size[0], size[1], th), (x + rng.uniform(-0.012, 0.012), y + rng.uniform(-0.012, 0.012), z + th / 2),
              rng.choice(mats), rot=(0, 0, math.radians(spin + rng.uniform(-5, 5))))
        z += th
    return b.make(), z


def glasses(name, centre, yaw, z):
    """Reading glasses folded on the papers: the owner has only stepped out."""
    m = mat("black_metal", rough=0.4, metal=0.6)
    parts = []
    for i, sx in enumerate((-1, 1)):
        ring = [on(centre, yaw, (sx * 0.031 + 0.024 * math.cos(a / 16 * math.tau), 0.019 * math.sin(a / 16 * math.tau), 0))
                for a in range(17)]
        parts.append(tube(f"{name}_rim_{i}", [(p[0], p[1], z + 0.003) for p in ring], 0.0016, m, n=6, caps=False))
        parts.append(tube(f"{name}_arm_{i}", [on(centre, yaw, (sx * 0.054, 0.004, 0)),
                                              on(centre, yaw, (sx * 0.05, 0.016, 0)),
                                              on(centre, yaw, (-sx * 0.035, 0.02, 0))], 0.0013, m, n=6))
        parts[-1].location.z = z + 0.006
    bridge = [on(centre, yaw, (0.009 * math.cos(a / 8 * math.pi + math.pi), 0.006 * math.sin(a / 8 * math.pi), 0))
              for a in range(9)]
    parts.append(tube(f"{name}_bridge", [(p[0], p[1], z + 0.004) for p in bridge], 0.0015, m, n=6))
    return parts


def build_desk():
    """The owner's desk, buried in papers (a clean desk belongs to a mafia boss or a crook, p.179)."""
    dm, dd = mat("desk", rough=0.55), mat("desk_dark", rough=0.6)
    br = mat("brass", rough=0.35, metal=0.85)
    cx, cy = 0.1, 2.35
    yf = cy - 0.43                    # pedestal fronts
    parts = [box("DESK_top", (2.0, 0.95, 0.05), (cx, cy, S - 0.025), dm, bevel=0.012, segs=3),
             box("DESK_apron", (0.92, 0.86, 0.08), (cx, cy, 0.72), dm, bevel=0.006),
             box("DESK_modesty", (0.92, 0.02, 0.55), (cx, cy + 0.41, 0.40), dm, bevel=0.004),
             box("DESK_drawer_mid", (0.88, 0.022, 0.065), (cx, yf - 0.011, 0.715), dm, bevel=0.005)]
    parts += pull("DESK_pull_mid", (cx, yf - 0.022, 0.715), br, w=0.13)
    for i, px in enumerate((-0.61, 0.81)):
        parts.append(box(f"DESK_pedestal_{i}", (0.5, 0.86, 0.70), (px, cy, 0.41), dm, bevel=0.008))
        parts.append(box(f"DESK_plinth_{i}", (0.46, 0.80, 0.06), (px, cy + 0.02, 0.03), dd, bevel=0.004))
        for k, (z0, z1) in enumerate(((0.08, 0.30), (0.32, 0.52), (0.54, 0.74))):
            zc = (z0 + z1) / 2
            parts.append(box(f"DESK_drawer_{i}{k}", (0.46, 0.022, z1 - z0 - 0.02), (px, yf - 0.011, zc), dm,
                             bevel=0.006))
            parts += pull(f"DESK_pull_{i}{k}", (px, yf - 0.022, zc + 0.03), br)

    pm, po, mn = mat("paper"), mat("paper_old"), mat("manila")
    papers = [pm, pm, pm, po]
    a, za = paper_stack("PAP_stack_a", -0.62, 2.58, 12, papers, spin=4)
    b, _ = paper_stack("PAP_stack_b", -0.36, 2.34, 7, papers + [mn], spin=-6)
    c, zc = paper_stack("PAP_stack_c", 0.62, 2.60, 15, papers, spin=3)
    d, zd = paper_stack("PAP_stack_d", 0.82, 2.18, 5, papers, spin=-10)
    e, _ = paper_stack("PAP_stack_e", -0.78, 2.12, 3, [po, mn], size=(0.21, 0.30), spin=8)
    parts += [a, b, c, d, e]
    for k, (col, spin) in enumerate((((0.55, 0.20, 0.15), 8), ((0.20, 0.30, 0.45), 1), ((0.70, 0.55, 0.25), -6))):
        fm = mat(f"folder{k}", col, rough=0.7, detail="paper")
        z = zc + 0.004 + k * 0.009
        parts.append(box(f"PAP_folder_{k}", (0.27, 0.36, 0.006), (0.61, 2.6, z), fm, bevel=0.0015, segs=1,
                         rot=(0, 0, math.radians(spin))))
        parts.append(box(f"PAP_tab_{k}", (0.07, 0.03, 0.006), on((0.61, 2.6, z), math.radians(spin), (0.06 - k * 0.07, -0.19, 0)),
                         fm, bevel=0.0015, segs=1, rot=(0, 0, math.radians(spin))))
    # a black binder clip on the left pile
    bk = mat("black_metal", rough=0.4, metal=0.6)
    clip = on((-0.62, 2.58, 0), math.radians(4), (0.0, -0.165, 0))
    parts.append(box("PAP_clip", (0.045, 0.018, 0.012), (clip[0], clip[1], za - 0.004), bk, bevel=0.003))
    for s in (-1, 1):
        parts.append(tube(f"PAP_clip_wire_{s}", [(clip[0] + s * 0.016, clip[1], za + 0.002),
                                                  (clip[0] + s * 0.016, clip[1] - 0.012, za + 0.016),
                                                  (clip[0] + s * 0.012, clip[1] - 0.03, za + 0.02)], 0.0012, br, n=5))
    parts += glasses("PAP_glasses", (0.82, 2.17, 0), math.radians(-20), zd)
    # three hardcover books, the top one a little askew
    z = S
    for k, (col, th, spin) in enumerate((((0.16, 0.25, 0.38), 0.035, 2), ((0.45, 0.14, 0.12), 0.03, -4),
                                         ((0.62, 0.48, 0.26), 0.028, 9))):
        bm = mat(f"desk_book{k}", col, rough=0.8, detail="fabric")
        parts.append(box(f"PAP_book_{k}", (0.24, 0.17, th), (0.97, 2.62, z + th / 2), bm, bevel=0.003,
                         rot=(0, 0, math.radians(spin))))
        parts.append(box(f"PAP_book_pages_{k}", (0.232, 0.162, th - 0.006),
                         on((0.97, 2.62, z + th / 2), math.radians(spin), (0.006, 0, 0)), pm, bevel=0,
                         rot=(0, 0, math.radians(spin))))
        z += th
    # a pen cup
    parts.append(lathe("PAP_pencup", [(0, 0), (0.036, 0), (0.038, 0.004), (0.038, 0.1), (0.034, 0.1), (0.034, 0.008),
                                      (0, 0.008)], (0.12, 2.62, S), mat("leather", rough=0.6), n=24))
    for k, (col, tilt, az) in enumerate((("ink", 10, 30), ("pen_blue", 14, 160), ("pencil", 8, 260))):
        m = mat(col, (0.82, 0.62, 0.20), rough=0.5) if col == "pencil" else mat(col, rough=0.35)
        parts.append(cyl(f"PAP_pen_{k}", 0.0045, 0.16, (0.12 + 0.012 * math.cos(math.radians(az)),
                                                         2.62 + 0.012 * math.sin(math.radians(az)), S + 0.095),
                         m, n=8, rot=(math.radians(tilt), 0, math.radians(az))))
    group("desk_papers", parts)

    build_lamp()
    build_letter()
    build_calendar()
    build_chair()


def build_lamp():
    """An articulated desk lamp with a green enamel shade (the web app lights it at night)."""
    br, shade, bulb = (mat("brass", rough=0.35, metal=0.85), mat("lampshade", rough=0.35),
                       mat("bulb", emit=6.0))
    bx, by = -0.15, 2.66
    head = Vector((bx, 2.455, 1.33))
    tilt = math.radians(-25)
    R = Euler((tilt, 0, 0)).to_matrix()
    neck = head + R @ Vector((0, 0, 0.07))
    elbow = Vector((bx, 2.76, 1.30))
    base_top = Vector((bx, by, S + 0.05))
    parts = [
        lathe("LAMP_base", [(0, 0), (0.09, 0), (0.092, 0.006), (0.086, 0.02), (0.05, 0.034), (0.022, 0.044),
                            (0.018, 0.05), (0, 0.05)], (bx, by, S), br, n=32),
        tube("LAMP_arm_low", [base_top, base_top.lerp(elbow, 0.5), elbow], 0.008, br, n=10),
        tube("LAMP_arm_up", [elbow, elbow.lerp(neck, 0.5), neck], 0.007, br, n=10),
        cyl("LAMP_elbow", 0.016, 0.036, tuple(elbow), br, n=16, rot=(0, math.pi / 2, 0)),
        lathe("LAMP_shade", [(0.016, 0.075), (0.016, 0.07), (0.026, 0.038), (0.06, -0.004), (0.104, -0.072),
                             (0.116, -0.095), (0.122, -0.095), (0.112, -0.072), (0.066, 0.0), (0.03, 0.045),
                             (0.022, 0.075)], tuple(head), shade, n=40, rot=(tilt, 0, 0)),
        lathe("LAMP_bulb", [(0, -0.075), (0.02, -0.07), (0.03, -0.05), (0.026, -0.03), (0.012, -0.015), (0, -0.012)],
              tuple(head), bulb, n=20, rot=(tilt, 0, 0)),
        tube("LAMP_cord", [(bx + 0.02, by + 0.07, S + 0.01), (bx + 0.06, by + 0.13, S + 0.004),
                           (bx + 0.14, 2.8, S + 0.004), (bx + 0.2, 2.86, S - 0.04)], 0.004, mat("ink"), n=6),
    ]
    group("lamp", parts)


def build_letter():
    """Letter paper on a leather blotter at the front of the desk: where the visitor writes."""
    pm, rule, ink = mat("paper"), mat("rule"), mat("ink", rough=0.35)
    parts = [box("LET_blotter", (0.62, 0.40, 0.005), (0.15, 2.12, S + 0.0025), mat("leather", rough=0.6),
                 bevel=0.0015, segs=1)]
    for i, sx in enumerate((-1, 1)):
        parts.append(box(f"LET_blotter_end_{i}", (0.045, 0.41, 0.008), (0.15 + sx * 0.3, 2.12, S + 0.004),
                         mat("desk_dark"), bevel=0.002))
    centre, yaw = (0.13, 2.10, S + 0.006), math.radians(-7)
    parts.append(box("LET_sheet", (0.25, 0.34, 0.002), centre, pm, bevel=0, rot=(0, 0, yaw)))
    lines = Batch("LET_lines")
    for j in range(8):
        lines.box((0.2, 0.0016, 0.0004), on(centre, yaw, (0, 0.12 - j * 0.034, 0.0012)), rule, rot=(0, 0, yaw))
    parts.append(lines.make())
    # a fountain pen, its cap posted, with a brass band
    pen_rot = (0, math.pi / 2, math.radians(30))
    pen_at = (0.36, 2.05, S + 0.005 + 0.0078)
    parts.append(lathe("LET_pen", [(0, -0.07), (0.004, -0.069), (0.0072, -0.064), (0.0078, -0.03), (0.0078, 0.02),
                                   (0.0072, 0.026), (0.0066, 0.045), (0.0045, 0.056), (0.002, 0.066), (0.0004, 0.07)],
                       pen_at, ink, n=16, rot=pen_rot))
    parts.append(cyl("LET_pen_band", 0.0081, 0.004, pen_at, mat("brass", rough=0.35, metal=0.85), n=16,
                     rot=pen_rot))
    parts[-1].location = Vector(pen_at) + Euler(pen_rot).to_matrix() @ Vector((0, 0, 0.022))
    # an envelope waiting for the letter
    env_c, env_yaw = (0.33, 2.25, S + 0.0065), math.radians(10)
    parts.append(box("LET_envelope", (0.22, 0.11, 0.003), env_c, mat("paper_old"), bevel=0, rot=(0, 0, env_yaw)))
    tri = [(-0.11, 0.055, 0.0018), (0.11, 0.055, 0.0018), (0.0, -0.012, 0.0018)]
    flap = [on(env_c, env_yaw, p) for p in tri]
    parts.append(_make("LET_envelope_flap", flap, [(0, 2, 1)], mat("manila")))
    group("letter", parts)


def build_calendar():
    """A tear-off daily calendar (일력) on a small wooden stand."""
    cx, cy = -0.55, 2.0
    fm, pm, red, ink = mat("frame", rough=0.6), mat("paper"), mat("pin", rough=0.5), mat("ink")
    base = box("CAL_base", (0.17, 0.09, 0.025), (cx, cy + 0.005, S + 0.0125), fm, bevel=0.004)
    z0 = S + 0.025
    pad = [box("CAL_board", (0.16, 0.012, 0.24), (cx, cy + 0.036, z0 + 0.12), fm, bevel=0.003),
           box("CAL_pad", (0.15, 0.028, 0.2), (cx, cy + 0.016, z0 + 0.105), pm, bevel=0.002, segs=1),
           box("CAL_header", (0.152, 0.03, 0.032), (cx, cy + 0.016, z0 + 0.19), red, bevel=0.002, segs=1)]
    marks, date = Batch("CAL_marks"), Batch("CAL_date")   # the web page writes today's date in place of CAL_date
    yfront = cy + 0.0015
    seg = {"a": (0, 0.03, 1), "g": (0, 0, 1), "d": (0, -0.03, 1), "f": (-0.014, 0.015, 0), "b": (0.014, 0.015, 0),
           "e": (-0.014, -0.015, 0), "c": (0.014, -0.015, 0)}
    for dx, digit in ((-0.02, "abged"), (0.02, "bc")):   # a big "21", seven-segment style
        for k in digit:
            sx, sz, flat = seg[k]
            date.box((0.028, 0.001, 0.007) if flat else (0.007, 0.001, 0.03), (cx + dx + sx, yfront, z0 + 0.115 + sz), ink)
    for k in range(3):
        marks.box((0.1 - k * 0.02, 0.001, 0.005), (cx, yfront, z0 + 0.055 - k * 0.012), ink)
    pad += [marks.make(), date.make()]
    turn(pad, (cx, cy + 0.03, z0), (math.radians(-12), 0, 0))
    group("calendar", [base] + pad)


def build_chair():
    """A wooden desk chair, pushed back as if someone just got up."""
    wd, cu = mat("chair", rough=0.55), mat("cushion", rough=0.7)
    cx, cy, sz = 0.2, 1.45, 0.45
    parts = [box("CHAIR_seat", (0.46, 0.44, 0.035), (cx, cy, sz), wd, bevel=0.01, segs=3),
             box("CHAIR_cushion", (0.40, 0.38, 0.035), (cx, cy + 0.01, sz + 0.035), cu, bevel=0.014, segs=3)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(cyl(f"CHAIR_leg_{sx}{sy}", 0.016, sz - 0.0175, (cx + sx * 0.19, cy + sy * 0.18, (sz - 0.0175) / 2),
                             wd, n=12, r2=0.021))
        parts.append(cyl(f"CHAIR_rung_y{sx}", 0.008, 0.36, (cx + sx * 0.19, cy, 0.12), wd, n=10, rot=(math.pi / 2, 0, 0)))
    for sy in (-1, 1):
        parts.append(cyl(f"CHAIR_rung_x{sy}", 0.008, 0.38, (cx, cy + sy * 0.18, 0.16), wd, n=10, rot=(0, math.pi / 2, 0)))
    yb, zb = cy - 0.18, sz + 0.0175
    back = [box(f"CHAIR_post_{sx}", (0.035, 0.035, 0.45), (cx + sx * 0.19, yb, zb + 0.225), wd, bevel=0.006)
            for sx in (-1, 1)]
    back += [box("CHAIR_crest", (0.44, 0.03, 0.085), (cx, yb, zb + 0.41), wd, bevel=0.01, segs=3),
             box("CHAIR_rail", (0.38, 0.022, 0.03), (cx, yb, zb + 0.12), wd, bevel=0.005)]
    back += [cyl(f"CHAIR_spindle_{k}", 0.009, 0.25, (cx + k * 0.09, yb, zb + 0.255), wd, n=10) for k in (-1, 0, 1)]
    turn(back, (cx, yb, zb), (math.radians(8), 0, 0))
    parts += back
    turn(parts, (cx, cy, 0), (0, 0, math.radians(6)))
    group("chair", parts)


# ---------------------------------------------------------------- the angle bench

def build_angle_bench():
    """Slotted steel angle with a plywood top: the desk built to save money (p.218)."""
    st, pw, sl = mat("steel", rough=0.45, metal=0.7), mat("plywood", rough=0.7), mat("slot", rough=0.8)
    cx, cy, w, d, hgt = 2.3, 2.45, 1.0, 0.7, 0.74
    fl, th, low = 0.045, 0.004, 0.17
    parts, slots = [], Batch("BENCH_slots")
    yfront, xright = cy - d / 2, cx + w / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            X, Y = cx + sx * w / 2, cy + sy * d / 2
            parts.append(box(f"BENCH_leg_{sx}{sy}a", (fl, th, hgt), (X - sx * fl / 2, Y - sy * th / 2, hgt / 2), st,
                             bevel=0.0012, segs=1))
            parts.append(box(f"BENCH_leg_{sx}{sy}b", (th, fl, hgt), (X - sx * th / 2, Y - sy * fl / 2, hgt / 2), st,
                             bevel=0.0012, segs=1))
            for k in range(13):
                z = 0.045 + k * 0.053
                if sy < 0:
                    slots.box((0.011, 0.0008, 0.026), (X - sx * fl / 2, Y - 0.0004, z), sl)
                if sx > 0:
                    slots.box((0.0008, 0.011, 0.026), (X + 0.0004, Y - sy * fl / 2, z), sl)
    for z in (low, hgt):     # rails bolt on behind the leg flanges, so they sit one thickness in
        for sy in (-1, 1):   # front and back rails along x
            Y = cy + sy * (d / 2 - th)
            parts.append(box(f"BENCH_rail_x{sy}_{z:.2f}v", (w - 2 * th, th, fl), (cx, Y - sy * th / 2, z - fl / 2), st,
                             bevel=0.0012, segs=1))
            parts.append(box(f"BENCH_rail_x{sy}_{z:.2f}h", (w - 2 * th, fl, th), (cx, Y - sy * fl / 2, z - th / 2), st,
                             bevel=0.0012, segs=1))
        for sx in (-1, 1):   # side rails along y
            X = cx + sx * (w / 2 - th)
            parts.append(box(f"BENCH_rail_y{sx}_{z:.2f}v", (th, d - 2 * th, fl), (X - sx * th / 2, cy, z - fl / 2), st,
                             bevel=0.0012, segs=1))
            parts.append(box(f"BENCH_rail_y{sx}_{z:.2f}h", (fl, d - 2 * th, th), (X - sx * fl / 2, cy, z - th / 2), st,
                             bevel=0.0012, segs=1))
        for k in range(2, 16):
            slots.box((0.026, 0.0008, 0.011), (cx - w / 2 + k * w / 17, yfront + th - 0.0004, z - fl / 2), sl)
        for k in range(2, 11):
            slots.box((0.0008, 0.026, 0.011), (xright - th + 0.0004, cy - d / 2 + k * d / 12, z - fl / 2), sl)
        for sx in (-1, 1):   # bolt heads where the rails meet the legs
            parts.append(cyl(f"BENCH_bolt_f{sx}_{z:.2f}", 0.008, 0.006, (cx + sx * (w / 2 - 0.022), yfront - 0.003, z - fl / 2),
                             st, n=6, rot=(math.pi / 2, 0, 0)))
            parts.append(cyl(f"BENCH_bolt_r{sx}_{z:.2f}", 0.008, 0.006, (xright + 0.003, cy + sx * (d / 2 - 0.022), z - fl / 2),
                             st, n=6, rot=(0, math.pi / 2, 0)))
    parts.append(slots.make())
    parts.append(box("BENCH_top", (w + 0.04, d + 0.04, 0.025), (cx, cy, hgt + 0.0125), pw, bevel=0.003))
    parts.append(box("BENCH_shelf", (w - 0.02, d - 0.02, 0.018), (cx, cy, low + 0.009), pw, bevel=0.003))
    group("angle_bench", parts)
    build_magazines(cx, cy, hgt + 0.025, low + 0.018)


def build_magazines(cx, cy, z_top, z_shelf):
    """Weekly economics magazines piled on the bench (p.304)."""
    mags = Batch("MAG_pile")
    lab = mat("label", rough=0.4)
    mm = [mat(f"mag{i}", c, rough=0.35, detail="paper") for i, c in enumerate(MAG_COLORS)]
    for (x, y, z, n) in ((cx - 0.2, cy - 0.02, z_top, 9), (cx + 0.2, cy, z_shelf, 5)):
        for _ in range(n):
            th, yaw = 0.008, math.radians(rng.uniform(-10, 10))
            c = (x + rng.uniform(-0.02, 0.02), y + rng.uniform(-0.02, 0.02), z + th / 2)
            mags.box((0.23, 0.30, th), c, rng.choice(mm), rot=(0, 0, yaw))
            mags.box((0.2, 0.05, 0.0008), on(c, yaw, (0, 0.11, th / 2 + 0.0004)), lab, rot=(0, 0, yaw))
            z += th
    group("magazines", [mags.make(bevel=0.0015, segs=1)])


# ---------------------------------------------------------------- the bookshelf

def build_bookshelf():
    """Bookshelf on the left wall: the recommended reading list (p.734)."""
    wm, dd = mat("shelf", rough=0.55), mat("desk_dark", rough=0.6)
    xb, xf = X0 + 0.04, X0 + 0.40
    xc, dep = (xb + xf) / 2, xf - xb
    y0, y1, side_t, div_t = -1.4, 1.6, 0.035, 0.03
    yc = (y0 + y1) / 2
    levels = [0.08, 0.56, 1.02, 1.48, 1.94, 2.40]
    parts = [box("SHELF_plinth", (dep - 0.03, y1 - y0 - 0.02, 0.08), (xc - 0.015, yc, 0.04), dd, bevel=0.004),
             box("SHELF_back", (0.015, y1 - y0 - 2 * side_t, 2.32), (xb + 0.0075, yc, 0.08 + 1.16), wm, bevel=0),
             box("SHELF_crown", (dep + 0.03, y1 - y0 + 0.03, 0.05), (xc + 0.015, yc, 2.455), wm, bevel=0.008, segs=3),
             box("SHELF_cornice", (dep + 0.05, y1 - y0 + 0.07, 0.025), (xc + 0.025, yc, 2.4925), wm, bevel=0.006,
                 segs=3)]
    for i, y in enumerate((y0 + side_t / 2, y1 - side_t / 2)):
        parts.append(box(f"SHELF_side_{i}", (dep, side_t, 2.43), (xc, y, 1.215), wm, bevel=0.006))
    dividers = (-0.42, 0.58)
    for i, y in enumerate(dividers):
        parts.append(box(f"SHELF_div_{i}", (dep - 0.01, div_t, 2.29), (xc - 0.005, y, 1.255), wm, bevel=0.004))
    for i, z in enumerate(levels):
        parts.append(box(f"SHELF_board_{i}", (dep - 0.015, y1 - y0 - 2 * side_t, 0.03),
                         (xb + 0.015 + (dep - 0.015) / 2, yc, z + 0.015), wm, bevel=0.004))

    books, bands, labels = Batch("SHELF_books"), Batch("SHELF_bands"), Batch("SHELF_labels")
    cols = [mat(f"book{i}", c, rough=0.8, detail="fabric") for i, c in enumerate(BOOK_COLORS)]
    gold, dark, lab = mat("band_gold", rough=0.4, metal=0.5), mat("ink"), mat("label")

    def add_book(t, h, dpt, y_lo, z0, lean=0.0):
        R = Euler((lean, 0, 0)).to_matrix()
        corners = [R @ Vector(p) for p in box_verts(dpt, t, h)]
        lo_y, hi_y = min(c.y for c in corners), max(c.y for c in corners)
        spine = xf - 0.012 - rng.uniform(0, 0.014)
        loc = Vector((spine - dpt / 2, y_lo - lo_y, z0 - min(c.z for c in corners)))
        books.box((dpt, t, h), loc, rng.choice(cols), rot=(lean, 0, 0))
        if rng.random() < 0.45:
            bm = gold if rng.random() < 0.6 else dark
            for zz in (h / 2 - 0.028, -h / 2 + 0.028):
                bands.box((0.0016, t * 0.86, 0.006), R @ Vector((dpt / 2 + 0.0008, 0, zz)) + loc, bm, rot=(lean, 0, 0))
        if rng.random() < 0.22:
            labels.box((0.0016, t * 0.7, 0.04), R @ Vector((dpt / 2 + 0.0008, 0, h * 0.14)) + loc, lab,
                       rot=(lean, 0, 0))
        return hi_y - lo_y

    bays = [(y0 + side_t, dividers[0] - div_t / 2), (dividers[0] + div_t / 2, dividers[1] - div_t / 2),
            (dividers[1] + div_t / 2, y1 - side_t)]
    for z0 in [z + 0.03 for z in levels[:5]]:
        for ya, yb in bays:
            y = ya + 0.004
            while True:
                r = rng.random()
                if r < 0.06 and yb - y > 0.4:            # a few books lying flat
                    wid, zz = rng.uniform(0.2, 0.27), z0
                    for _ in range(rng.randint(3, 5)):
                        th, dpt = rng.uniform(0.025, 0.045), rng.uniform(0.17, 0.22)
                        books.box((dpt, wid - rng.uniform(0, 0.02), th),
                                  (xf - 0.015 - dpt / 2, y + wid / 2, zz + th / 2), rng.choice(cols))
                        zz += th
                    y += wid + 0.006
                    continue
                if r < 0.1 and yb - y > 0.2:             # a gap
                    y += rng.uniform(0.04, 0.1)
                    continue
                t, h, dpt = rng.uniform(0.022, 0.058), rng.uniform(0.22, 0.36), rng.uniform(0.16, 0.25)
                if y + t > yb - 0.004:
                    space = yb - y - 0.004
                    if space > 0.04:                     # lean the last book into the leftover space
                        t = min(t, space * 0.6)
                        lean = math.asin(min(0.45, max(0.0, (space - t) / h)))
                        add_book(t, h, dpt, y, z0, lean)
                    break
                y += add_book(t, h, dpt, y, z0) + rng.uniform(0.0, 0.003)
    # a small pile and a box file on top
    zz = 2.505
    for k in range(3):
        th = rng.uniform(0.03, 0.05)
        books.box((0.2, 0.27, th), (xc + 0.02, 1.05, zz + th / 2), rng.choice(cols), rot=(0, 0, math.radians(rng.uniform(-6, 6))))
        zz += th
    parts.append(box("SHELF_boxfile", (0.26, 0.09, 0.3), (xc + 0.02, 0.62, 2.505 + 0.15), mat("manila"), bevel=0.004))
    parts += [books.make(bevel=0.0025, segs=1), bands.make(), labels.make()]
    group("bookshelf", parts)


# ---------------------------------------------------------------- the drawer cabinet

def build_cabinet():
    """Drawer cabinet with card-catalogue labels: where replies are kept. The top drawer is
    marked so the export keeps it apart and the web app can slide it open."""
    cm, dd, br, lab = mat("cabinet", rough=0.55), mat("desk_dark"), mat("brass", rough=0.35, metal=0.85), mat("label")
    cx, cy = -1.75, 2.5
    body = [box("CAB_plinth", (0.62, 0.52, 0.07), (cx, cy + 0.02, 0.035), dd, bevel=0.004),
            box("CAB_body", (0.66, 0.56, 0.82), (cx, cy + 0.01, 0.48), cm, bevel=0.008),
            box("CAB_top", (0.72, 0.62, 0.03), (cx, cy, 0.905), cm, bevel=0.01, segs=3)]
    yf = cy + 0.01 - 0.28
    slide = []
    for k, (z0, z1) in enumerate(((0.09, 0.34), (0.36, 0.61), (0.63, 0.87))):
        zc, hh = (z0 + z1) / 2, z1 - z0
        dst = slide if k == 2 else body
        dst += [box(f"CAB_front_{k}", (0.6, 0.022, hh), (cx, yf - 0.011, zc), cm, bevel=0.006),
                box(f"CAB_panel_{k}", (0.48, 0.008, hh - 0.08), (cx, yf - 0.026, zc), cm, bevel=0.004),
                box(f"CAB_holder_{k}", (0.095, 0.005, 0.06), (cx, yf - 0.0325, zc + 0.045), br, bevel=0.0015, segs=1),
                box(f"CAB_card_{k}", (0.078, 0.004, 0.044), (cx, yf - 0.0345, zc + 0.045), lab, bevel=0),
                box(f"CAB_pull_{k}", (0.085, 0.018, 0.02), (cx, yf - 0.039, zc - 0.035), br, bevel=0.006)]
    slide.append(box("CAB_drawer_box", (0.56, 0.5, 0.2), (cx, yf + 0.252, 0.75), cm, bevel=0.004))
    for o in slide:
        o["slide"] = True

    # letters on top: a bundle tied with red string and two loose envelopes
    po, red = mat("paper_old"), mat("pin", rough=0.6)
    top = 0.92
    bc, byaw = (cx + 0.1, cy + 0.04, 0), math.radians(8)
    env = Batch("CAB_letters")
    for k in range(5):
        env.box((0.22, 0.12, 0.004), on((bc[0], bc[1], top + 0.002 + k * 0.004), byaw, (rng.uniform(-0.004, 0.004), 0, 0)),
                po, rot=(0, 0, byaw + math.radians(rng.uniform(-3, 3))))
    zt = top + 0.0215
    env.box((0.226, 0.004, 0.003), on((bc[0], bc[1], zt), byaw, (0, 0, 0)), red, rot=(0, 0, byaw))
    env.box((0.004, 0.126, 0.003), on((bc[0], bc[1], zt), byaw, (0, 0, 0)), red, rot=(0, 0, byaw))
    for k, yaw in enumerate((math.radians(-14), math.radians(-4))):
        c = (cx - 0.16 + k * 0.02, cy - 0.06 - k * 0.02, top + 0.0015 + k * 0.003)
        env.box((0.22, 0.11, 0.003), c, po, rot=(0, 0, yaw))
        env.add([(-0.11, 0.055, 0.0016), (0.11, 0.055, 0.0016), (0.0, -0.012, 0.0016)], [(0, 2, 1)],
                mat("manila"), c, (0, 0, yaw))
    body.append(env.make())
    group("drawer", body + slide)


# ---------------------------------------------------------------- on the walls

def build_wall_things():
    pm, ink, pen = mat("paper"), mat("ink"), mat("pen_blue", rough=0.4)
    # the checklist pinned above the desk (p.143)
    cxk, zk = 0.1, 1.75
    yp = Y1 - 0.004
    yl = yp - 0.0015 - 0.0004
    parts = [box("CHK_paper", (0.30, 0.003, 0.42), (cxk, yp, zk), pm, bevel=0)]
    lines = Batch("CHK_lines")
    lines.box((0.15, 0.0008, 0.012), (cxk - 0.045, yl, zk + 0.17), ink)
    for j in range(8):
        z = zk + 0.12 - j * 0.04
        bxc = cxk - 0.11
        lines.box((0.022, 0.0008, 0.0025), (bxc, yl, z + 0.0098), ink)
        lines.box((0.022, 0.0008, 0.0025), (bxc, yl, z - 0.0098), ink)
        lines.box((0.0025, 0.0008, 0.022), (bxc - 0.0098, yl, z), ink)
        lines.box((0.0025, 0.0008, 0.022), (bxc + 0.0098, yl, z), ink)
        lines.box((0.17 - (j % 3) * 0.03, 0.0008, 0.003), (cxk + 0.01 - (j % 3) * 0.015, yl, z), ink)
        if j < 5:
            lines.box((0.012, 0.0008, 0.0035), (bxc - 0.004, yl - 0.0005, z - 0.001), pen, rot=(0, math.radians(45), 0))
            lines.box((0.026, 0.0008, 0.0035), (bxc + 0.008, yl - 0.0005, z + 0.006), pen, rot=(0, math.radians(-55), 0))
    parts.append(lines.make())
    parts.append(lathe("CHK_pin", [(0, 0), (0.004, 0), (0.004, 0.006), (0.009, 0.008), (0.010, 0.016), (0.008, 0.024),
                                   (0, 0.026)], (cxk, yp - 0.0015, zk + 0.19), mat("pin", rough=0.3), n=16,
                       rot=(math.pi / 2, 0, 0)))
    turn(parts, (cxk, Y1, zk), (0, math.radians(2), 0))
    group("checklist", parts)

    # a caricature in a frame, the face left blank (preface p.6)
    fx, fz, fw, fh, mw, dp = -1.0, 1.9, 0.5, 0.62, 0.045, 0.03
    fm = mat("frame", rough=0.6)
    fr = [box("CAR_frame_top", (fw, dp, mw), (fx, Y1 - dp / 2, fz + fh / 2 - mw / 2), fm, bevel=0.006),
          box("CAR_frame_bot", (fw, dp, mw), (fx, Y1 - dp / 2, fz - fh / 2 + mw / 2), fm, bevel=0.006),
          box("CAR_frame_l", (mw, dp, fh - 2 * mw), (fx - fw / 2 + mw / 2, Y1 - dp / 2, fz), fm, bevel=0.006),
          box("CAR_frame_r", (mw, dp, fh - 2 * mw), (fx + fw / 2 - mw / 2, Y1 - dp / 2, fz), fm, bevel=0.006),
          box("CAR_mat", (fw - 2 * mw + 0.004, 0.006, fh - 2 * mw + 0.004), (fx, Y1 - 0.012, fz), mat("label"), bevel=0),
          box("CAR_paper", (0.28, 0.002, 0.38), (fx, Y1 - 0.016, fz), pm, bevel=0)]
    yd = Y1 - 0.0172

    def stroke(name, pts, r=0.0017):
        return tube(name, [(fx + x, yd, fz + z) for x, z in pts], r, ink, n=5)

    head = [(0.066 * math.cos(math.radians(a)), 0.07 + 0.086 * math.sin(math.radians(a))) for a in range(115, 430, 15)]
    fr.append(stroke("CAR_head", head))
    fr.append(stroke("CAR_shoulders", [(-0.13, -0.16), (-0.11, -0.1), (-0.05, -0.065), (0.0, -0.06), (0.05, -0.066),
                                       (0.11, -0.1), (0.13, -0.16)]))
    fr.append(stroke("CAR_neck_l", [(-0.022, -0.012), (-0.024, -0.058)], 0.0014))
    fr.append(stroke("CAR_neck_r", [(0.024, -0.012), (0.026, -0.058)], 0.0014))
    fr.append(stroke("CAR_hair", [(-0.06, 0.12), (-0.03, 0.15), (0.01, 0.158), (0.05, 0.14)], 0.0014))
    fr.append(stroke("CAR_sign", [(0.06, -0.175), (0.075, -0.168), (0.085, -0.178), (0.1, -0.17)], 0.0011))
    group("caricature", fr)


# ---------------------------------------------------------------- the reading corner

def build_reading_corner():
    """Armchair, side table, the open book where replies appear, tea and a floor lamp."""
    fab, wood = mat("armchair", rough=0.95), mat("desk", rough=0.55)
    ax, ay, W, D = 1.2, -0.9, 0.92, 0.86
    chair = [box("ARM_body", (W - 0.012, D, 0.28), (ax, ay, 0.22), fab, bevel=0.045, segs=4),
             box("ARM_seat", (0.62, 0.66, 0.13), (ax, ay - 0.07, 0.425), fab, bevel=0.05, segs=4)]
    back = box("ARM_back", (W - 0.03, 0.2, 0.62), (ax, ay + 0.33, 0.61), fab, bevel=0.06, segs=4)
    turn([back], (ax, ay + 0.33, 0.30), (math.radians(-10), 0, 0))
    pillow = box("ARM_back_cushion", (0.62, 0.15, 0.42), (ax, ay + 0.2, 0.70), fab, bevel=0.06, segs=5)
    turn([pillow], (ax, ay + 0.28, 0.49), (math.radians(-14), 0, 0))
    chair += [back, pillow]
    for sx in (-1, 1):
        chair.append(box(f"ARM_side_{sx}", (0.15, D - 0.04, 0.34), (ax + sx * (W / 2 - 0.075), ay - 0.01, 0.47), fab,
                         bevel=0.04, segs=4))
        chair.append(cyl(f"ARM_roll_{sx}", 0.08, D - 0.02, (ax + sx * (W / 2 - 0.06), ay - 0.01, 0.62), fab, n=24,
                         rot=(math.pi / 2, 0, 0), bevel=0.025, segs=3))
        for sy in (-1, 1):
            chair.append(lathe(f"ARM_foot_{sx}{sy}", [(0, 0), (0.022, 0), (0.026, 0.02), (0.03, 0.06), (0.032, 0.08),
                                                      (0, 0.08)], (ax + sx * 0.38, ay + sy * 0.35, 0), wood, n=16))
    # a throw over the right arm
    path = [(1.40, 0.498), (1.46, 0.50), (1.50, 0.53), (1.515, 0.60), (1.535, 0.665), (1.57, 0.70), (1.60, 0.708),
            (1.635, 0.70), (1.666, 0.678), (1.687, 0.625), (1.673, 0.565), (1.667, 0.50), (1.667, 0.42), (1.668, 0.34)]
    rows = []
    for j in range(9):
        yy = ay - 0.15 + j * 0.05
        rows.append([(x + 0.003 * math.sin(j * 1.7 + k) * (k > 9), yy + (0.008 * math.sin(k * 0.9) if k > 9 else 0), z)
                     for k, (x, z) in enumerate(path)])
    chair.append(sheet("ARM_throw", list(map(list, zip(*rows))), mat("throw", rough=1.0), 0.012))
    group("armchair", chair)

    tx, ty = 0.25, -1.1
    group("side_table", [
        lathe("SIDE_top", [(0, 0.535), (0.30, 0.535), (0.305, 0.545), (0.305, 0.562), (0.298, 0.57), (0, 0.57)],
              (tx, ty, 0), wood, n=48),
        lathe("SIDE_column", [(0, 0.035), (0.036, 0.035), (0.05, 0.07), (0.032, 0.12), (0.027, 0.3), (0.04, 0.38),
                              (0.03, 0.45), (0.026, 0.5), (0.045, 0.535), (0, 0.535)], (tx, ty, 0), wood, n=24),
        lathe("SIDE_base", [(0, 0), (0.19, 0), (0.2, 0.012), (0.18, 0.028), (0.08, 0.04), (0, 0.042)], (tx, ty, 0),
              wood, n=40)])

    # the open book, its pages curving up from the spine
    bx, by, yaw, top = tx - 0.02, ty + 0.06, math.radians(12), 0.57
    pm, ink = mat("paper"), mat("ink")
    book = [box("BOOK_cover", (0.40, 0.28, 0.006), (bx, by, top + 0.003), mat("book0", BOOK_COLORS[0], rough=0.8,
                                                                                detail="fabric"), bevel=0.002)]

    def page_z(u):
        return top + 0.007 + 0.016 * math.sin(min(1.0, u / 0.3) * math.pi / 2) - 0.004 * max(0.0, u - 0.3) / 0.7

    us = [k / 12 for k in range(13)]
    text = Batch("BOOK_text")
    for side in (-1, 1):
        poly = [(side * 0.19 * u, page_z(u)) for u in us] + [(side * 0.19, top + 0.006), (0.0, top + 0.006)]
        if side > 0:                             # counter-clockwise, so the faces point outward
            poly.reverse()
        book.append(prism_xz(f"BOOK_pages_{side}", poly, -0.13, 0.13, pm, loc=(bx, by, 0)))
        for j in range(7):
            yy = 0.1 - j * 0.033
            pts = [(side * 0.19 * u, page_z(u) + 0.0006) for u in [0.14 + 0.72 * k / 6 for k in range(7)]]
            v = [(x, yy - 0.002, z) for x, z in pts] + [(x, yy + 0.002, z) for x, z in pts]
            f = [(i, i + 1, 8 + i, 7 + i) if side > 0 else (i, 7 + i, 8 + i, i + 1) for i in range(6)]
            text.add(v, f, ink, (bx, by, 0))
    book.append(text.make())
    turn(book, (bx, by, 0), (0, 0, yaw))
    group("open_book", book)

    # tea in a cup on its saucer, the handle toward the room
    cx_, cy_, z = tx + 0.16, ty - 0.15, top
    por = mat("porcelain", rough=0.25)
    phi = math.radians(-60)
    d = Vector((math.cos(phi), math.sin(phi), 0))
    c = Vector((cx_, cy_, z + 0.008 + 0.038)) + d * 0.046
    arc = [c + 0.016 * (math.cos(t) * d + math.sin(t) * Vector((0, 0, 1)))
           for t in [math.radians(a) for a in range(-100, 101, 20)]]
    group("teacup", [
        lathe("TEA_saucer", [(0, 0), (0.045, 0), (0.05, 0.004), (0.068, 0.013), (0.07, 0.016), (0.066, 0.017),
                             (0.045, 0.008), (0, 0.007)], (cx_, cy_, z), por, n=32),
        lathe("TEA_cup", [(0, 0.006), (0.026, 0.006), (0.03, 0.01), (0.042, 0.035), (0.046, 0.06), (0.047, 0.068),
                          (0.044, 0.068), (0.043, 0.06), (0.039, 0.035), (0.026, 0.013), (0, 0.012)],
              (cx_, cy_, z + 0.002), por, n=32),
        lathe("TEA_tea", [(0, 0.05), (0.041, 0.05), (0.041, 0.052), (0, 0.052)], (cx_, cy_, z + 0.002),
              mat("tea", rough=0.05), n=24),
        tube("TEA_handle", arc, 0.0045, por, n=8)])

    # floor lamp behind the armchair
    br, lx, ly = mat("brass", rough=0.35, metal=0.85), 2.0, -0.4
    sm = mat("shade2", rough=0.9)
    flamp = [lathe("FL_base", [(0, 0), (0.15, 0), (0.152, 0.008), (0.14, 0.022), (0.06, 0.035), (0.02, 0.045), (0, 0.045)],
                   (lx, ly, 0), br, n=32),
             cyl("FL_pole", 0.011, 1.43, (lx, ly, 0.76), br, n=16),
             cyl("FL_switch", 0.016, 0.03, (lx, ly, 1.0), br, n=16),
             lathe("FL_fitter", [(0, 1.47), (0.02, 1.47), (0.022, 1.50), (0.015, 1.53), (0, 1.535)], (lx, ly, 0), br, n=16),
             lathe("FL_shade", [(0.22, 1.46), (0.17, 1.74), (0.165, 1.74), (0.215, 1.46)], (lx, ly, 0), sm, n=48,
                   sharp=30),
             lathe("FL_bulb", [(0, 1.47), (0.03, 1.49), (0.05, 1.52), (0.035, 1.56), (0, 1.57)], (lx, ly, 0),
                   mat("bulb", emit=6.0), n=20)]
    group("floor_lamp", flamp)   # no spider arms: seen through the open top, one read as a crack in the shade


# ---------------------------------------------------------------- rug, plant, floor books

def leaf_geom(length, width):
    """A leaf lying along +x, folded a little along its midrib and drooping at the tip."""
    n = 7
    v, f = [(0, 0, 0)], []
    for i in range(1, n):
        u = i / n
        x = length * u
        hw = width / 2 * math.sin(math.pi * u ** 0.85) ** 0.8
        z = -0.22 * length * u * u
        v += [(x, -hw, z + 0.18 * hw), (x, 0, z), (x, hw, z + 0.18 * hw)]
    v.append((length, 0, -0.22 * length))
    tip = len(v) - 1
    f += [(0, 2, 1), (0, 3, 2)]
    for i in range(n - 2):
        a, b = 1 + 3 * i, 4 + 3 * i
        f += [(a, a + 1, b + 1, b), (a + 1, a + 2, b + 2, b + 1)]
    last = 1 + 3 * (n - 2)
    f += [(last, last + 1, tip), (last + 1, last + 2, tip)]
    return v, f


def build_decor():
    # the rug, with a border and a medallion
    rx, ry, RW, RD = 0.7, -0.6, 2.6, 1.8
    base, edge, acc = mat("rug", rough=1.0), mat("rug_edge", rough=1.0), mat("rug_accent", rough=1.0)
    rug = [box("RUG_base", (RW, RD, 0.012), (rx, ry, 0.006), base, bevel=0.004, segs=2)]
    pat = Batch("RUG_pattern")
    z = 0.0128
    for inset, band, m in ((0.1, 0.09, edge), (0.26, 0.025, acc)):
        for s in (-1, 1):
            pat.box((RW - 2 * inset, band, 0.0016), (rx, ry + s * (RD / 2 - inset - band / 2), z), m)
            pat.box((band, RD - 2 * inset - 2 * band, 0.0016), (rx + s * (RW / 2 - inset - band / 2), ry, z), m)
    for k, (size, m) in enumerate(((0.56, acc), (0.36, edge), (0.14, base))):
        pat.box((size, size, 0.0016), (rx, ry, z + k * 0.0012), m, rot=(0, 0, math.pi / 4))
    for sx in (-1, 1):
        for sy in (-1, 1):
            pat.box((0.12, 0.12, 0.0016), (rx + sx * (RW / 2 - 0.42), ry + sy * (RD / 2 - 0.42), z), edge,
                    rot=(0, 0, math.pi / 4))
        for k in range(int(RD / 0.03)):
            pat.box((0.06, 0.005, 0.003), (rx + sx * (RW / 2 + 0.028), ry - RD / 2 + 0.02 + k * 0.03, 0.0015), edge,
                    rot=(0, 0, math.radians(rng.uniform(-8, 8))))
    rug.append(pat.make())
    group("rug", rug)

    # a rubber plant in a terracotta pot
    px, py = 2.55, 1.6
    plant = [lathe("PLANT_saucer", [(0, 0), (0.15, 0), (0.175, 0.025), (0.168, 0.025), (0.145, 0.008), (0, 0.008)],
                   (px, py, 0), mat("pot", rough=0.9), n=32),
             lathe("PLANT_pot", [(0, 0), (0.11, 0), (0.113, 0.006), (0.148, 0.255), (0.166, 0.26), (0.168, 0.30),
                                 (0.152, 0.30), (0.146, 0.27), (0, 0.27)], (px, py, 0.008), mat("pot", rough=0.9), n=32),
             lathe("PLANT_soil", [(0, 0.27), (0.145, 0.27), (0.146, 0.276), (0, 0.279)], (px, py, 0.008),
                   mat("soil", rough=1.0), n=24)]
    stem_m, leaves = mat("stem", rough=0.7), [mat("leaf", rough=0.45), mat("leaf_light", rough=0.45)]
    for s, (dx, dy, height, lean, n_leaves) in enumerate(((0.02, 0.0, 1.08, 0.08, 9), (-0.05, 0.04, 0.86, -0.1, 8),
                                                        (0.04, -0.05, 0.70, 0.12, 7))):
        pts = [Vector((px + dx + lean * t * t * 0.6, py + dy + lean * t * 0.3, 0.28 + (height - 0.28) * t))
               for t in [k / 6 for k in range(7)]]
        plant.append(tube(f"PLANT_stem_{s}", pts, [0.011 - 0.006 * k / 6 for k in range(7)], stem_m, n=6))
        az = rng.uniform(0, math.tau)
        for k in range(n_leaves):
            t = 0.22 + 0.78 * k / max(1, n_leaves - 1)
            at = pts[0].lerp(pts[-1], t)
            az += math.radians(137.5 + rng.uniform(-15, 15))
            elev = math.radians(rng.uniform(5, 30) + 25 * t)
            length = rng.uniform(0.21, 0.28) * (1.1 - 0.35 * t)
            v, f = leaf_geom(length, length * 0.52)
            lf = _make(f"PLANT_leaf_{s}_{k}", v, f, leaves[(s + k) % 2], loc=tuple(at + Vector((0, 0, 0.01))),
                       rot=(0, -elev, az), smooth=True)
            mod = lf.modifiers.new("solidify", "SOLIDIFY")
            mod.thickness = 0.003
            plant.append(lf)
    group("plant", plant)

    # a few books on the floor by the shelf
    z = 0
    for k in range(5):
        th = rng.uniform(0.04, 0.07)
        box(f"ENV_floor_book_{k}", (0.3, 0.22, th), (-2.3, -1.9, z + th / 2),
            mat(f"book{k}", BOOK_COLORS[k], rough=0.8, detail="fabric"), bevel=0.004,
            rot=(0, 0, math.radians(rng.uniform(-15, 15))))
        z += th


# ---------------------------------------------------------------- moods, lights and camera

MOODS = {
    # sky behind the window, world colour, sun (energy, colour, elevation), lamps, fill from the open side
    "dusk": dict(sky=(1.0, 0.55, 0.30), sky_emit=3.0, world=(0.93, 0.80, 0.66), world_str=0.45,
                 sun=(6.0, (1.0, 0.58, 0.32), 21), lamp=60, fill=(1.0, 0.85, 0.7), fill_e=600),
    "night": dict(sky=(0.10, 0.16, 0.32), sky_emit=1.2, world=(0.16, 0.18, 0.26), world_str=0.5,
                  sun=(0.0, (0.5, 0.6, 1.0), 40), lamp=200, fill=(0.45, 0.55, 0.85), fill_e=450),
    "morning": dict(sky=(0.75, 0.88, 1.0), sky_emit=2.5, world=(0.90, 0.92, 0.90), world_str=0.8,
                    sun=(5.0, (1.0, 0.95, 0.85), 35), lamp=0, fill=(0.95, 0.97, 1.0), fill_e=1100),
}


def _light(name, kind, loc=(0, 0, 0)):
    data = bpy.data.lights.new(name, kind)
    ob = bpy.data.objects.new(name, data)
    _link(ob)
    ob.location = loc
    return ob


def setup_lights_and_camera(mood):
    """Sun through the window, the two lamps, a soft fill from the open side, the diorama camera.
    Only sun, spot and point lights, so the hosted viewer and glTF keep them."""
    m = MOODS[mood]
    scene = bpy.context.scene
    world = bpy.data.worlds.new("WORLD_study")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*m["world"], 1)
    bg.inputs["Strength"].default_value = m["world_str"]
    scene.world = world

    sky = _make("ENV_sky", [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)], [(0, 1, 2, 3)],
                mat("sky_" + mood, m["sky"], emit=m["sky_emit"]), loc=(1.55, Y1 + 0.6, 1.85))
    sky.visible_shadow = False   # let the sun through the window

    energy, color, elev = m["sun"]
    if energy:
        sun = _light("LGT_key", "SUN")
        sun.data.energy, sun.data.color, sun.data.angle = energy, color, math.radians(3)
        d = Vector((-0.35, -1.0, -math.tan(math.radians(elev)))).normalized()
        sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if m["lamp"]:
        spot = _light("LGT_desk", "SPOT", (-0.15, 2.43, 1.28))
        spot.data.energy, spot.data.color = m["lamp"], (1.0, 0.72, 0.42)
        spot.data.spot_size, spot.data.spot_blend, spot.data.shadow_soft_size = math.radians(95), 0.6, 0.05
        spot.rotation_euler = (math.radians(25), 0, 0)
        glow = _light("LGT_desk_glow", "POINT", (-0.15, 2.43, 1.3))
        glow.data.energy, glow.data.color, glow.data.shadow_soft_size = m["lamp"] * 0.25, (1.0, 0.7, 0.4), 0.1
        fl = _light("LGT_floor", "POINT", (2.0, -0.4, 1.52))
        fl.data.energy, fl.data.color, fl.data.shadow_soft_size = m["lamp"] * 0.8, (1.0, 0.72, 0.45), 0.15
        for name, strength in (("shade2", 0.9), ("lampshade", 0.4)):
            bsdf = bpy.data.materials[name].node_tree.nodes["Principled BSDF"]
            bsdf.inputs["Emission Color"].default_value = (1.0, 0.75, 0.45, 1)
            bsdf.inputs["Emission Strength"].default_value = strength * m["lamp"] / 60
    else:
        for name in ("bulb",):
            bpy.data.materials[name].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0

    fill = _light("LGT_fill", "POINT", (4.5, -4.5, 5.0))
    fill.data.energy, fill.data.color, fill.data.shadow_soft_size = m["fill_e"], m["fill"], 3.0

    cam_data = bpy.data.cameras.new("CAM_main")
    cam_data.type, cam_data.ortho_scale = "ORTHO", 8.2
    cam = bpy.data.objects.new("CAM_main", cam_data)
    _link(cam)
    cam.location = (9.5, -9.0, 8.2)
    cam.rotation_euler = (Vector((-0.1, 0.4, 1.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam


# ---------------------------------------------------------------- build and render

def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for blocks in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.worlds):
        for b in list(blocks):
            blocks.remove(b)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def _collection(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def build_study(detail=False, mood="dusk", lights=True):
    """Clear the scene and build the whole study (and, unless lights=False, the lights and camera)."""
    global DETAIL, COLL, rng, tag_rng
    DETAIL, rng, tag_rng = detail, random.Random(7), random.Random(11)
    _mats.clear()
    clear_scene()
    COLL = _collection("STUDY")
    build_room()
    build_desk()
    build_angle_bench()
    build_bookshelf()
    build_cabinet()
    build_wall_things()
    build_reading_corner()
    build_decor()
    if lights:
        COLL = _collection("RIG")
        setup_lights_and_camera(mood)
    COLL = None


def render(path, samples, res, engine="CYCLES"):
    scene = bpy.context.scene
    scene.render.engine = engine
    if engine == "CYCLES":
        scene.cycles.device = "CPU"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
    else:
        scene.eevee.taa_render_samples = samples
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--mood", default="dusk", choices=list(MOODS))
    ap.add_argument("--out")
    ap.add_argument("--save")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--res", default="1200x900")
    ap.add_argument("--detail", action="store_true", help="procedural surface detail (slower)")
    a = ap.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_study(detail=a.detail, mood=a.mood)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=a.save)
    if a.out:
        render(a.out, a.samples, tuple(int(v) for v in a.res.split("x")))


if __name__ == "__main__":
    main()
