"""Grow the study into a small house: the study as built, a waiting room by the front door and a
garage with a car and bicycles. This is the concept stage (step 2 of the house plan); the web
page still shows the study alone.

    python3 blender/build_house.py --out renders/house/overview.png --font <EastSeaDokdo-Regular.ttf>
    python3 blender/build_house.py --view hall --out renders/house/hall.png
    python3 blender/build_house.py --view garage --out renders/house/garage.png --font <...>
    python3 blender/build_house.py --save blender/house.blend

It is a cutaway, like a doll's house with its front taken off: the front walls stop at 0.3 m,
and the walls between the rooms and the garage's side wall stop at 0.95 m, so the camera looks
over them into every room. The words on the garage wall need a Korean brush-script font (East Sea
Dokdo, SIL Open Font License, from github.com/google/fonts); without --font they are left out.

What is in it, from 세이노의 가르침 (데이원, 2023):
- The waiting room is plain on purpose. His father, a doctor, would not dress up his waiting
  room: "병원은 환자를 치료하는 곳이지 여관이 아니다" (p.610). A long bench, a table to write the
  letter at, a coat stand, and a low case of the books he recommends: the driver he hired read
  them in the drivers' waiting room instead of playing cards (p.183).
- The garage has an old silver two-seater, drawn without any brand mark, which he still drives
  for the car audio he rebuilt himself (p.377); shelves for model bicycles (p.27, p.287); a
  workbench, because he did everything himself to save money (p.419); and a corner that recalls
  the rented garage he lived in for four years in his twenties (pp.324-325): a board desk hung
  on dog-leash chains, a small used fridge with an electric hot plate on it, old used audio
  equipment, and the words he wrote large on the wall.
- The study gets a place to listen to music: in the garage he was happy anywhere he could read
  and listen to music (p.324), and he kept changing his audio (p.394).
It is not his real house: only rooms a visitor would see, no bedroom, no family (p.287).
"""
import argparse
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_study as bs  # noqa: E402
import characters as ch  # noqa: E402
from build_study import BOX_FACES, Batch, _make, box, cyl, group, lathe, mat, on, prism_xz, sheet, tube, turn  # noqa: E402

# ---------------------------------------------------------------- layout

Y1, T, WALL_H, X0 = bs.Y1, bs.T, bs.WALL_H, bs.X0
YF = -3.06                      # front edge of the floors
YW = YF + T                     # inner face of the low front walls
HX0, HX1 = 3.2, 7.2             # waiting room, between its side walls
GX0, GX1 = 7.4, 13.4            # garage
XR = GX1 + T                    # outer face of the garage's side wall
CUT, LOW = 0.95, 0.3            # walls the camera looks over, and the front walls
DOOR_A = (0.15, 1.15)           # study to waiting room, in the wall at x 3.0..3.2
DOOR_B = (-2.05, -1.05)         # waiting room to garage, in the wall at x 7.2..7.4
FRONT_DOOR = (4.7, 5.7)         # in the waiting room's front wall
SHUTTER = (7.7, 13.1)           # the garage's open front, between two short wall ends
HALL_WIN = (4.6, 6.0, 1.25, 2.45)
GAR_WIN = (7.95, 9.05, 2.2, 2.7)
CAR_AT = (10.35, -0.25)         # the car stands nose to the street
EPS = 0.002                     # outer skins stand this proud of the walls behind them: Cycles renders
                                # two faces in one plane black

HOUSE = {
    "oak_a": (0.60, 0.42, 0.24), "oak_b": (0.55, 0.38, 0.21), "oak_c": (0.64, 0.46, 0.27),
    "concrete": (0.40, 0.39, 0.36), "seam": (0.20, 0.19, 0.18), "oil": (0.11, 0.10, 0.09),
    "block": (0.72, 0.70, 0.64), "brick_a": (0.40, 0.18, 0.11), "brick_b": (0.33, 0.15, 0.10),
    "mortar": (0.60, 0.57, 0.52), "paving_a": (0.50, 0.47, 0.43), "paving_b": (0.44, 0.42, 0.39),
    "stone": (0.56, 0.53, 0.49), "bench": (0.40, 0.25, 0.14), "coir": (0.46, 0.33, 0.17),
    "butcher": (0.55, 0.38, 0.21), "pegboard": (0.52, 0.38, 0.24),
    "car_paint": (0.58, 0.60, 0.62), "chrome": (0.86, 0.86, 0.87), "tire": (0.035, 0.035, 0.038),
    "car_seat": (0.46, 0.26, 0.13), "car_inside": (0.10, 0.09, 0.09), "softtop": (0.07, 0.07, 0.08),
    "lens": (0.86, 0.87, 0.83), "taillight": (0.55, 0.05, 0.04), "plate": (0.90, 0.90, 0.86),
    "grille": (0.03, 0.03, 0.035), "car_glass": (0.82, 0.88, 0.90),
    "saddle": (0.30, 0.17, 0.09), "wicker": (0.52, 0.36, 0.17), "bike_mint": (0.24, 0.50, 0.45),
    "bike_red": (0.62, 0.08, 0.06), "bike_green": (0.12, 0.34, 0.20), "bike_blue": (0.12, 0.24, 0.55),
    "bike_black": (0.04, 0.04, 0.045), "tool_red": (0.55, 0.08, 0.06), "tool_yellow": (0.80, 0.56, 0.08),
    "fridge": (0.78, 0.76, 0.68), "hotplate": (0.74, 0.70, 0.60), "yangeun": (0.80, 0.58, 0.22),
    "radio": (0.42, 0.42, 0.43), "cone": (0.07, 0.07, 0.07), "tube_light": (1.0, 0.97, 0.90),
    "sconce": (1.0, 0.86, 0.66), "umbrella_a": (0.12, 0.16, 0.30), "umbrella_b": (0.45, 0.10, 0.08),
    "ceramic": (0.30, 0.36, 0.40), "record": (0.02, 0.02, 0.02), "coat": (0.07, 0.09, 0.15),
    "coat_dark": (0.045, 0.055, 0.09), "hat": (0.17, 0.12, 0.08), "hat_band": (0.035, 0.03, 0.028),
}

rng = random.Random(23)
FONT = None                     # path to a Korean handwriting font for the garage wall


def hm(name, rough=0.75, metal=0.0, emit=0.0, detail=None):
    """A house material, coloured from HOUSE."""
    return mat(name, HOUSE[name], rough=rough, metal=metal, emit=emit, detail=detail)


def brick():
    """Brick for the outside faces, from Blender's brick texture laid along each wall."""
    if "brick" in bs._mats:
        return bs._mats["brick"]
    m = bpy.data.materials.new("brick")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bsdf = N["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.85
    tc, sep, add, comb = (N.new("ShaderNodeTexCoord"), N.new("ShaderNodeSeparateXYZ"), N.new("ShaderNodeMath"),
                          N.new("ShaderNodeCombineXYZ"))
    L.new(tc.outputs["Object"], sep.inputs[0])
    L.new(sep.outputs[0], add.inputs[0])
    L.new(sep.outputs[1], add.inputs[1])
    L.new(add.outputs[0], comb.inputs[0])
    L.new(sep.outputs[2], comb.inputs[1])
    tex = N.new("ShaderNodeTexBrick")
    L.new(comb.outputs[0], tex.inputs["Vector"])
    for k, c in (("Color1", "brick_a"), ("Color2", "brick_b"), ("Mortar", "mortar")):
        tex.inputs[k].default_value = (*HOUSE[c], 1)
    tex.inputs["Scale"].default_value = 1.0
    tex.inputs["Mortar Size"].default_value = 0.01
    tex.inputs["Brick Width"].default_value = 0.23
    tex.inputs["Row Height"].default_value = 0.075
    L.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bs._mats["brick"] = m
    return m


def glass():
    m = hm("car_glass", rough=0.04)
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Transmission Weight"].default_value = 0.92
    bsdf.inputs["IOR"].default_value = 1.45
    return m


def apply_modifiers(ob):
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    old, ob.data = ob.data, me
    ob.modifiers.clear()
    bpy.data.meshes.remove(old)


def ring_pts(c, r, axis="y", n=40, a0=0.0, a1=math.tau):
    """Points on a circle around c, in the plane across `axis`."""
    c = Vector(c)
    pts = []
    for k in range(n + 1):
        t = a0 + (a1 - a0) * k / n
        u, w = r * math.cos(t), r * math.sin(t)
        pts.append(c + (Vector((u, 0, w)) if axis == "y" else Vector((0, u, w)) if axis == "x" else Vector((u, w, 0))))
    return pts


def wedge(name, x0, x1, y0, y1, z_front, z_back, zb, material):
    """A slab whose top slopes from z_back at y1 down to z_front at y0."""
    v = [(x0, y0, zb), (x1, y0, zb), (x1, y1, zb), (x0, y1, zb),
         (x0, y0, z_front), (x1, y0, z_front), (x1, y1, z_back), (x0, y1, z_back)]
    return _make(name, v, BOX_FACES, material, bevel=0.006, segs=1)


def text(name, body, size, loc, rot, material, font=None, align="CENTER"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(str(font or FONT), check_existing=True)
    cu.size, cu.align_x, cu.align_y = size, align, "CENTER"
    cu.space_line = 0.95
    cu.extrude = 0.0006
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(material)
    bs._link(ob)
    ob.location, ob.rotation_euler = loc, rot
    return ob


# ---------------------------------------------------------------- walls and floors

def panelling(prefix, along, u0, u1, plane, side):
    """The study's painted wainscot on any wall; `side` points from the wall into the room."""
    paint, trim = mat("wainscot", rough=0.6), mat("trim", rough=0.55)

    def pbox(name, a, b, w0, w1, z0, z1, m, bevel=0.004):
        wc = plane + side * (w0 + w1) / 2
        if along == "x":
            return box(name, (b - a, w1 - w0, z1 - z0), ((a + b) / 2, wc, (z0 + z1) / 2), m, bevel=bevel)
        return box(name, (w1 - w0, b - a, z1 - z0), (wc, (a + b) / 2, (z0 + z1) / 2), m, bevel=bevel)

    pbox(prefix + "_board", u0, u1, 0, 0.012, 0, 0.86, paint, bevel=0)
    pbox(prefix + "_skirting", u0, u1, 0, 0.024, 0, 0.13, paint)
    pbox(prefix + "_rail", u0, u1, 0, 0.022, 0.80, 0.86, paint)
    pbox(prefix + "_cap", u0, u1, 0, 0.036, 0.86, 0.90, trim, bevel=0.008)
    n = max(1, round((u1 - u0) / 0.62))
    for k in range(n + 1):
        u = u0 + (u1 - u0) * k / n
        pbox(f"{prefix}_stile_{k}", max(u0, u - 0.035), min(u1, u + 0.035), 0, 0.022, 0.13, 0.80, paint)


def slab(name, x0, x1, y0, y1, height, material, cap=True):
    """A wall standing on the floor, its cut top covered by a dark cap like the study's walls."""
    w = box(name, (x1 - x0, y1 - y0, height + 0.02), ((x0 + x1) / 2, (y0 + y1) / 2, (height - 0.02) / 2), material,
            bevel=0.006)
    if cap:
        box(name + "_cap", (x1 - x0 + 0.02, y1 - y0 + 0.02, 0.03), ((x0 + x1) / 2, (y0 + y1) / 2, height + 0.015),
            mat("plinth"), bevel=0.006)
    return w


def build_shell():
    plaster, block, brk, cap = mat("plaster", rough=0.9), hm("block", rough=0.9, detail="plaster"), brick(), mat("plinth")

    # the base: one dark plinth under the three rooms, and a lower step in front for the pavement
    box("ENV_plinth", (XR + 0.02 - (X0 - T - 0.02), Y1 + T + 0.02 - (YF - 0.02), 0.2),
        ((XR + 0.02 + X0 - T - 0.02) / 2, (Y1 + T + 0.02 + YF - 0.02) / 2, -0.12), cap, bevel=0.02, segs=3)
    box("ENV_base_front", (XR + 0.06 - (X0 - T - 0.06), 1.0, 0.2), ((XR + X0 - T) / 2, YF - 0.42, -0.16), cap,
        bevel=0.02, segs=3)
    tiles = Batch("ENV_pavement")
    pa, pb = hm("paving_a", rough=0.9, detail="plaster"), hm("paving_b", rough=0.9, detail="plaster")
    x, size = X0 - T - 0.04, 0.39
    while x < XR + 0.02:
        for j in range(2):
            tiles.box((min(size, XR + 0.04 - x) - 0.008, size - 0.008, 0.025),
                      (x + min(size, XR + 0.04 - x) / 2, YF - 0.02 - size * (j + 0.5), -0.0475), rng.choice((pa, pb)))
        x += size
    tiles.make(bevel=0.003, segs=1)
    stone, conc = hm("stone", rough=0.8, detail="plaster"), hm("concrete", rough=0.9, detail="plaster")
    box("ENV_doorstep", (FRONT_DOOR[1] - FRONT_DOOR[0] + 0.3, 0.42, 0.065),
        (sum(FRONT_DOOR) / 2, YF - 0.21, -0.0325), stone, bevel=0.01)
    wedge("ENV_apron", SHUTTER[0] + 0.05, SHUTTER[1] - 0.05, YF - 0.8, YF, -0.035, 0.0, -0.07, conc)

    # floors: oak boards across the waiting room, a concrete slab in the garage
    boards = Batch("ENV_hall_floor")
    tones = [hm(k, rough=0.6, detail="wood") for k in ("oak_a", "oak_b", "oak_c")]
    y = YF
    while y < Y1 - 0.01:
        w = min(0.2, Y1 - y)
        x, first = bs.XF, True
        while x < GX0 - 0.1 - 0.01:
            length = min(rng.uniform(0.5, 1.4) if first else rng.uniform(1.0, 2.0), GX0 - 0.1 - x)
            first = False
            boards.box((length - 0.004, w - 0.004, 0.02), (x + length / 2, y + w / 2, -0.01), rng.choice(tones))
            x += length
        y += w
    boards.make(bevel=0.0025, segs=1)
    box("ENV_garage_floor", (XR - (GX0 - 0.1), Y1 - YF, 0.02), ((XR + GX0 - 0.1) / 2, (Y1 + YF) / 2, -0.01), conc,
        bevel=0)
    seams = Batch("ENV_garage_seams")
    sm = hm("seam", rough=0.9)
    for x in (9.4, 11.4):
        seams.box((0.012, Y1 - YF, 0.001), (x, (Y1 + YF) / 2, 0.0004), sm)
    for y in (-1.0, 1.0):
        seams.box((GX1 - GX0, 0.012, 0.001), ((GX0 + GX1) / 2, y, 0.0004), sm)
    seams.make()
    stain = cyl("ENV_oil_stain", 0.3, 0.001, (CAR_AT[0] - 0.05, CAR_AT[1] - 1.45, 0.0006), hm("oil", rough=0.25), n=24)
    stain.scale = (1.0, 0.7, 1.0)

    # the back wall, on from the study's: plaster with a window in the waiting room, painted block
    # with a small high window in the garage
    bs.wall_with_window("ENV_wall_back_hall", (bs.XF - 0.02, 7.3), (Y1, Y1 + T), (-0.02, WALL_H), HALL_WIN[:2],
                        HALL_WIN[2:], plaster)
    bs.wall_with_window("ENV_wall_back_garage", (7.3, XR), (Y1, Y1 + T), (-0.02, WALL_H), GAR_WIN[:2], GAR_WIN[2:],
                        block)
    box("ENV_cap_back_house", (XR - bs.XF + 0.02, T + 0.02, 0.03), ((XR + bs.XF) / 2, Y1 + T / 2, WALL_H + 0.015),
        cap, bevel=0.006)
    bs.wainscot("ENV_wains_back_hall", "x", HX0, HX1, Y1)
    joints = Batch("ENV_block_joints")
    mm = hm("mortar", rough=0.9)
    for k in range(1, 16):
        z = k * 0.2
        runs = ((GX0, GAR_WIN[0]), (GAR_WIN[1], GX1)) if GAR_WIN[2] - 0.01 < z < GAR_WIN[3] + 0.01 else ((GX0, GX1),)
        for a, b in runs:
            joints.box((b - a, 0.002, 0.008), ((a + b) / 2, Y1 - 0.001, z), mm)
        for j in range(16):
            x = GX0 + (j + (0.5 if k % 2 else 0.0)) * 0.4
            in_window = GAR_WIN[0] - 0.01 < x < GAR_WIN[1] + 0.01 and GAR_WIN[2] < z < GAR_WIN[3] + 0.2
            if GX0 + 0.02 < x < GX1 - 0.02 and not in_window:
                joints.box((0.008, 0.002, 0.2), (x, Y1 - 0.001, z - 0.1), mm)
    joints.make()

    # the walls between the rooms, cut low, with a door in each
    for name, door in (("A", DOOR_A), ("B", DOOR_B)):
        x0 = 3.0 if name == "A" else HX1
        for k, (a, b) in enumerate(((YF, door[0]), (door[1], Y1))):
            if name == "A":
                slab(f"ENV_wall_A{k}", x0, x0 + T, a, b, CUT, plaster)
            else:
                slab(f"ENV_wall_B{k}", x0, x0 + T / 2, a, b, CUT, plaster, cap=False)
                slab(f"ENV_wall_B{k}g", x0 + T / 2, x0 + T, a, b, CUT, block, cap=False)
                box(f"ENV_wall_B{k}_cap", (T + 0.02, b - a + 0.02, 0.03), (x0 + T / 2, (a + b) / 2, CUT + 0.015), cap,
                    bevel=0.006)
        fm = mat("frame", rough=0.6)
        for k, y in enumerate(door):                       # casings lining both jambs
            s = 1 if k == 0 else -1
            box(f"ENV_door{name}_casing_{k}", (T + 0.04, 0.07, CUT - 0.01), (x0 + T / 2, y - s * 0.031, (CUT - 0.01) / 2),
                fm, bevel=0.006)
        box(f"ENV_door{name}_sill", (T, door[1] - door[0], 0.012), (x0 + T / 2, sum(door) / 2, 0.006), fm, bevel=0.003)
    for k, (a, b) in enumerate(((YW, DOOR_A[0] - 0.066), (DOOR_A[1] + 0.066, Y1))):
        panelling(f"ENV_wains_A{k}s", "y", a, b, 3.0, -1)           # study side
        panelling(f"ENV_wains_A{k}h", "y", a, b, HX0, 1)            # waiting-room side
    for k, (a, b) in enumerate(((YW, DOOR_B[0] - 0.066), (DOOR_B[1] + 0.066, Y1))):
        panelling(f"ENV_wains_B{k}h", "y", a, b, HX1, -1)
    # the garage's side wall, block inside and brick outside
    slab("ENV_wall_right_in", GX1, GX1 + T / 2, YF, Y1, CUT, block, cap=False)
    slab("ENV_wall_right_out", GX1 + T / 2, XR + EPS, YF, Y1, CUT, brk, cap=False)
    box("ENV_wall_right_cap", (T + 0.02, Y1 - YF + 0.02, 0.03), (GX1 + T / 2, (Y1 + YF) / 2, CUT + 0.015), cap,
        bevel=0.006)

    # front walls, cut at 0.3 m: plaster inside, brick outside; a door gap in the waiting room and
    # the garage's open front between two short wall ends
    paint = mat("wainscot", rough=0.6)
    for k, (a, b, inner, skirting) in enumerate(((X0 - T, 3.0, plaster, True), (3.0, FRONT_DOOR[0], plaster, True),
                                                 (FRONT_DOOR[1], HX1, plaster, True), (HX1, SHUTTER[0], block, False),
                                                 (SHUTTER[1], XR, block, False))):
        a0 = a + EPS if k == 0 else a                     # just inside the study's left wall
        slab(f"ENV_front_{k}_in", a0, b, YF + T / 2, YW, LOW, inner, cap=False)
        slab(f"ENV_front_{k}_out", a0, b, YF - EPS, YF + T / 2, LOW, brk, cap=False)
        box(f"ENV_front_{k}_cap", (b - a + 0.02, T + 0.02, 0.03), ((a + b) / 2, YF + T / 2, LOW + 0.015), cap, bevel=0.006)
        if skirting:
            lo, hi = max(a, X0 if k == 0 else HX0), min(b, 3.0 if k == 0 else HX1)
            box(f"ENV_front_{k}_skirting", (hi - lo, 0.024, 0.13), ((lo + hi) / 2, YW + 0.012, 0.065), paint, bevel=0.004)
    fm = mat("frame", rough=0.6)
    box("ENV_front_door_sill", (FRONT_DOOR[1] - FRONT_DOOR[0], T, 0.015), (sum(FRONT_DOOR) / 2, YF + T / 2, 0.0075), fm,
        bevel=0.003)
    for k, x in enumerate(FRONT_DOOR):
        s = 1 if k == 0 else -1
        box(f"ENV_front_door_casing_{k}", (0.07, T + 0.04, LOW + 0.04), (x - s * 0.031, YF + T / 2, (LOW + 0.04) / 2), fm,
            bevel=0.006)
    # guide rails for the steel shutter (p.325: one wall of his garage was a steel shutter)
    st = mat("steel", rough=0.45, metal=0.7)
    for k, x in enumerate(SHUTTER):
        s = 1 if k == 0 else -1
        box(f"ENV_shutter_rail_{k}", (0.05, 0.09, LOW + 0.06), (x + s * 0.025, YF + 0.1, (LOW + 0.06) / 2), st, bevel=0.004)
    box("ENV_shutter_track", (SHUTTER[1] - SHUTTER[0], 0.06, 0.008), (sum(SHUTTER) / 2, YF + 0.1, 0.004), st, bevel=0.002)


def window(prefix, x0, x1, z0, z1, steel=False):
    """A sash window like the study's (or a steel-framed one), on the back wall."""
    fm = mat("black_metal", rough=0.4, metal=0.6) if steel else mat("frame", rough=0.6)
    xc = (x0 + x1) / 2
    if not steel:
        box(f"{prefix}_casing_top", (x1 - x0 + 0.16, 0.025, 0.08), (xc, Y1 - 0.0125, z1 + 0.04), fm, bevel=0.006)
        for s, x in ((-1, x0), (1, x1)):
            box(f"{prefix}_casing_{s}", (0.08, 0.025, z1 - z0), (x + s * 0.04, Y1 - 0.0125, (z0 + z1) / 2), fm, bevel=0.006)
        box(f"{prefix}_apron", (x1 - x0 + 0.12, 0.025, 0.08), (xc, Y1 - 0.0125, z0 - 0.08), fm, bevel=0.005)
    if steel:
        box(f"{prefix}_sill", (x1 - x0 + 0.06, T, 0.04), (xc, Y1 + T / 2, z0 - 0.02), mat("trim", rough=0.55), bevel=0.008)
    else:
        box(f"{prefix}_sill", (x1 - x0 + 0.24, 0.18, 0.04), (xc, Y1 + 0.01, z0 - 0.02), fm, bevel=0.008, segs=3)
    ys, w = Y1 + 0.12, 0.05 if not steel else 0.03
    box(f"{prefix}_sash_top", (x1 - x0, 0.04, w), (xc, ys, z1 - w / 2), fm, bevel=0.004)
    box(f"{prefix}_sash_bot", (x1 - x0, 0.04, w), (xc, ys, z0 + w / 2), fm, bevel=0.004)
    for s, x in ((-1, x0), (1, x1)):
        box(f"{prefix}_sash_{s}", (w, 0.04, z1 - z0 - 2 * w), (x - s * w / 2, ys, (z0 + z1) / 2), fm, bevel=0.004)
    if steel:
        for k in range(1, 4):
            box(f"{prefix}_bar_{k}", (0.018, 0.03, z1 - z0 - 2 * w), (x0 + (x1 - x0) * k / 4, ys, (z0 + z1) / 2), fm,
                bevel=0.002)
    else:
        box(f"{prefix}_mullion_v", (0.035, 0.036, z1 - z0 - 2 * w), (xc, ys, (z0 + z1) / 2), fm, bevel=0.003)
        box(f"{prefix}_mullion_h", (x1 - x0 - 2 * w, 0.036, 0.035), (xc, ys, z0 + (z1 - z0) * 0.58), fm, bevel=0.003)


# ---------------------------------------------------------------- the study: a place for music

def build_music_corner():
    """An old turntable and amplifier on a low cabinet between two speakers, by the study's left
    wall (pp.324, 394)."""
    wd, dd = mat("cabinet", rough=0.55), mat("desk_dark", rough=0.6)
    st, bk = hm("chrome", rough=0.25, metal=1.0), mat("black_metal", rough=0.4, metal=0.6)
    xb, xf, y0, y1 = X0 + 0.045, X0 + 0.46, -2.55, -1.95
    xc, yc = (xb + xf) / 2, (y0 + y1) / 2
    carcass = Batch("MUSIC_cabinet")
    for z in (0.06, 0.53):
        carcass.box((xf - xb, y1 - y0, 0.025), (xc, yc, z + 0.0125), wd)
    for y in (y0 + 0.0125, y1 - 0.0125):
        carcass.box((xf - xb, 0.025, 0.47), (xc, y, 0.06 + 0.025 + 0.2225), wd)
    carcass.box((0.012, y1 - y0, 0.47), (xb + 0.006, yc, 0.3075), dd)
    carcass.box((xf - xb - 0.02, y1 - y0 - 0.02, 0.06), (xc - 0.01, yc, 0.03), dd)
    parts = [carcass.make(bevel=0.004, segs=1)]
    # the amplifier inside, its brushed front toward the room
    face = xc - 0.02 + 0.175
    parts.append(box("MUSIC_amp", (0.34, 0.5, 0.11), (xc - 0.02, yc, 0.085 + 0.055), bk, bevel=0.006))
    parts.append(box("MUSIC_amp_face", (0.01, 0.5, 0.11), (face, yc, 0.14), st, bevel=0.003))
    for k, y in enumerate((yc - 0.16, yc + 0.16)):
        parts.append(cyl(f"MUSIC_knob_{k}", 0.022, 0.03, (face + 0.015, y, 0.14), bk, n=16, rot=(0, math.pi / 2, 0)))
    parts.append(box("MUSIC_amp_meter", (0.006, 0.14, 0.04), (face + 0.006, yc, 0.15), mat("bulb", emit=6.0), bevel=0.002))
    # the turntable on top
    zt = 0.555
    parts.append(box("MUSIC_tt_plinth", (0.36, 0.46, 0.07), (xc, yc, zt + 0.035), dd, bevel=0.01, segs=2))
    parts.append(cyl("MUSIC_tt_platter", 0.15, 0.02, (xc, yc - 0.03, zt + 0.08), st, n=40))
    parts.append(cyl("MUSIC_tt_record", 0.148, 0.004, (xc, yc - 0.03, zt + 0.092), hm("record", rough=0.25), n=40))
    parts.append(cyl("MUSIC_tt_label", 0.045, 0.005, (xc, yc - 0.03, zt + 0.093), mat("pin", rough=0.5), n=24))
    parts.append(cyl("MUSIC_tt_pivot", 0.018, 0.04, (xc + 0.12, yc + 0.17, zt + 0.09), st, n=12))
    parts.append(tube("MUSIC_tt_arm", [(xc + 0.12, yc + 0.17, zt + 0.11), (xc + 0.1, yc + 0.06, zt + 0.108),
                                       (xc + 0.06, yc - 0.02, zt + 0.1)], 0.005, st, n=6))
    # two floor-standing speakers, the drivers toward the room
    for k, y in enumerate((y0 - 0.15, y1 + 0.15)):
        h = 0.84
        parts.append(box(f"MUSIC_spk_{k}", (0.24, 0.24, h), (xb + 0.12, y, h / 2 + 0.03), wd, bevel=0.01, segs=2))
        parts.append(box(f"MUSIC_spk_face_{k}", (0.01, 0.21, h - 0.06), (xb + 0.245, y, h / 2 + 0.03), dd, bevel=0.003))
        for j, (z, r) in enumerate(((0.62, 0.035), (0.36, 0.085))):
            parts.append(lathe(f"MUSIC_drv_{k}{j}", [(0, 0), (r, 0), (r + 0.006, 0.006), (r, 0.012), (r * 0.4, 0.004),
                                                     (0, 0.008)], (xb + 0.25, y, z), hm("cone", rough=0.6), n=24,
                               rot=(0, math.pi / 2, 0)))
    group("music", parts)


# ---------------------------------------------------------------- the waiting room

def chair(prefix, cx, cy, yaw, seat=0.40):
    """A wooden chair facing -y before it is turned by yaw (degrees, toward +x)."""
    wd, cu = mat("chair", rough=0.55), mat("cushion", rough=0.7)
    parts = [box(f"{prefix}_seat", (0.44, 0.42, 0.035), (cx, cy, seat - 0.0175), wd, bevel=0.01, segs=3),
             box(f"{prefix}_cushion", (0.38, 0.36, 0.03), (cx, cy - 0.01, seat + 0.015), cu, bevel=0.012, segs=3)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(cyl(f"{prefix}_leg_{sx}{sy}", 0.015, seat - 0.035, (cx + sx * 0.18, cy + sy * 0.17, (seat - 0.035) / 2),
                             wd, n=12, r2=0.02))
        parts.append(cyl(f"{prefix}_rung_{sx}", 0.008, 0.34, (cx + sx * 0.18, cy, 0.11), wd, n=10, rot=(math.pi / 2, 0, 0)))
    yb, zb = cy + 0.17, seat
    back = [box(f"{prefix}_post_{sx}", (0.034, 0.034, 0.42), (cx + sx * 0.18, yb, zb + 0.21), wd, bevel=0.006)
            for sx in (-1, 1)]
    back += [box(f"{prefix}_crest", (0.42, 0.03, 0.08), (cx, yb, zb + 0.39), wd, bevel=0.01, segs=3),
             box(f"{prefix}_rail", (0.36, 0.022, 0.03), (cx, yb, zb + 0.12), wd, bevel=0.005)]
    back += [cyl(f"{prefix}_spindle_{k}", 0.008, 0.24, (cx + k * 0.085, yb, zb + 0.245), wd, n=10) for k in (-1, 0, 1)]
    turn(back, (cx, yb, zb), (math.radians(-8), 0, 0))
    parts += back
    turn(parts, (cx, cy, 0), (0, 0, math.radians(yaw)))
    return parts


def ccw(poly):
    """A polygon in the x-z plane wound counter-clockwise, as prism_xz needs."""
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))
    return poly if area > 0 else poly[::-1]


def soft(ob, width, segs=3):
    """Round off a part's edges."""
    mod = ob.modifiers.new("bevel", "BEVEL")
    mod.width, mod.segments, mod.limit_method, mod.harden_normals = width, segs, "ANGLE", True
    return ob


def coat(prefix, top, yaw):
    """A wool coat hung by its collar at `top`, its front turned by `yaw` (0 faces -y): body,
    sleeves with cuffs, lapels, buttons and pocket flaps, so that it reads as a coat."""
    wool, dark = hm("coat", rough=0.95, detail="fabric"), hm("coat_dark", rough=0.95, detail="fabric")
    t = Vector(top)
    body = [(-0.25, -0.97), (0.25, -0.97), (0.235, -0.62), (0.205, -0.30), (0.20, -0.17), (0.185, -0.095),
            (0.14, -0.06), (0.075, -0.035), (0.03, -0.02), (-0.03, -0.02), (-0.075, -0.035), (-0.14, -0.06),
            (-0.185, -0.095), (-0.20, -0.17), (-0.205, -0.30), (-0.235, -0.62)]
    parts = [soft(prism_xz(f"{prefix}_body", ccw(body), -0.045, 0.045, wool, loc=tuple(t)), 0.018)]
    lapel = [(0.012, -0.36), (0.13, -0.15), (0.10, -0.095), (0.075, -0.09), (0.08, -0.035), (0.035, -0.022),
             (0.03, -0.12)]
    for s, side in ((1, "r"), (-1, "l")):
        parts.append(soft(prism_xz(f"{prefix}_lapel_{side}", ccw([(s * x, z) for x, z in lapel]), -0.056, -0.04, dark,
                                   loc=tuple(t)), 0.004, segs=2))
        sleeve = [t + Vector((s * x, y, z)) for x, y, z in ((0.165, -0.01, -0.105), (0.198, -0.022, -0.30),
                                                             (0.21, -0.03, -0.50), (0.208, -0.034, -0.64))]
        parts.append(tube(f"{prefix}_sleeve_{side}", sleeve, [0.04, 0.048, 0.046, 0.044], wool, n=12))
        parts.append(cyl(f"{prefix}_cuff_{side}", 0.047, 0.05, tuple(sleeve[-1] + Vector((0, 0, 0.012))), dark, n=12))
        parts.append(box(f"{prefix}_pocket_{side}", (0.11, 0.008, 0.032), tuple(t + Vector((s * 0.105, -0.049, -0.66))),
                         dark, bevel=0.003))
    parts.append(box(f"{prefix}_edge", (0.007, 0.006, 0.6), tuple(t + Vector((0.012, -0.046, -0.665))), dark, bevel=0))
    for k, z in enumerate((-0.42, -0.56, -0.70)):
        parts.append(cyl(f"{prefix}_button_{k}", 0.014, 0.008, tuple(t + Vector((0.036, -0.05, z))),
                         mat("desk_dark", rough=0.5), n=12, rot=(math.pi / 2, 0, 0)))
    turn(parts, tuple(t), (0, 0, yaw))
    return parts


def build_waiting_room():
    window("HWIN", *HALL_WIN)
    wd = hm("bench", rough=0.6, detail="wood")

    # a long, plain wooden bench under the window (p.610)
    cx, cy, L, zs = sum(HALL_WIN[:2]) / 2, Y1 - 0.25, 1.9, 0.40
    parts = [box("HBENCH_seat", (L, 0.38, 0.045), (cx, cy - 0.02, zs - 0.0225), wd, bevel=0.008)]
    for sx in (-1, 1):
        x = cx + sx * (L / 2 - 0.12)
        for sy, yy in ((-1, cy - 0.17), (1, cy + 0.14)):
            parts.append(box(f"HBENCH_leg_{sx}{sy}", (0.05, 0.05, zs - 0.045), (x, yy, (zs - 0.045) / 2), wd, bevel=0.005))
        parts.append(box(f"HBENCH_rail_{sx}", (0.04, 0.31, 0.05), (x, cy - 0.015, 0.12), wd, bevel=0.004))
        parts.append(box(f"HBENCH_post_{sx}", (0.05, 0.045, 0.47), (x, cy + 0.155, zs + 0.235), wd, bevel=0.005))
    parts.append(box("HBENCH_stretcher", (L - 0.24, 0.035, 0.05), (cx, cy - 0.015, 0.12), wd, bevel=0.004))
    for k, z in enumerate((zs + 0.22, zs + 0.40)):
        parts.append(box(f"HBENCH_slat_{k}", (L - 0.08, 0.025, 0.09), (cx, cy + 0.18, z), wd, bevel=0.006))
    group("waiting_bench", parts)

    # the table where the visitor writes the letter, and its chair
    wt, dd, br = mat("desk", rough=0.55), mat("desk_dark", rough=0.6), mat("brass", rough=0.35, metal=0.85)
    tx, ty, top = 5.65, -0.25, 0.70
    parts = [box("HTABLE_top", (0.84, 0.56, 0.03), (tx, ty, top - 0.015), wt, bevel=0.008, segs=3),
             box("HTABLE_apron", (0.74, 0.46, 0.07), (tx, ty, top - 0.065), wt, bevel=0.004)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(cyl(f"HTABLE_leg_{sx}{sy}", 0.016, top - 0.03, (tx + sx * 0.35, ty + sy * 0.21, (top - 0.03) / 2),
                             wt, n=12, r2=0.024))
    pm, rule, ink = mat("paper"), mat("rule"), mat("ink", rough=0.35)
    c, yaw = (tx - 0.08, ty - 0.04, top + 0.001), math.radians(6)
    parts.append(box("HTABLE_sheet", (0.21, 0.29, 0.002), c, pm, bevel=0, rot=(0, 0, yaw)))
    lines = Batch("HTABLE_lines")
    for j in range(7):
        lines.box((0.17, 0.0015, 0.0004), on(c, yaw, (0, 0.1 - j * 0.03, 0.0012)), rule, rot=(0, 0, yaw))
    parts.append(lines.make())
    parts.append(box("HTABLE_envelope", (0.22, 0.11, 0.003), (tx + 0.24, ty + 0.12, top + 0.0015), mat("paper_old"),
                     bevel=0, rot=(0, 0, math.radians(-12))))
    parts.append(lathe("HTABLE_ink", [(0, 0), (0.028, 0), (0.03, 0.004), (0.03, 0.04), (0.012, 0.05), (0.012, 0.062),
                                      (0, 0.062)], (tx + 0.28, ty - 0.12, top), mat("pen_blue", rough=0.2), n=20))
    parts.append(cyl("HTABLE_pen", 0.005, 0.14, (tx + 0.1, ty - 0.1, top + 0.005), ink, n=10,
                     rot=(0, math.pi / 2, math.radians(70))))
    # a small lamp for the evenings
    lx, ly = tx - 0.3, ty + 0.17
    parts += [lathe("HTABLE_lamp_base", [(0, 0), (0.06, 0), (0.06, 0.012), (0.02, 0.03), (0, 0.032)], (lx, ly, top), br, n=24),
              cyl("HTABLE_lamp_stem", 0.007, 0.26, (lx, ly, top + 0.15), br, n=10),
              lathe("HTABLE_lamp_shade", [(0.11, 0.0), (0.06, 0.12), (0.056, 0.12), (0.104, 0.0)], (lx, ly, top + 0.2),
                    mat("shade2", rough=0.9), n=32, sharp=30),
              lathe("HTABLE_lamp_bulb", [(0, 0.02), (0.025, 0.035), (0.03, 0.06), (0, 0.09)], (lx, ly, top + 0.2),
                    mat("bulb", emit=6.0), n=16)]
    group("letter_table", parts)
    group("letter_chair", chair("HCHAIR", tx + 0.02, ty + 0.5, 4))

    # low case of the books he recommends (p.183, p.734), facing the room
    wm = mat("shelf", rough=0.55)
    xb, xf, y0, y1, hgt = HX0 + 0.045, HX0 + 0.37, 1.45, 2.85, 0.9
    xc, yc = (xb + xf) / 2, (y0 + y1) / 2
    parts = [box("HBOOKS_plinth", (xf - xb - 0.02, y1 - y0 - 0.02, 0.06), (xc - 0.01, yc, 0.03), dd, bevel=0.004),
             box("HBOOKS_back", (0.012, y1 - y0, hgt - 0.06), (xb + 0.006, yc, 0.06 + (hgt - 0.06) / 2), wm, bevel=0),
             box("HBOOKS_top", (xf - xb + 0.03, y1 - y0 + 0.03, 0.03), (xc + 0.015, yc, hgt + 0.015), wm, bevel=0.006)]
    for k, y in enumerate((y0 + 0.0125, y1 - 0.0125)):
        parts.append(box(f"HBOOKS_side_{k}", (xf - xb, 0.025, hgt), (xc, y, hgt / 2), wm, bevel=0.004))
    levels = (0.06, 0.34, 0.62)
    for k, z in enumerate(levels):
        parts.append(box(f"HBOOKS_board_{k}", (xf - xb - 0.012, y1 - y0 - 0.05, 0.025), (xc + 0.006, yc, z + 0.0125), wm,
                         bevel=0.003))
    books = Batch("HBOOKS_books")
    cols = [mat(f"book{i}", c, rough=0.8, detail="fabric") for i, c in enumerate(bs.BOOK_COLORS)]
    for z0 in [z + 0.025 for z in levels]:
        y = y0 + 0.03
        while True:
            t, h, dpt = rng.uniform(0.024, 0.05), rng.uniform(0.19, 0.25), rng.uniform(0.15, 0.22)
            if y + t > y1 - 0.03:
                break
            if rng.random() < 0.08:
                y += rng.uniform(0.04, 0.09)
                continue
            books.box((dpt, t, h), (xf - 0.012 - dpt / 2, y + t / 2, z0 + h / 2), rng.choice(cols))
            y += t + rng.uniform(0.0, 0.003)
    parts.append(books.make(bevel=0.0025, segs=1))
    group("waiting_books", parts)

    # coat stand and umbrella stand by the front door, a mat inside it
    x, y = 6.75, -2.5
    parts = [lathe("HCOAT_base", [(0, 0), (0.2, 0), (0.2, 0.02), (0.06, 0.05), (0, 0.05)], (x, y, 0), dd, n=24),
             lathe("HCOAT_pole", [(0, 0.04), (0.026, 0.04), (0.021, 0.3), (0.019, 1.6), (0.026, 1.68), (0.03, 1.72),
                                  (0, 1.76)], (x, y, 0), dd, n=16)]
    for k in range(4):
        a = k / 4 * math.tau + 0.4
        d = Vector((math.cos(a), math.sin(a), 0))
        base = Vector((x, y, 0))
        parts.append(tube(f"HCOAT_hook_{k}", [base + Vector((0, 0, 1.6)) + d * 0.02, base + Vector((0, 0, 1.64)) + d * 0.1,
                                              base + Vector((0, 0, 1.7)) + d * 0.14], 0.009, br, n=8))
    a = 3 / 4 * math.tau + 0.4                          # a wool coat on the hook toward the door
    parts += coat("HCOAT", Vector((x, y, 1.71)) + Vector((math.cos(a), math.sin(a), 0)) * 0.17, a + math.pi / 2)
    hat_at = (x, y, 1.725)                              # and a felt hat on top
    hat = [lathe("HCOAT_hat", [(0, 0), (0.155, 0), (0.16, 0.008), (0.15, 0.016), (0.10, 0.02), (0.088, 0.03),
                               (0.085, 0.10), (0.06, 0.125), (0, 0.118)], hat_at, hm("hat", rough=0.9, detail="fabric"),
                 n=32),
           cyl("HCOAT_hat_band", 0.0905, 0.025, (x, y, hat_at[2] + 0.0425), hm("hat_band", rough=0.6), n=32, r2=0.0895)]
    turn(hat, hat_at, (math.radians(5), math.radians(-4), 0))
    parts += hat
    group("coat_stand", parts)
    ux, uy = 4.3, -2.55
    parts = [lathe("HUMB_pot", [(0, 0), (0.11, 0), (0.12, 0.02), (0.12, 0.46), (0.13, 0.48), (0.115, 0.48), (0.108, 0.47),
                                (0.108, 0.03), (0, 0.03)], (ux, uy, 0), hm("ceramic", rough=0.3), n=32)]
    for k, (dx, dy, lean, col) in enumerate(((-0.03, 0.02, 9, "umbrella_a"), (0.03, -0.02, -7, "umbrella_b"))):
        um = hm(col, rough=0.8, detail="fabric")
        u = [lathe(f"HUMB_canopy_{k}", [(0, 0.12), (0.025, 0.2), (0.05, 0.62), (0.03, 0.74), (0, 0.76)],
                   (ux + dx, uy + dy, 0), um, n=8, sharp=20),
             cyl(f"HUMB_shaft_{k}", 0.006, 0.2, (ux + dx, uy + dy, 0.84), mat("black_metal"), n=8)]
        hc = Vector((ux + dx + 0.04, uy + dy, 0.98))
        hook = [Vector((ux + dx, uy + dy, 0.93))] + [hc + 0.04 * Vector((math.cos(math.radians(a)), 0, math.sin(math.radians(a))))
                                                     for a in range(180, -80, -20)]
        u.append(tube(f"HUMB_handle_{k}", hook, 0.01, mat("desk_dark"), n=8))
        turn(u, (ux + dx, uy + dy, 0.03), (math.radians(lean), math.radians(lean * 0.6), 0))
        parts += u
    group("umbrella_stand", parts)
    mm = hm("coir", rough=1.0, detail="fabric")
    group("door_mat", [box("HMAT", (0.9, 0.55, 0.014), (sum(FRONT_DOOR) / 2, YW + 0.34, 0.007), mm, bevel=0.004),
                       box("HMAT_edge", (0.86, 0.51, 0.002), (sum(FRONT_DOOR) / 2, YW + 0.34, 0.0145), mat("desk_dark"),
                           bevel=0)])

    # a wall light beside the window, and a plain clock: waiting is counted in minutes
    sx, sz = HALL_WIN[0] - 0.55, 1.9
    group("sconce", [
        lathe("HSCONCE_plate", [(0, 0), (0.05, 0), (0.05, 0.012), (0, 0.016)], (sx, Y1, sz - 0.08), br, n=24,
              rot=(math.pi / 2, 0, 0)),
        tube("HSCONCE_arm", [(sx, Y1 - 0.012, sz - 0.08), (sx, Y1 - 0.08, sz - 0.07), (sx, Y1 - 0.13, sz - 0.02)], 0.008, br,
             n=8),
        lathe("HSCONCE_shade", [(0, -0.02), (0.035, -0.015), (0.07, 0.04), (0.08, 0.11), (0.074, 0.11), (0.064, 0.045),
                                (0.03, 0.0), (0, -0.004)], (sx, Y1 - 0.13, sz - 0.04), hm("sconce", rough=0.3, emit=2.5),
              n=24)])
    cx_, cz = HALL_WIN[1] + 0.55, 2.0
    face, ink2 = mat("label"), mat("ink")
    parts = [lathe("HCLOCK_rim", [(0, 0), (0.15, 0), (0.155, 0.02), (0.148, 0.04), (0.138, 0.04), (0.136, 0.034), (0, 0.034)],
                   (cx_, Y1, cz), dd, n=40, rot=(math.pi / 2, 0, 0)),
             lathe("HCLOCK_face", [(0, 0.033), (0.137, 0.033), (0.137, 0.035), (0, 0.035)], (cx_, Y1, cz), face, n=40,
                   rot=(math.pi / 2, 0, 0))]
    ticks = Batch("HCLOCK_ticks")
    for k in range(12):
        a = k / 12 * math.tau
        big = k % 3 == 0
        ticks.box((0.006 if big else 0.004, 0.002, 0.024 if big else 0.014),
                  (cx_ + 0.112 * math.sin(a), Y1 - 0.036, cz + 0.112 * math.cos(a)), ink2, rot=(0, a, 0))
    parts.append(ticks.make())
    for k, (length, width, ang) in enumerate(((0.07, 0.008, 5 / 12 * 360 + 20), (0.105, 0.005, 40 / 60 * 360))):
        a = math.radians(ang)
        parts.append(box(f"HCLOCK_hand_{k}", (width, 0.002, length),
                         (cx_ + (length / 2 - 0.012) * math.sin(a), Y1 - 0.038 - k * 0.002, cz + (length / 2 - 0.012) * math.cos(a)),
                         ink2, bevel=0, rot=(0, a, 0)))
    group("waiting_clock", parts)


# ---------------------------------------------------------------- the car

def arch(cx, cz, r, zb, n=10):
    """A wheel arch cut up into the bottom edge of the side profile, from rear to front."""
    a = math.asin((zb - cz) / r)
    return [(cx + r * math.cos(t), cz + r * math.sin(t)) for t in (math.pi - a + (2 * a - math.pi) * k / n for k in range(n + 1))]


def build_car():
    """An old silver two-seater with its top folded down, drawn without any brand mark (pp.377, 394).
    Built facing +x at the origin, then turned nose to the street."""
    paint, inside = hm("car_paint", rough=0.3, metal=0.5), hm("car_inside", rough=0.7)
    chrome, tire, dark = hm("chrome", rough=0.15, metal=1.0), hm("tire", rough=0.85), mat("black_metal", rough=0.4, metal=0.6)
    seat = hm("car_seat", rough=0.55, detail="leather")
    AXF, AXR, AZ, HW = 1.30, -1.25, 0.325, 0.88
    prof = [(-2.10, 0.30), (-1.96, 0.22)] + arch(AXR, AZ, 0.385, 0.22) + arch(AXF, AZ, 0.385, 0.22) + [
        (2.00, 0.22), (2.15, 0.30), (2.20, 0.45), (2.16, 0.58), (2.02, 0.66), (1.60, 0.71), (1.00, 0.75),
        (0.50, 0.78), (-0.30, 0.80), (-1.10, 0.82), (-1.70, 0.80), (-2.02, 0.72), (-2.16, 0.58), (-2.18, 0.42)]
    body = prism_xz("CAR_body", prof, -HW, HW, paint)
    cut = box("CAR_cut", (1.40, 1.46, 1.0), (-0.27, 0, 1.0), inside, bevel=0)
    mod = body.modifiers.new("cockpit", "BOOLEAN")
    mod.operation, mod.object, mod.solver = "DIFFERENCE", cut, "EXACT"
    if hasattr(mod, "material_mode"):
        mod.material_mode = "TRANSFER"
    apply_modifiers(body)
    bpy.data.objects.remove(cut, do_unlink=True)
    body.data.shade_smooth()
    body.data.set_sharp_from_angle(angle=math.radians(35))
    bev = body.modifiers.new("bevel", "BEVEL")
    bev.width, bev.segments, bev.limit_method, bev.harden_normals = 0.035, 3, "ANGLE", True
    P = [body, box("CAR_chassis", (3.9, 1.22, 0.24), (0.0, 0, 0.37), inside, bevel=0.02)]

    # the cockpit: two leather seats, a dashboard with the head unit he rebuilt, the wheel
    for k, sy in enumerate((0.36, -0.36)):
        P.append(box(f"CAR_seat_{k}", (0.50, 0.46, 0.12), (-0.50, sy, 0.56), seat, bevel=0.035, segs=3))
        back = box(f"CAR_seatback_{k}", (0.13, 0.46, 0.52), (-0.82, sy, 0.84), seat, bevel=0.04, segs=3)
        turn([back], (-0.82, sy, 0.6), (0, math.radians(-14), 0))
        P.append(back)
    P.append(box("CAR_console", (0.72, 0.16, 0.14), (-0.22, 0, 0.57), inside, bevel=0.02))
    P.append(cyl("CAR_gear", 0.008, 0.14, (-0.05, 0, 0.7), chrome, n=8))
    P.append(lathe("CAR_gear_knob", [(0, 0), (0.02, 0.004), (0.024, 0.02), (0.016, 0.038), (0, 0.04)], (-0.05, 0, 0.76),
                   mat("desk_dark"), n=12))
    P.append(box("CAR_dash", (0.22, 1.40, 0.2), (0.32, 0, 0.72), inside, bevel=0.03, segs=2))
    for k, y in enumerate((0.29, 0.43)):
        P.append(lathe(f"CAR_dial_{k}", [(0, 0), (0.042, 0), (0.046, 0.008), (0.04, 0.012), (0, 0.01)], (0.21, y, 0.75),
                       mat("label"), n=20, rot=(0, -math.pi / 2, 0)))
    P.append(box("CAR_headunit", (0.02, 0.2, 0.06), (0.205, 0.0, 0.70), dark, bevel=0.004))
    P.append(box("CAR_headunit_glow", (0.004, 0.11, 0.012), (0.194, 0.0, 0.712), mat("bulb", emit=6.0), bevel=0))
    for k, sy in enumerate((1, -1)):           # door speakers
        P.append(lathe(f"CAR_speaker_{k}", [(0, 0), (0.07, 0), (0.074, 0.006), (0.07, 0.01), (0.03, 0.004), (0, 0.006)],
                       (-0.3, sy * 0.728, 0.62), hm("cone", rough=0.6), n=24, rot=(sy * math.pi / 2, 0, 0)))
    c = Vector((0.02, 0.36, 0.86))
    a = Vector((-0.906, 0, 0.423))
    u, v = Vector((0, 1, 0)), a.cross(Vector((0, 1, 0))).normalized()
    P.append(tube("CAR_wheel", [c + 0.17 * (math.cos(t) * u + math.sin(t) * v) for t in (k / 32 * math.tau for k in range(33))],
                  0.013, dark, n=8, caps=False))
    for k, d in enumerate((u, -u, v)):
        P.append(tube(f"CAR_spoke_{k}", [c, c + d * 0.16], 0.008, chrome, n=6))
    P.append(tube("CAR_column", [c, Vector((0.30, 0.36, 0.72))], 0.02, dark, n=10))
    # windscreen in a chrome frame, the soft top folded behind the seats
    bx, tx_, bz, tz = 0.47, 0.22, 0.79, 1.13
    for sy in (-1, 1):
        P.append(tube(f"CAR_pillar_{sy}", [(bx, sy * 0.70, bz), (tx_, sy * 0.66, tz)], 0.016, chrome, n=8))
    P.append(tube("CAR_screen_top", [(tx_, -0.66, tz), (tx_ - 0.01, 0, tz + 0.012), (tx_, 0.66, tz)], 0.016, chrome, n=8))
    P.append(sheet("CAR_screen", [[(bx, -0.69, bz), (bx, 0.69, bz)], [(tx_, -0.65, tz), (tx_, 0.65, tz)]], glass(), 0.006))
    P.append(box("CAR_softtop", (0.34, 1.36, 0.13), (-1.17, 0, 0.87), hm("softtop", rough=0.9, detail="fabric"),
                 bevel=0.05, segs=3))
    # wheels with chrome hubcaps
    tire_prof = [(0.20, -0.10), (0.27, -0.112), (0.31, -0.10), (0.325, -0.06), (0.325, 0.06), (0.31, 0.10), (0.27, 0.112),
                 (0.20, 0.10)]
    rim_prof = [(0, -0.06), (0.205, -0.06), (0.205, 0.07), (0.17, 0.09), (0.07, 0.085), (0.06, 0.11), (0, 0.115)]
    for i, ax in enumerate((AXF, AXR)):
        for sy in (-1, 1):
            loc, rot = (ax, sy * (HW - 0.115), AZ), (-sy * math.pi / 2, 0, 0)
            P.append(lathe(f"CAR_tire_{i}{sy}", tire_prof, loc, tire, n=32, rot=rot))
            P.append(lathe(f"CAR_rim_{i}{sy}", rim_prof, loc, chrome, n=32, rot=rot))
    # round lamps, a plain grille, chrome bumpers, blank plates: nothing that names a maker
    lens = hm("lens", rough=0.1)
    for sy in (-1, 1):
        lc = (2.12, sy * 0.58, 0.56)
        P.append(lathe(f"CAR_lamp_ring_{sy}", [(0, 0), (0.085, 0), (0.09, 0.02), (0.08, 0.035), (0, 0.035)], lc, chrome, n=24,
                       rot=(0, math.pi / 2, 0)))
        P.append(lathe(f"CAR_lamp_lens_{sy}", [(0, 0.02), (0.075, 0.02), (0.06, 0.05), (0, 0.06)], lc, lens, n=24,
                       rot=(0, math.pi / 2, 0)))
        P.append(box(f"CAR_taillight_{sy}", (0.04, 0.2, 0.09), (-2.165, sy * 0.62, 0.6), hm("taillight", rough=0.2, emit=0.3),
                     bevel=0.01))
        P.append(tube(f"CAR_mirror_stalk_{sy}", [(0.42, sy * 0.80, 0.80), (0.40, sy * 0.87, 0.9)], 0.008, chrome, n=6))
        P.append(lathe(f"CAR_mirror_{sy}", [(0, 0), (0.05, 0), (0.05, 0.02), (0, 0.03)], (0.40, sy * 0.88, 0.92), chrome,
                       n=16, rot=(0, -math.pi / 2, 0)))
        for k, x in enumerate((0.40, -0.93)):
            P.append(box(f"CAR_doorline_{sy}{k}", (0.008, 0.004, 0.46), (x, sy * (HW + 0.001), 0.53), dark, bevel=0))
        P.append(box(f"CAR_handle_{sy}", (0.1, 0.012, 0.02), (-0.78, sy * (HW + 0.006), 0.7), chrome, bevel=0.005))
    P.append(box("CAR_grille", (0.03, 0.56, 0.12), (2.19, 0, 0.42), hm("grille", rough=0.5), bevel=0.01))
    for k, z in enumerate((0.39, 0.42, 0.45)):
        P.append(box(f"CAR_grille_bar_{k}", (0.012, 0.54, 0.01), (2.205, 0, z), chrome, bevel=0.003))
    front = [(2.02, -0.84), (2.16, -0.76), (2.235, -0.45), (2.245, 0), (2.235, 0.45), (2.16, 0.76), (2.02, 0.84)]
    rear = [(-2.0, -0.84), (-2.1, -0.76), (-2.16, -0.45), (-2.168, 0), (-2.16, 0.45), (-2.1, 0.76), (-2.0, 0.84)]
    for k, pts in enumerate((front, rear)):
        P.append(tube(f"CAR_bumper_{k}", [(x, y, 0.32) for x, y in pts], 0.032, chrome, n=10))
    pl = hm("plate", rough=0.5)
    P.append(box("CAR_plate_front", (0.008, 0.34, 0.11), (2.282, 0, 0.32), pl, bevel=0.004))
    P.append(box("CAR_plate_rear", (0.008, 0.34, 0.11), (-2.19, 0, 0.48), pl, bevel=0.004))
    P.append(cyl("CAR_exhaust", 0.03, 0.14, (-2.12, -0.5, 0.26), chrome, n=12, rot=(0, math.pi / 2, 0)))
    g = group("car", P)
    g.location, g.rotation_euler = (CAR_AT[0], CAR_AT[1], 0), (0, 0, -math.pi / 2)


# ---------------------------------------------------------------- bicycles

def wheel_parts(prefix, c, r, tire_m, rim_m, spokes=True, tire_r=0.018):
    c = Vector(c)
    P = [tube(prefix + "_tire", ring_pts(c, r - tire_r, n=48), tire_r, tire_m, n=8, caps=False),
         tube(prefix + "_rim", ring_pts(c, r - 2 * tire_r - 0.006, n=48), 0.007, rim_m, n=6, caps=False),
         cyl(prefix + "_hub", 0.018, 0.09, tuple(c), rim_m, n=12, rot=(math.pi / 2, 0, 0))]
    if spokes:
        sp = Batch(prefix + "_spokes")
        rr = r - 2 * tire_r - 0.006
        for k in range(18):
            t = k / 18 * math.tau
            sp.box((0.0025, 0.0025, rr), tuple(c + Vector((math.cos(t), 0, math.sin(t))) * rr / 2), rim_m,
                   rot=(0, math.pi / 2 - t, 0))
        P.append(sp.make())
    return P


def bicycle(prefix, paint, kind="city", spokes=True):
    """A bicycle at the origin, its wheels in the x-z plane, the front wheel toward +x and the chain
    on the -y side. kind: "city" (step-through frame, fenders, basket, kickstand) or "road"."""
    tire, steel = hm("tire", rough=0.85), hm("chrome", rough=0.2, metal=1.0)
    leather, dark = hm("saddle", rough=0.5, detail="leather"), mat("black_metal", rough=0.4, metal=0.6)
    R = 0.34
    rear, front = Vector((-0.52, 0, R)), Vector((0.53, 0, R))
    bb, st = Vector((-0.03, 0, 0.27)), Vector((-0.19, 0, 0.78))
    ht, hb = Vector((0.37, 0, 0.83)), Vector((0.41, 0, 0.69))
    P = wheel_parts(prefix + "_rear", rear, R, tire, steel, spokes) + wheel_parts(prefix + "_front", front, R, tire, steel, spokes)
    t = 0.016
    P.append(tube(prefix + "_down", [hb, bb], t, paint))
    P.append(tube(prefix + "_seat", [bb, st], t, paint))
    if kind == "city":
        P.append(tube(prefix + "_top", [ht.lerp(hb, 0.35), Vector((0.24, 0, 0.68)), Vector((0.06, 0, 0.54)),
                                        bb.lerp(st, 0.42)], t, paint))
    else:
        P.append(tube(prefix + "_top", [ht.lerp(hb, 0.15), st.lerp(bb, 0.06)], t, paint))
    P.append(tube(prefix + "_head", [hb - (ht - hb) * 0.1, ht + (ht - hb) * 0.15], 0.02, paint))
    for sy in (-1, 1):
        o = Vector((0, sy * 0.06, 0))
        P.append(tube(f"{prefix}_chainstay_{sy}", [bb + o * 0.4, rear + o], 0.009, paint))
        P.append(tube(f"{prefix}_seatstay_{sy}", [st.lerp(bb, 0.08) + o * 0.3, rear + o], 0.008, paint))
        P.append(tube(f"{prefix}_fork_{sy}", [hb + o * 0.4, Vector((0.47, 0, 0.52)) + o, front + o], 0.01, paint))
    top = st + (st - bb).normalized() * 0.1
    P.append(tube(prefix + "_post", [st, top], 0.011, steel))
    P.append(box(prefix + "_saddle", (0.25, 0.15, 0.05), tuple(top + Vector((-0.02, 0, 0.03))), leather, bevel=0.02))
    stem = ht + Vector((-0.02, 0, 0.14))
    P.append(tube(prefix + "_stem", [ht, stem], 0.011, steel))
    if kind == "city":
        bar = [stem + Vector(p) for p in ((-0.16, -0.29, -0.01), (-0.07, -0.24, 0), (0, -0.1, 0), (0, 0.1, 0),
                                          (-0.07, 0.24, 0), (-0.16, 0.29, -0.01))]
    else:
        half = [(0, 0, 0), (0, 0.2, 0), (0.08, 0.21, -0.02), (0.11, 0.21, -0.08), (0.08, 0.21, -0.14), (0.0, 0.21, -0.15),
                (-0.06, 0.21, -0.13)]
        bar = [stem + Vector((x, -y, z)) for x, y, z in reversed(half[1:])] + [stem + Vector(p) for p in half[1:]]
    P.append(tube(prefix + "_bar", bar, 0.011, steel))
    for k, (e, f) in enumerate(((bar[0], bar[1]), (bar[-1], bar[-2]))):
        P.append(tube(f"{prefix}_grip_{k}", [e, e + (e - f).normalized() * 0.1], 0.016, dark, n=8))
    cr = Vector((0, -0.055, 0))
    P.append(tube(prefix + "_ring", ring_pts(bb + cr, 0.09, n=24), 0.005, steel, n=6, caps=False))
    for sy, ang in ((-1, math.radians(-30)), (1, math.radians(150))):
        end = bb + Vector((0.165 * math.cos(ang), sy * 0.08, 0.165 * math.sin(ang)))
        P.append(tube(f"{prefix}_crank_{sy}", [bb + Vector((0, sy * 0.06, 0)), end], 0.009, steel))
        P.append(box(f"{prefix}_pedal_{sy}", (0.09, 0.08, 0.02), tuple(end + Vector((0, sy * 0.05, 0))), dark, bevel=0.004))
    for k, dz in enumerate((0.09, -0.09)):
        P.append(tube(f"{prefix}_chain_{k}", [bb + cr + Vector((0, 0, dz)), rear + cr + Vector((0, 0, dz * 0.45))], 0.004,
                      dark, n=4))
    if kind == "city":
        for k, (c, a0, a1) in enumerate(((rear, 15, 172), (front, 8, 165))):
            rows = []
            for j in range(17):
                a = math.radians(a0 + (a1 - a0) * j / 16)
                n = Vector((math.cos(a), 0, math.sin(a)))
                p = c + n * (R + 0.035)
                rows.append([p - n * 0.014 + Vector((0, -0.034, 0)), p + Vector((0, -0.018, 0)), p,
                             p + Vector((0, 0.018, 0)), p - n * 0.014 + Vector((0, 0.034, 0))])
            P.append(sheet(f"{prefix}_fender_{k}", rows, paint, 0.003))
        wick = hm("wicker", rough=0.95, detail="fabric")
        bc = Vector((0.62, 0, 0.93))
        bw, bd, bh, th = 0.30, 0.34, 0.20, 0.012
        bk = Batch(prefix + "_basket")
        bk.box((bw, bd, th), tuple(bc + Vector((0, 0, -bh / 2))), wick)
        for s in (-1, 1):
            bk.box((th, bd, bh), tuple(bc + Vector((s * (bw / 2 - th / 2), 0, 0))), wick)
            bk.box((bw, th, bh), tuple(bc + Vector((0, s * (bd / 2 - th / 2), 0))), wick)
        P.append(bk.make(bevel=0.003, segs=1))
        for sy in (-1, 1):
            P.append(tube(f"{prefix}_basket_strut_{sy}", [bc + Vector((0.08, sy * 0.1, -bh / 2)), front + Vector((0, sy * 0.06, 0))],
                          0.005, steel, n=5))
        P.append(tube(prefix + "_kickstand", [bb + Vector((-0.08, 0.04, -0.005)), Vector((-0.2, 0.18, 0.025))], 0.009, steel,
                      n=6))
        P.append(lathe(prefix + "_bell", [(0, 0), (0.022, 0), (0.024, 0.012), (0.012, 0.024), (0, 0.026)],
                       tuple(bar[3] + Vector((0, 0.04, 0.012))), steel, n=16))
    return P


def high_wheeler(prefix, paint, spokes=True):
    """The tall-wheeled bicycle on the book's cover, which is one of his models (colophon)."""
    tire, steel = hm("tire", rough=0.85), hm("chrome", rough=0.2, metal=1.0)
    leather, dark = hm("saddle", rough=0.5, detail="leather"), mat("black_metal", rough=0.4, metal=0.6)
    F, Rr = 0.62, 0.17
    front, rear = Vector((0.30, 0, F)), Vector((-0.80, 0, Rr))
    P = (wheel_parts(prefix + "_front", front, F, tire, steel, spokes, tire_r=0.02)
         + wheel_parts(prefix + "_rear", rear, Rr, tire, steel, spokes, tire_r=0.014))
    head = Vector((0.24, 0, 1.33))
    for sy in (-1, 1):
        P.append(tube(f"{prefix}_fork_{sy}", [head + Vector((0, sy * 0.03, 0)), front + Vector((0.01, sy * 0.07, 0.3)),
                                              front + Vector((0, sy * 0.07, 0))], 0.012, paint))
        end = front + Vector((0.13 * math.cos(math.radians(-60 if sy < 0 else 120)), sy * 0.1,
                              0.13 * math.sin(math.radians(-60 if sy < 0 else 120))))
        P.append(tube(f"{prefix}_crank_{sy}", [front + Vector((0, sy * 0.08, 0)), end], 0.01, steel))
        P.append(box(f"{prefix}_pedal_{sy}", (0.07, 0.07, 0.02), tuple(end + Vector((0, sy * 0.04, 0))), dark, bevel=0.004))
    bone = [front + Vector((0.71 * math.cos(a), 0, 0.71 * math.sin(a))) for a in
            (math.radians(97 + (205 - 97) * k / 12) for k in range(13))]
    bone.append(rear + Vector((0.02, 0, 0.02)))
    P.append(tube(prefix + "_backbone", bone, 0.017, paint, n=10))
    P.append(box(prefix + "_saddle", (0.2, 0.13, 0.05), tuple(bone[2] + Vector((-0.02, 0, 0.04))), leather, bevel=0.02))
    bar = [head + Vector(p) for p in ((-0.04, -0.32, 0.02), (0.0, -0.16, 0.07), (0.01, 0, 0.08), (0.0, 0.16, 0.07),
                                      (-0.04, 0.32, 0.02))]
    P.append(tube(prefix + "_bar", bar, 0.011, steel))
    for k, e in enumerate((bar[0], bar[-1])):
        P.append(cyl(f"{prefix}_grip_{k}", 0.02, 0.09, tuple(e + Vector((-0.02, 0, -0.03))), mat("desk_dark"), n=10,
                     rot=(0, math.radians(30), 0)))
    P.append(tube(prefix + "_step", [bone[8], bone[8] + Vector((0, -0.07, 0))], 0.01, steel, n=6))
    return P


def build_bike_shelf():
    """Shelves of fourteen cubbies for model bicycles (p.27, p.287): one fills each time a visitor
    marks a mission done. Four are filled here to show the idea, the cover's high-wheeler first."""
    wd, brass = mat("shelf", rough=0.55), mat("brass", rough=0.35, metal=0.85)
    x0, x1, yb, yf, zb, th, hh = 9.3, 11.9, Y1 - 0.005, Y1 - 0.27, 1.42, 0.025, 0.40
    n, cw = 7, (x1 - x0) / 7
    yc = (yb + yf) / 2
    parts = []
    for k in range(3):
        parts.append(box(f"MB_board_{k}", (x1 - x0 + th, yb - yf, th), ((x0 + x1) / 2, yc, zb + k * (hh + th) + th / 2), wd,
                         bevel=0.003))
    for k in range(n + 1):
        parts.append(box(f"MB_div_{k}", (th, yb - yf, 2 * hh + th), (x0 + k * cw, yc, zb + th + hh + th / 2), wd, bevel=0.003))
    parts.append(box("MB_back", (x1 - x0, 0.01, 2 * hh + 3 * th), ((x0 + x1) / 2, yb - 0.005, zb + hh + 1.5 * th),
                     mat("trim", rough=0.55), bevel=0))
    plates = Batch("MB_plates")
    for r in range(2):
        for k in range(n):
            plates.box((0.07, 0.003, 0.016), (x0 + (k + 0.5) * cw, yf - 0.0015, zb + r * (hh + th) + th / 2), brass)
    parts.append(plates.make())
    models = ((high_wheeler, "bike_black", 0.175), (bicycle, "bike_red", 0.19), (bicycle, "bike_green", 0.19),
              (bicycle, "bike_blue", 0.19))
    for k, (fn, col, s) in enumerate(models):
        x, z = x0 + (k + 0.5) * cw, zb + hh + 2 * th
        parts.append(box(f"MB_base_{k}", (0.3, 0.09, 0.016), (x, yc + 0.01, z + 0.008), mat("frame", rough=0.6), bevel=0.003))
        paint = hm(col, rough=0.35, metal=0.3)
        if fn is bicycle:
            P = bicycle(f"MB_model_{k}", paint, kind="road" if k != 2 else "city", spokes=False)
        else:
            P = fn(f"MB_model_{k}", paint, spokes=False)
        g = group(f"model_bicycle_{k}", P)
        g.scale = (s, s, s)
        g.location = (x + (0.004 if fn is high_wheeler else 0.0), yc + 0.01, z + 0.016)
    group("bike_shelf", parts)


# ---------------------------------------------------------------- the garage's back wall

def chain(name, a, b, m, link=0.046, wire=0.0055):
    """A taut chain of interlocking oval links from a to b."""
    a, b = Vector(a), Vector(b)
    d = b - a
    length = d.length
    d.normalize()
    side = d.cross(Vector((1, 0, 0)))
    side = (side if side.length > 1e-6 else d.cross(Vector((0, 1, 0)))).normalized()
    up = d.cross(side).normalized()
    n = max(2, int(length / (link * 0.72)))
    bt = Batch(name)
    for k in range(n):
        c = a + d * (length * (k + 0.5) / n)
        w = side if k % 2 == 0 else up
        pts = [c + d * (link / 2 - wire) * math.cos(t) + w * (link * 0.3 - wire) * math.sin(t)
               for t in (j / 16 * math.tau for j in range(17))]
        v, f = bs.tube_geom(pts, wire, 6, caps=False)
        bt.add(v, f, m)
    return bt.make()


def build_memory_corner():
    """The rented garage on the Yaksu-dong hill, recalled (pp.324-325)."""
    wood, st = mat("plywood", rough=0.7), mat("steel", rough=0.45, metal=0.7)
    chrome = hm("chrome", rough=0.2, metal=1.0)
    # "작은 중고 냉장고 위에는 전기 곤로를 올려놓았고"
    fx, fy = GX0 + 0.33, Y1 - 0.28
    fr = hm("fridge", rough=0.45, metal=0.15)
    parts = [box("MEM_fridge", (0.5, 0.5, 0.86), (fx, fy, 0.43), fr, bevel=0.03, segs=3),
             box("MEM_fridge_line", (0.48, 0.004, 0.006), (fx, fy - 0.252, 0.6), mat("ink"), bevel=0),
             box("MEM_fridge_handle", (0.02, 0.025, 0.16), (fx + 0.19, fy - 0.262, 0.7), chrome, bevel=0.006),
             box("MEM_hotplate", (0.32, 0.27, 0.07), (fx, fy - 0.03, 0.86 + 0.035), hm("hotplate", rough=0.5), bevel=0.012),
             cyl("MEM_hotplate_coil", 0.085, 0.006, (fx, fy - 0.02, 0.86 + 0.073), mat("black_metal", rough=0.5), n=24),
             cyl("MEM_hotplate_dial", 0.016, 0.014, (fx + 0.11, fy - 0.165, 0.89), mat("black_metal"), n=12,
                 rot=(math.pi / 2, 0, 0))]
    pot = hm("yangeun", rough=0.25, metal=0.85)
    zp = 0.86 + 0.076
    parts.append(lathe("MEM_pot", [(0, 0), (0.085, 0), (0.09, 0.006), (0.092, 0.075), (0.098, 0.08), (0.092, 0.08),
                                   (0.087, 0.075), (0.086, 0.008), (0, 0.008)], (fx, fy - 0.02, zp), pot, n=32))
    for s in (-1, 1):
        parts.append(tube(f"MEM_pot_ear_{s}", [(fx + s * 0.09, fy - 0.02, zp + 0.065), (fx + s * 0.125, fy - 0.02, zp + 0.07),
                                               (fx + s * 0.125, fy - 0.02, zp + 0.05)], 0.006, pot, n=6))
    group("fridge", parts)

    # "경첩을 이용하여 판자 하나를 벽에 붙이고 개목걸이 사슬을 이용하여 책상 역할을 하게 했는데"
    dx0, dx1, dz, dep = GX0 + 0.72, GX0 + 1.72, 0.74, 0.42
    xc = (dx0 + dx1) / 2
    parts = [box("MEM_desk", (dx1 - dx0, dep, 0.028), (xc, Y1 - dep / 2, dz), wood, bevel=0.003)]
    for k, x in enumerate((dx0 + 0.15, dx1 - 0.15)):
        parts.append(box(f"MEM_hinge_{k}", (0.09, 0.006, 0.05), (x, Y1 - 0.003, dz - 0.012), st, bevel=0.002))
    for k, x in enumerate((dx0 + 0.05, dx1 - 0.05)):
        top, low = (x, Y1 - 0.012, dz + 0.58), (x, Y1 - dep + 0.03, dz + 0.016)
        parts.append(chain(f"MEM_chain_{k}", top, low, st))
        parts.append(tube(f"MEM_eye_{k}", ring_pts(Vector(top) + Vector((0, 0.002, 0.012)), 0.012, axis="x", n=16), 0.0035,
                          st, n=6, caps=False))
    # on it: a dictionary, a page of translation, a pencil, and an old cassette radio
    po = mat("paper_old")
    parts.append(box("MEM_dictionary", (0.16, 0.23, 0.07), (dx0 + 0.16, Y1 - 0.15, dz + 0.014 + 0.035),
                     mat("book1", bs.BOOK_COLORS[1], rough=0.8, detail="fabric"), bevel=0.004, rot=(0, 0, math.radians(-6))))
    parts.append(box("MEM_page", (0.21, 0.29, 0.002), (xc - 0.06, Y1 - 0.25, dz + 0.015), po, bevel=0,
                     rot=(0, 0, math.radians(4))))
    lines = Batch("MEM_page_lines")
    for j in range(9):
        lines.box((0.15 - (j % 3) * 0.02, 0.0015, 0.0004), on((xc - 0.06, Y1 - 0.25, dz + 0.0162), math.radians(4),
                                                             (-0.005, 0.11 - j * 0.026, 0)), mat("ink"),
                  rot=(0, 0, math.radians(4)))
    parts.append(lines.make())
    parts.append(cyl("MEM_pencil", 0.004, 0.16, (xc + 0.08, Y1 - 0.27, dz + 0.018), mat("pencil", (0.82, 0.62, 0.2)), n=6,
                     rot=(0, math.pi / 2, math.radians(30))))
    rx, ry, rz = dx1 - 0.2, Y1 - 0.13, dz + 0.014
    rad = hm("radio", rough=0.4, metal=0.4)
    parts += [box("MEM_radio", (0.34, 0.11, 0.17), (rx, ry, rz + 0.085), rad, bevel=0.012, segs=2),
              box("MEM_radio_deck", (0.12, 0.004, 0.07), (rx, ry - 0.056, rz + 0.08), mat("black_metal"), bevel=0.002)]
    for s in (-1, 1):
        parts.append(lathe(f"MEM_radio_spk_{s}", [(0, 0), (0.045, 0), (0.048, 0.004), (0, 0.004)], (rx + s * 0.105, ry - 0.055, rz + 0.08),
                           hm("cone", rough=0.6), n=20, rot=(math.pi / 2, 0, 0)))
    parts.append(tube("MEM_radio_handle", [(rx - 0.12, ry, rz + 0.17), (rx - 0.1, ry, rz + 0.21), (rx + 0.1, ry, rz + 0.21),
                                           (rx + 0.12, ry, rz + 0.17)], 0.007, chrome, n=6))
    parts.append(cyl("MEM_radio_aerial", 0.003, 0.3, (rx + 0.15, ry + 0.03, rz + 0.3), chrome, n=6,
                     rot=(0, math.radians(-20), 0)))
    # a round stool
    sx, sy_ = xc - 0.1, Y1 - 0.72
    parts.append(lathe("MEM_stool_seat", [(0, 0.40), (0.16, 0.40), (0.165, 0.41), (0.16, 0.43), (0, 0.432)], (sx, sy_, 0),
                       wood, n=32))
    for k in range(3):
        a = k / 3 * math.tau + 0.5
        parts.append(tube(f"MEM_stool_leg_{k}", [(sx + 0.09 * math.cos(a), sy_ + 0.09 * math.sin(a), 0.40),
                                                (sx + 0.17 * math.cos(a), sy_ + 0.17 * math.sin(a), 0.0)], 0.014, wood, n=8))
    # "벽에 '3분 이상 잡담을 하려면 집으로 돌아가라'라고 크게 써 놓았다"
    if FONT:
        parts.append(text("MEM_words", "3분 이상 잡담을 하려면\n집으로 돌아가라", 0.2, (8.38, Y1 - 0.004, 1.68),
                          (math.pi / 2, 0, 0), mat("ink", rough=0.9)))
    # a bare bulb on a cord from a nail
    bx, bz = GX0 + 0.2, 2.12
    parts += [tube("MEM_cord", [(bx, Y1 - 0.01, bz + 0.3), (bx, Y1 - 0.03, bz + 0.16), (bx, Y1 - 0.05, bz + 0.06)], 0.003,
                   mat("ink"), n=5),
              cyl("MEM_socket", 0.016, 0.05, (bx, Y1 - 0.05, bz + 0.03), mat("black_metal"), n=12),
              lathe("MEM_bulb", [(0, -0.07), (0.022, -0.064), (0.03, -0.04), (0.018, -0.012), (0.012, 0), (0, 0)],
                    (bx, Y1 - 0.05, bz + 0.005), mat("bulb", emit=6.0), n=16)]
    group("garage_room", parts)


def build_workbench():
    """A workbench and a pegboard of tools (p.419), with a car-audio amplifier and a speaker on it (p.377)."""
    wd, st = hm("butcher", rough=0.6, detail="wood"), mat("steel", rough=0.45, metal=0.7)
    dark, red = mat("black_metal", rough=0.4, metal=0.6), hm("tool_red", rough=0.4, metal=0.2)
    x0, x1, yb, yf, top = 12.05, 13.33, Y1 - 0.01, Y1 - 0.62, 0.90
    cx, cy, w, d = (x0 + x1) / 2, (yb + yf) / 2, x1 - x0, yb - yf
    parts = [box("WB_top", (w, d, 0.06), (cx, cy, top - 0.03), wd, bevel=0.006)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(box(f"WB_leg_{sx}{sy}", (0.07, 0.07, top - 0.06), (cx + sx * (w / 2 - 0.06), cy + sy * (d / 2 - 0.06),
                                                                            (top - 0.06) / 2), wd, bevel=0.005))
    parts.append(box("WB_shelf", (w - 0.08, d - 0.08, 0.025), (cx, cy, 0.17), mat("plywood", rough=0.7), bevel=0.003))
    parts.append(box("WB_toolbox", (0.46, 0.22, 0.18), (cx - 0.3, cy, 0.18 + 0.09), red, bevel=0.01))
    parts.append(tube("WB_toolbox_handle", [(cx - 0.42, cy, 0.36), (cx - 0.4, cy, 0.4), (cx - 0.2, cy, 0.4), (cx - 0.18, cy, 0.36)],
                      0.008, dark, n=6))
    # a vise on the front corner
    vx = x0 + 0.16
    parts += [box("WB_vise", (0.16, 0.16, 0.09), (vx, yf + 0.04, top + 0.045), hm("bike_blue", rough=0.4), bevel=0.008),
              box("WB_vise_jaw", (0.16, 0.03, 0.06), (vx, yf - 0.03, top + 0.06), hm("bike_blue", rough=0.4), bevel=0.006),
              cyl("WB_vise_screw", 0.008, 0.2, (vx, yf - 0.1, top + 0.04), st, n=8, rot=(math.pi / 2, 0, 0)),
              cyl("WB_vise_bar", 0.006, 0.18, (vx, yf - 0.19, top + 0.04), st, n=8, rot=(0, math.pi / 2, 0))]
    # the car-audio amplifier he is working on, its fins up, and a speaker beside it
    ax, ay = cx + 0.05, cy + 0.06
    parts.append(box("WB_amp", (0.32, 0.22, 0.05), (ax, ay, top + 0.025), dark, bevel=0.006))
    fins = Batch("WB_amp_fins")
    for k in range(9):
        fins.box((0.3, 0.006, 0.018), (ax, ay - 0.1 + k * 0.025, top + 0.059), dark)
    parts.append(fins.make())
    parts.append(lathe("WB_speaker", [(0, 0), (0.04, 0), (0.045, 0.03), (0.08, 0.06), (0.09, 0.066), (0.09, 0.072),
                                      (0.084, 0.072), (0.074, 0.064), (0.032, 0.036), (0, 0.04)], (cx + 0.43, cy - 0.06, top),
                       hm("cone", rough=0.6), n=32))
    for k, (col, off) in enumerate((("pin", 0.0), ("ink", 0.02))):
        parts.append(tube(f"WB_wire_{k}", [(ax + 0.16, ay - 0.05 + off, top + 0.02), (ax + 0.24, ay - 0.1 + off, top + 0.006),
                                           (cx + 0.36, cy - 0.04 + off, top + 0.006), (cx + 0.4, cy - 0.05 + off, top + 0.03)],
                          0.004, mat(col), n=5))
    # pegboard and tools
    pz0, pz1 = 1.08, 2.02
    parts.append(box("WB_pegboard", (w, 0.012, pz1 - pz0), (cx, Y1 - 0.006, (pz0 + pz1) / 2), hm("pegboard", rough=0.8),
                     bevel=0.002))
    holes = Batch("WB_holes")
    hd = mat("hole", (0.08, 0.06, 0.04))
    for i in range(1, int(w / 0.05)):
        for j in range(1, int((pz1 - pz0) / 0.05)):
            holes.box((0.006, 0.001, 0.006), (x0 + i * 0.05, Y1 - 0.0125, pz0 + j * 0.05), hd)
    parts.append(holes.make())
    yt = Y1 - 0.025
    handle = mat("desk", rough=0.55)
    parts += [box("WB_hammer_handle", (0.028, 0.02, 0.3), (x0 + 0.14, yt, 1.48), handle, bevel=0.006),
              box("WB_hammer_head", (0.12, 0.03, 0.035), (x0 + 0.14, yt, 1.64), st, bevel=0.006)]
    for k, length in enumerate((0.17, 0.21, 0.25)):
        x = x0 + 0.3 + k * 0.06
        parts.append(box(f"WB_wrench_{k}", (0.02, 0.006, length), (x, yt, 1.62 - length / 2), st, bevel=0.002))
        for j, z in enumerate((1.62, 1.62 - length)):
            parts.append(cyl(f"WB_wrench_end_{k}{j}", 0.018, 0.007, (x, yt, z), st, n=12, rot=(math.pi / 2, 0, 0)))
    for k, col in enumerate(("tool_red", "tool_yellow", "tool_red", "bike_blue")):
        x = x0 + 0.56 + k * 0.05
        parts += [cyl(f"WB_driver_handle_{k}", 0.012, 0.09, (x, yt, 1.7), hm(col, rough=0.4), n=10),
                  cyl(f"WB_driver_shaft_{k}", 0.003, 0.13 - k * 0.015, (x, yt, 1.65 - (0.13 - k * 0.015) / 2), st, n=6)]
    saw = [(0.0, 0.0), (0.42, 0.0), (0.42, 0.04), (0.0, 0.11)]
    parts.append(prism_xz("WB_saw", saw, -0.001, 0.001, st, loc=(x0 + 0.2, yt, 1.82)))
    parts.append(box("WB_saw_handle", (0.11, 0.025, 0.1), (x0 + 0.16, yt, 1.87), handle, bevel=0.01))
    for k, s in enumerate((-1, 1)):
        parts.append(box(f"WB_pliers_{k}", (0.018, 0.008, 0.19), (x0 + 0.9, yt, 1.45), hm("tool_red", rough=0.4), bevel=0.003,
                         rot=(0, math.radians(s * 9), 0)))
    parts.append(cyl("WB_tape", 0.035, 0.026, (x0 + 1.08, yt - 0.004, 1.6), hm("tool_yellow", rough=0.4), n=20,
                     rot=(math.pi / 2, 0, 0)))
    group("workbench", parts)

    # two spare tyres stacked in front of the bench
    tire = hm("tire", rough=0.85)
    prof = [(0.2, 0.0), (0.27, -0.01), (0.31, 0.01), (0.325, 0.05), (0.325, 0.15), (0.31, 0.19), (0.27, 0.21), (0.2, 0.2)]
    group("spare_tyres", [lathe(f"TYRE_{k}", prof, (12.95, 1.86, 0.01 + k * 0.205), tire, n=32) for k in range(2)])


def build_garage():
    window("GWIN", *GAR_WIN, steel=True)
    build_car()
    build_bike_shelf()
    build_memory_corner()
    build_workbench()
    # the visitor's own bicycle, ridden in and parked inside the shutter, clear of the car
    g = group("visitor_bicycle", bicycle("VBIKE", hm("bike_mint", rough=0.35, metal=0.2), "city"))
    g.location, g.rotation_euler = (12.38, -2.2, 0), (math.radians(-8), 0, 0)
    # a fluorescent tube over the shelves
    z = 2.62
    group("tube_light", [box("TUBE_batten", (1.3, 0.07, 0.05), (10.6, Y1 - 0.045, z), mat("trim", rough=0.55), bevel=0.008),
                         cyl("TUBE_glow", 0.014, 1.2, (10.6, Y1 - 0.06, z - 0.035), hm("tube_light", emit=5.0), n=12,
                             rot=(0, math.pi / 2, 0))])


# ---------------------------------------------------------------- lights, cameras, figures

def house_lights(mood):
    m = bs.MOODS[mood]
    for name, (x0, x1, z0, z1) in (("hall", HALL_WIN), ("garage", GAR_WIN)):
        sky = _make(f"ENV_sky_{name}", [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)], [(0, 1, 2, 3)],
                    bpy.data.materials["sky_" + mood], loc=((x0 + x1) / 2, Y1 + 0.6, (z0 + z1) / 2))
        sky.scale = ((x1 - x0) / 2 + 0.4, 1, (z1 - z0) / 2 + 0.15)
        sky.visible_shadow = False
    for k, x in enumerate((9.5, 14.5)):
        f = bs._light(f"LGT_fill_{k + 2}", "POINT", (x, -4.5, 5.0))
        f.data.energy, f.data.color, f.data.shadow_soft_size = m["fill_e"], m["fill"], 3.0
    on_ = m["lamp"] / 60
    if not on_:
        for name in ("sconce", "tube_light"):
            bpy.data.materials[name].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
        return
    warm = (1.0, 0.72, 0.45)
    for name, kind, loc, energy, color in (
            ("LGT_sconce", "POINT", (HALL_WIN[0] - 0.55, Y1 - 0.2, 1.92), 45, warm),
            ("LGT_table", "POINT", (5.35, -0.08, 0.96), 30, warm),
            ("LGT_bulb", "POINT", (GX0 + 0.2, Y1 - 0.12, 2.08), 35, warm),
            ("LGT_tube", "SPOT", (10.6, Y1 - 0.2, 2.55), 380, (1.0, 0.95, 0.86))):
        lt = bs._light(name, kind, loc)
        lt.data.energy, lt.data.color = energy * on_, color
        lt.data.shadow_soft_size = 0.1 if kind == "POINT" else 0.4
        if kind == "SPOT":
            lt.data.spot_size, lt.data.spot_blend = math.radians(140), 0.8
            lt.rotation_euler = (math.radians(-35), 0, 0)


VIEWS = {   # yaw (turned to look from the right), pitch, and the box to fit
    "overview": (24, 33, (X0 - T - 0.1, YF - 0.9, -0.26), (XR + 0.1, Y1 + T, WALL_H + 0.03), (2160, 1200)),
    "hall": (45.6, 28.2, (2.8, YF - 0.5, 0.0), (GX0 + 0.1, Y1 + T, WALL_H + 0.03), (1600, 1250)),
    "garage": (45.6, 28.2, (HX1 - 0.1, YF - 0.85, 0.0), (XR + 0.1, Y1 + T, WALL_H + 0.03), (1600, 1250)),
    "study": (45.6, 28.2, (X0 - T, YF - 0.3, 0.0), (3.4, Y1 + T, WALL_H + 0.03), (1600, 1250)),
}


def frame_camera(view, margin=0.03):
    """An orthographic camera at the view's angle, sized and centred to fit its box."""
    yaw, pitch, lo, hi, res = VIEWS[view]
    yaw, pitch = math.radians(yaw), math.radians(pitch)
    fwd = Vector((-math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), -math.sin(pitch)))
    right = Vector((math.cos(yaw), math.sin(yaw), 0))
    up = right.cross(fwd)
    corners = [Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    us, vs = [c.dot(right) for c in corners], [c.dot(up) for c in corners]
    scale = max(max(us) - min(us), (max(vs) - min(vs)) * res[0] / res[1]) * (1 + margin)
    centre = right * (max(us) + min(us)) / 2 + up * (max(vs) + min(vs)) / 2
    cam = ch.camera("CAM_" + view, tuple(centre - fwd * 40), tuple(centre), ortho=scale)
    cam.data.clip_end = 200
    return res


FIGURES = {   # where the two stand in each view: (x, y), yaw
    "visitor": ((4.85, -1.25), 18),
    "sayno": ((12.15, 1.02), 28),
}


def add_figures(view):
    bs.COLL = bs._collection("CHARACTERS")
    if view in ("overview", "garage"):
        s = ch.make_sayno(True)
        ch.rename(s, 0)
        s.place(*FIGURES["sayno"])
    if view in ("overview", "hall"):
        v = ch.make_visitor(True)
        v.place(*FIGURES["visitor"])
    bs.COLL = None


def build_house(detail=True, mood="dusk"):
    """The study as built (without its lights), then the rest of the house, lights and all."""
    bs.build_study(detail=detail, mood=mood, lights=False)
    bpy.data.objects.remove(bpy.data.objects["ENV_plinth"], do_unlink=True)
    bs.COLL = bs._collection("HOUSE")
    build_shell()
    build_music_corner()
    build_waiting_room()
    build_garage()
    bs.COLL = bs._collection("RIG")
    bs.setup_lights_and_camera(mood)
    house_lights(mood)
    bs.COLL = None


def main():
    global FONT
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--view", default="overview", choices=list(VIEWS))
    ap.add_argument("--mood", default="dusk", choices=list(bs.MOODS))
    ap.add_argument("--out")
    ap.add_argument("--save")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--res", help="override the view's resolution, e.g. 800x450")
    ap.add_argument("--font", help="Korean brush-script font for the words on the garage wall")
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args(argv)
    FONT = a.font
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_house(detail=True, mood=a.mood)
    if not a.no_figures:
        add_figures(a.view)
    res = frame_camera(a.view)
    if a.res:
        res = tuple(int(v) for v in a.res.split("x"))
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=a.save)
    if a.out:
        bs.render(a.out, a.samples, res)


if __name__ == "__main__":
    main()
