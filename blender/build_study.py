"""Build Sayno's study as a low-poly diorama and render mood previews.

Run headless with the `bpy` package:
    python3 blender/build_study.py --mood dusk --out renders/dusk.png
    python3 blender/build_study.py --save blender/study.blend
"""
import argparse
import math
import random
import sys

import bpy
from mathutils import Vector

random.seed(7)

# ---------------------------------------------------------------- materials

PALETTE = {
    "floor": (0.42, 0.27, 0.16),
    "wall": (0.80, 0.72, 0.60),
    "wall_edge": (0.55, 0.45, 0.35),
    "desk": (0.30, 0.18, 0.10),
    "plywood": (0.72, 0.56, 0.36),
    "steel": (0.35, 0.37, 0.38),
    "paper": (0.90, 0.87, 0.78),
    "paper_old": (0.82, 0.76, 0.60),
    "ink": (0.08, 0.08, 0.10),
    "brass": (0.72, 0.52, 0.22),
    "lampshade": (0.20, 0.33, 0.24),
    "rug": (0.48, 0.18, 0.14),
    "rug_edge": (0.78, 0.66, 0.44),
    "chair": (0.36, 0.22, 0.12),
    "cushion": (0.55, 0.40, 0.26),
    "pot": (0.62, 0.36, 0.24),
    "leaf": (0.24, 0.38, 0.20),
    "frame": (0.22, 0.14, 0.08),
    "pin": (0.70, 0.12, 0.10),
    "cabinet": (0.40, 0.26, 0.15),
}
BOOK_COLORS = [
    (0.45, 0.14, 0.12), (0.16, 0.25, 0.38), (0.24, 0.34, 0.22), (0.62, 0.48, 0.26),
    (0.30, 0.20, 0.14), (0.70, 0.62, 0.48), (0.20, 0.20, 0.22), (0.52, 0.30, 0.18),
]

_mats = {}


def mat(name, color=None, rough=0.75, metal=0.0, emit=0.0):
    key = (name, color, emit)
    if key in _mats:
        return _mats[key]
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
    _mats[key] = m
    return m


# ---------------------------------------------------------------- primitives

def _finish(obj, material, bevel, name):
    obj.name = name
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
    for p in obj.data.polygons:
        p.use_smooth = False
    return obj


def box(name, size, loc, material, bevel=0.012, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.scale = size
    return _finish(obj, material, bevel, name)


def cyl(name, radius, depth, loc, material, verts=16, rot=(0, 0, 0), bevel=0.006):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth,
                                        location=loc, rotation=rot)
    return _finish(bpy.context.object, material, bevel, name)


def cone(name, r1, r2, depth, loc, material, verts=16, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=depth,
                                    location=loc, rotation=rot)
    return _finish(bpy.context.object, material, 0, name)


def blob(name, radius, loc, material):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=radius, location=loc)
    return _finish(bpy.context.object, material, 0, name)


def group(name, objs):
    """Parent objects under an empty so the web app can pick them by name."""
    empty = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(empty)
    for o in objs:
        o.parent = empty
    return empty


# ---------------------------------------------------------------- the room

ROOM = 6.0      # floor is ROOM x ROOM, centred on origin
WALL_H = 3.2
T = 0.2         # wall / slab thickness


def build_room():
    h = ROOM / 2
    box("floor", (ROOM + T, ROOM + T, T), (T / 2 * -1 + 0.1, 0.1 - T / 2 + 0.0, -T / 2),
        mat("floor"), bevel=0.02)
    # plank lines on the floor
    for i in range(1, 12):
        x = -h + i * ROOM / 12
        box(f"plank_{i}", (0.012, ROOM, 0.004), (x, 0, 0.001),
            mat("plank_line", (0.30, 0.19, 0.11)), bevel=0)

    back = box("wall_back", (ROOM + T, T, WALL_H), (0 - T / 2, h + T / 2, WALL_H / 2),
               mat("wall"), bevel=0.02)
    box("wall_left", (T, ROOM, WALL_H), (-h - T / 2, 0, WALL_H / 2), mat("wall"), bevel=0.02)
    box("skirting_back", (ROOM, 0.04, 0.14), (0, h - 0.02, 0.07), mat("wall_edge"))
    box("skirting_left", (0.04, ROOM, 0.14), (-h + 0.02, 0, 0.07), mat("wall_edge"))

    # window hole in the back wall
    win_c = (1.55, h + T / 2, 1.85)
    win_size = (1.3, 1.2)
    cutter = box("win_cut", (win_size[0], 1.0, win_size[1]), win_c, mat("wall"), bevel=0)
    boolean = back.modifiers.new("window", "BOOLEAN")
    boolean.operation = "DIFFERENCE"
    boolean.object = cutter
    cutter.hide_render = True
    cutter.hide_viewport = True
    fm = mat("frame")
    wx, wz = win_size
    box("win_frame_top", (wx + 0.1, T + 0.06, 0.06), (win_c[0], win_c[1], win_c[2] + wz / 2), fm)
    box("win_frame_bot", (wx + 0.2, T + 0.16, 0.06), (win_c[0], win_c[1] - 0.05, win_c[2] - wz / 2), fm)
    box("win_frame_l", (0.06, T + 0.06, wz), (win_c[0] - wx / 2, win_c[1], win_c[2]), fm)
    box("win_frame_r", (0.06, T + 0.06, wz), (win_c[0] + wx / 2, win_c[1], win_c[2]), fm)
    box("win_mullion_v", (0.04, 0.05, wz), (win_c[0], win_c[1], win_c[2]), fm)
    box("win_mullion_h", (wx, 0.05, 0.04), (win_c[0], win_c[1], win_c[2] + 0.1), fm)
    return win_c, win_size


def build_desk():
    """The owner's desk: buried in papers (a clean desk belongs to a mafia boss or a crook, p.179)."""
    parts = []
    dm = mat("desk")
    top_z = 0.78
    cx, cy = 0.1, 2.35
    parts.append(box("desk_top", (2.0, 0.95, 0.06), (cx, cy, top_z), dm, bevel=0.015))
    for sx in (-0.92, 0.92):
        for sy in (-0.4, 0.4):
            parts.append(box("desk_leg", (0.07, 0.07, top_z), (cx + sx, cy + sy, top_z / 2), dm))
    parts.append(box("desk_apron", (1.9, 0.04, 0.12), (cx, cy - 0.43, top_z - 0.09), dm))

    # paper stacks
    pm, po = mat("paper"), mat("paper_old")
    for i, (px, py, n) in enumerate([(-0.65, 2.55, 14), (-0.3, 2.6, 9), (0.55, 2.6, 18),
                                     (0.82, 2.25, 6), (-0.72, 2.15, 4)]):
        z = top_z + 0.03
        for k in range(n):
            th = random.uniform(0.008, 0.02)
            parts.append(box(f"paper_{i}_{k}", (0.30, 0.40, th),
                             (px + random.uniform(-0.02, 0.02), py + random.uniform(-0.02, 0.02), z + th / 2),
                             random.choice([pm, pm, po]), bevel=0,
                             rot=(0, 0, math.radians(random.uniform(-6, 6)))))
            z += th
    # folders with coloured tabs
    for k, c in enumerate([(0.55, 0.20, 0.15), (0.20, 0.30, 0.45), (0.65, 0.55, 0.25)]):
        parts.append(box(f"folder_{k}", (0.32, 0.42, 0.012), (0.55, 2.6, top_z + 0.33 + k * 0.015),
                         mat(f"folder{k}", c), bevel=0, rot=(0, 0, math.radians(8 - k * 7))))
    desk = group("desk_papers", parts)

    # desk lamp
    bm, sm = mat("brass", rough=0.35, metal=0.8), mat("lampshade", rough=0.5)
    lamp = [
        cyl("lamp_base", 0.11, 0.03, (-0.15, 2.62, top_z + 0.045), bm),
        cyl("lamp_arm", 0.012, 0.5, (-0.15, 2.58, top_z + 0.3), bm, rot=(math.radians(-12), 0, 0)),
        cone("lamp_shade", 0.16, 0.05, 0.16, (-0.15, 2.45, top_z + 0.55), sm,
             rot=(math.radians(-25), 0, 0)),
        blob("lamp_bulb", 0.045, (-0.15, 2.43, top_z + 0.49), mat("bulb", (1.0, 0.75, 0.42), emit=6.0)),
    ]
    group("lamp", lamp)

    # the letter paper and pen at the front edge: where the visitor writes
    letter = [
        box("letter_sheet", (0.26, 0.36, 0.004), (0.15, 2.08, top_z + 0.033), mat("paper"),
            bevel=0, rot=(0, 0, math.radians(-7))),
        cyl("pen", 0.009, 0.16, (0.33, 2.05, top_z + 0.04), mat("ink", rough=0.3),
            rot=(0, math.radians(90), math.radians(30))),
    ]
    for j in range(5):  # faint ruled lines
        letter.append(box(f"letter_line_{j}", (0.2, 0.002, 0.001),
                          (0.15 - 0.004 * j, 2.18 - j * 0.05, top_z + 0.036),
                          mat("rule", (0.62, 0.66, 0.74)), bevel=0, rot=(0, 0, math.radians(-7))))
    group("letter", letter)

    # daily tear-off calendar (일력)
    cal = [
        box("cal_base", (0.16, 0.08, 0.03), (-0.55, 2.0, top_z + 0.045), mat("frame")),
        box("cal_pages", (0.15, 0.03, 0.2), (-0.55, 2.02, top_z + 0.16), mat("paper"),
            rot=(math.radians(-12), 0, 0)),
        box("cal_red", (0.15, 0.032, 0.035), (-0.55, 2.04, top_z + 0.245), mat("pin"),
            bevel=0, rot=(math.radians(-12), 0, 0)),
    ]
    group("calendar", cal)

    # chair
    cm = mat("chair")
    chair = [
        box("chair_seat", (0.5, 0.48, 0.06), (0.2, 1.45, 0.47), cm),
        box("chair_cushion", (0.44, 0.42, 0.05), (0.2, 1.45, 0.52), mat("cushion", rough=0.95), bevel=0.02),
        box("chair_back", (0.5, 0.05, 0.5), (0.2, 1.22, 0.78), cm, rot=(math.radians(-8), 0, 0)),
    ]
    for sx in (-0.21, 0.21):
        for sy in (-0.2, 0.2):
            chair.append(box("chair_leg", (0.045, 0.045, 0.45), (0.2 + sx, 1.45 + sy, 0.225), cm))
    group("chair", chair)
    return desk


def build_angle_bench():
    """Steel angle frame with a plywood top: the desk built to save money (p.218)."""
    parts = []
    st, pw = mat("steel", rough=0.45, metal=0.7), mat("plywood")
    cx, cy, w, d, hgt = 2.3, 2.45, 1.0, 0.7, 0.74
    for sx in (-w / 2 + 0.03, w / 2 - 0.03):
        for sy in (-d / 2 + 0.03, d / 2 - 0.03):
            parts.append(box("angle_leg_a", (0.05, 0.008, hgt), (cx + sx, cy + sy, hgt / 2), st, bevel=0))
            parts.append(box("angle_leg_b", (0.008, 0.05, hgt), (cx + sx, cy + sy, hgt / 2), st, bevel=0))
    for z in (0.15, hgt - 0.02):
        parts.append(box("angle_rail_f", (w, 0.008, 0.05), (cx, cy - d / 2 + 0.03, z), st, bevel=0))
        parts.append(box("angle_rail_b", (w, 0.008, 0.05), (cx, cy + d / 2 - 0.03, z), st, bevel=0))
    parts.append(box("plywood_top", (w + 0.04, d + 0.04, 0.025), (cx, cy, hgt + 0.0125), pw, bevel=0.004))
    parts.append(box("plywood_shelf", (w - 0.06, d - 0.06, 0.02), (cx, cy, 0.17), pw, bevel=0.004))
    for k in range(6):  # bolt heads
        parts.append(blob("bolt", 0.012, (cx - w / 2 + 0.03 + (k % 2) * (w - 0.06), cy - d / 2 + 0.025,
                                          0.15 if k < 2 else hgt - 0.02), st))
    group("angle_bench", parts)

    # weekly economics magazines on the bench (p.304)
    mags = []
    z = 0.765
    for k in range(9):
        c = random.choice([(0.70, 0.20, 0.15), (0.85, 0.80, 0.70), (0.20, 0.30, 0.50), (0.15, 0.15, 0.17)])
        mags.append(box(f"mag_{k}", (0.24, 0.32, 0.012), (cx - 0.2 + random.uniform(-0.02, 0.02),
                        cy + random.uniform(-0.02, 0.02), z + 0.006), mat(f"mag{k}", c), bevel=0,
                        rot=(0, 0, math.radians(random.uniform(-10, 10)))))
        z += 0.012
    for k in range(5):
        c = random.choice([(0.85, 0.80, 0.70), (0.30, 0.45, 0.55), (0.75, 0.55, 0.20)])
        mags.append(box(f"mag_s_{k}", (0.24, 0.32, 0.01), (cx + 0.2, cy, 0.19 + k * 0.011),
                        mat(f"mags{k}", c), bevel=0, rot=(0, 0, math.radians(random.uniform(-8, 8)))))
    group("magazines", mags)


def build_bookshelf():
    """Bookshelf on the left wall: the recommended reading list (p.734)."""
    parts = []
    wm = mat("desk")
    x0 = -ROOM / 2 + 0.2
    y0, y1 = -1.4, 1.6
    hgt, depth = 2.5, 0.36
    cy = (y0 + y1) / 2
    parts.append(box("shelf_side_a", (depth, 0.05, hgt), (x0, y0, hgt / 2), wm))
    parts.append(box("shelf_side_b", (depth, 0.05, hgt), (x0, y1, hgt / 2), wm))
    parts.append(box("shelf_back", (0.02, y1 - y0, hgt), (x0 - depth / 2 + 0.01, cy, hgt / 2), wm))
    levels = [0.05, 0.55, 1.05, 1.55, 2.05, hgt - 0.02]
    for z in levels:
        parts.append(box("shelf_board", (depth, y1 - y0, 0.04), (x0, cy, z), wm))
    books = []
    for li, z in enumerate(levels[:-1]):
        y = y0 + 0.05
        while y < y1 - 0.1:
            w = random.uniform(0.035, 0.075)
            h = random.uniform(0.28, 0.42)
            if random.random() < 0.06:  # leave a gap now and then
                y += random.uniform(0.08, 0.2)
                continue
            lean = math.radians(random.uniform(-10, 0)) if random.random() < 0.08 else 0
            books.append(box("book", (random.uniform(0.2, 0.28), w, h),
                             (x0 + 0.02, y + w / 2, z + 0.02 + h / 2),
                             mat(f"book{random.randrange(len(BOOK_COLORS))}",
                                 random.choice(BOOK_COLORS), rough=0.8),
                             bevel=0.004, rot=(lean, 0, 0)))
            y += w + 0.004
    group("bookshelf", parts + books)


def build_cabinet():
    """Drawer cabinet: where replies are kept."""
    parts = []
    cm, bm = mat("cabinet"), mat("brass", rough=0.35, metal=0.8)
    cx, cy = -1.75, 2.5
    w, d, hgt = 0.7, 0.6, 0.9
    parts.append(box("cab_body", (w, d, hgt), (cx, cy, hgt / 2), cm, bevel=0.015))
    for k in range(3):
        z = 0.17 + k * 0.28
        parts.append(box(f"drawer_{k}", (w - 0.08, 0.03, 0.24), (cx, cy - d / 2 - 0.005, z), cm, bevel=0.01))
        parts.append(cyl(f"knob_{k}", 0.022, 0.03, (cx, cy - d / 2 - 0.035, z), bm,
                         rot=(math.radians(90), 0, 0)))
    # a few envelopes on top
    for k in range(3):
        parts.append(box(f"envelope_{k}", (0.24, 0.14, 0.006),
                         (cx + random.uniform(-0.05, 0.05), cy + random.uniform(-0.05, 0.05),
                          hgt + 0.004 + k * 0.006), mat("paper_old"), bevel=0,
                         rot=(0, 0, math.radians(random.uniform(-15, 15)))))
    group("drawer", parts)


def build_wall_things():
    parts = []
    # checklist pinned above the desk (p.143)
    parts.append(box("checklist", (0.34, 0.01, 0.46), (0.1, ROOM / 2 - 0.01, 1.75), mat("paper"), bevel=0))
    for j in range(6):
        parts.append(box(f"check_box_{j}", (0.03, 0.004, 0.03), (-0.02, ROOM / 2 - 0.018, 1.9 - j * 0.06),
                         mat("ink"), bevel=0))
        parts.append(box(f"check_line_{j}", (0.18, 0.004, 0.008), (0.14, ROOM / 2 - 0.018, 1.9 - j * 0.06),
                         mat("ink"), bevel=0))
    parts.append(blob("checklist_pin", 0.018, (0.1, ROOM / 2 - 0.03, 1.96), mat("pin", rough=0.3)))
    group("checklist", parts)

    # caricature frame, no face: just a few pen strokes (preface p.6)
    fr = [box("frame", (0.5, 0.04, 0.62), (-1.0, ROOM / 2 - 0.02, 1.9), mat("frame")),
          box("frame_paper", (0.42, 0.01, 0.54), (-1.0, ROOM / 2 - 0.045, 1.9), mat("paper_old"), bevel=0)]
    for j, (dx, dz, w, r) in enumerate([(0, 0.08, 0.16, 0), (-0.02, -0.02, 0.1, 20), (0.03, -0.1, 0.2, -5)]):
        fr.append(box(f"stroke_{j}", (w, 0.004, 0.008), (-1.0 + dx, ROOM / 2 - 0.052, 1.9 + dz),
                      mat("ink"), bevel=0, rot=(0, math.radians(r), 0)))
    group("caricature", fr)


def build_reading_corner():
    """Armchair, side table and the open book where replies appear."""
    fab, wood = mat("armchair", (0.30, 0.36, 0.30), rough=0.95), mat("desk")
    ax, ay = 1.2, -0.9
    chair = [
        box("arm_base", (0.9, 0.85, 0.3), (ax, ay, 0.25), fab, bevel=0.05),
        box("arm_cushion", (0.66, 0.7, 0.14), (ax, ay - 0.02, 0.46), fab, bevel=0.05),
        box("arm_back", (0.9, 0.2, 0.62), (ax, ay + 0.37, 0.66), fab, bevel=0.06,
            rot=(math.radians(-10), 0, 0)),
        box("arm_left", (0.14, 0.8, 0.5), (ax - 0.4, ay, 0.45), fab, bevel=0.05),
        box("arm_right", (0.14, 0.8, 0.5), (ax + 0.4, ay, 0.45), fab, bevel=0.05),
    ]
    for sx in (-0.38, 0.38):
        for sy in (-0.35, 0.35):
            chair.append(cyl("arm_foot", 0.03, 0.1, (ax + sx, ay + sy, 0.05), wood))
    chair.append(box("throw", (0.5, 0.9, 0.02), (ax + 0.1, ay + 0.1, 0.58), mat("rug", rough=1.0),
                     bevel=0.01, rot=(math.radians(-8), 0, math.radians(12))))
    group("armchair", chair)

    tx, ty = 0.25, -1.1
    table = [cyl("side_top", 0.32, 0.04, (tx, ty, 0.55), wood, verts=24),
             cyl("side_leg", 0.04, 0.53, (tx, ty, 0.27), wood),
             cyl("side_foot", 0.2, 0.03, (tx, ty, 0.015), wood, verts=24)]
    group("side_table", table)
    book = [
        box("book_left", (0.2, 0.28, 0.02), (tx - 0.1, ty, 0.585), mat("paper"), bevel=0.003,
            rot=(0, math.radians(8), 0)),
        box("book_right", (0.2, 0.28, 0.02), (tx + 0.1, ty, 0.585), mat("paper"), bevel=0.003,
            rot=(0, math.radians(-8), 0)),
        box("book_cover", (0.42, 0.3, 0.012), (tx, ty, 0.572), mat("book0", BOOK_COLORS[0]), bevel=0.003),
    ]
    for j in range(6):
        for side in (-1, 1):
            book.append(box("book_text", (0.14, 0.004, 0.002),
                            (tx + side * 0.1, ty + 0.09 - j * 0.035, 0.598 - 0.004 * abs(side) + 0.0),
                            mat("ink"), bevel=0, rot=(0, math.radians(-8 * side), 0)))
    group("open_book", book)
    cup = [cyl("cup", 0.045, 0.08, (tx + 0.18, ty - 0.18, 0.61), mat("paper", rough=0.3), verts=16),
           cyl("tea", 0.04, 0.005, (tx + 0.18, ty - 0.18, 0.648), mat("tea", (0.35, 0.18, 0.06), rough=0.1))]
    group("teacup", cup)

    # floor lamp behind the armchair
    bm = mat("brass", rough=0.35, metal=0.8)
    flamp = [cyl("fl_base", 0.16, 0.03, (2.0, -0.4, 0.015), bm, verts=20),
             cyl("fl_pole", 0.015, 1.5, (2.0, -0.4, 0.78), bm),
             cone("fl_shade", 0.24, 0.14, 0.28, (2.0, -0.4, 1.6), mat("shade2", (0.88, 0.80, 0.62), rough=0.9),
                  verts=20),
             blob("fl_bulb", 0.05, (2.0, -0.4, 1.52), mat("bulb", (1.0, 0.75, 0.42), emit=6.0))]
    group("floor_lamp", flamp)


def build_decor():
    rug = [box("rug", (2.6, 1.8, 0.02), (0.7, -0.6, 0.01), mat("rug", rough=1.0), bevel=0.01),
           box("rug_inner", (2.3, 1.5, 0.022), (0.7, -0.6, 0.012), mat("rug_edge", rough=1.0), bevel=0),
           box("rug_core", (2.1, 1.3, 0.024), (0.7, -0.6, 0.013), mat("rug", rough=1.0), bevel=0)]
    group("rug", rug)
    plant = [cyl("pot", 0.17, 0.3, (2.55, 1.6, 0.15), mat("pot"), verts=12)]
    for k in range(7):
        a = k / 7 * math.tau
        plant.append(blob("leaf", random.uniform(0.12, 0.18),
                          (2.55 + 0.12 * math.cos(a), 1.6 + 0.12 * math.sin(a), 0.42 + random.uniform(0, 0.3)),
                          mat("leaf", rough=0.8)))
    group("plant", plant)
    # a floor lamp's worth of extra books stacked on the floor by the shelf
    z = 0
    for k in range(5):
        th = random.uniform(0.04, 0.07)
        box("floor_book", (0.3, 0.22, th), (-2.3, -1.9, z + th / 2),
            mat(f"book{k}", random.choice(BOOK_COLORS)), bevel=0.004,
            rot=(0, 0, math.radians(random.uniform(-15, 15))))
        z += th


# ---------------------------------------------------------------- moods

MOODS = {
    # sky colour behind the window, world colour, sun (energy, colour, elevation, azimuth), lamp on
    "dusk": dict(sky=(1.0, 0.55, 0.30), sky_emit=3.0, world=(0.93, 0.80, 0.66), world_str=0.45,
                 sun=(7.0, (1.0, 0.58, 0.32), 22, 200), lamp=60, fill=(1.0, 0.85, 0.7), fill_e=150),
    "night": dict(sky=(0.10, 0.16, 0.32), sky_emit=1.2, world=(0.16, 0.18, 0.26), world_str=0.5,
                  sun=(0.0, (0.5, 0.6, 1.0), 40, 200), lamp=200, fill=(0.45, 0.55, 0.85), fill_e=110),
    "morning": dict(sky=(0.75, 0.88, 1.0), sky_emit=2.5, world=(0.90, 0.92, 0.90), world_str=0.8,
                    sun=(5.0, (1.0, 0.95, 0.85), 35, 210), lamp=0, fill=(0.95, 0.97, 1.0), fill_e=300),
}


def setup_lights_and_camera(mood, win_c):
    m = MOODS[mood]
    scene = bpy.context.scene
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*m["world"], 1)
    bg.inputs["Strength"].default_value = m["world_str"]
    scene.world = world

    # sky card behind the window
    bpy.ops.mesh.primitive_plane_add(size=1, location=(win_c[0], win_c[1] + 0.6, win_c[2]),
                                     rotation=(math.radians(90), 0, 0))
    sky = bpy.context.object
    sky.name = "sky"
    sky.scale = (2.0, 2.0, 1)
    sky.data.materials.append(mat("sky_" + mood, m["sky"], emit=m["sky_emit"]))
    sky.visible_shadow = False  # let the sun through the window

    energy, color, elev, az = m["sun"]
    if energy:
        bpy.ops.object.light_add(type="SUN")
        sun = bpy.context.object
        sun.data.energy = energy
        sun.data.color = color
        sun.data.angle = math.radians(3)
        # point the sun from behind the window into the room
        d = Vector((-0.35, -1.0, -math.tan(math.radians(elev)))).normalized()
        sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

    if m["lamp"]:
        bpy.ops.object.light_add(type="SPOT", location=(-0.15, 2.43, 1.28))
        spot = bpy.context.object
        spot.data.energy = m["lamp"]
        spot.data.color = (1.0, 0.72, 0.42)
        spot.data.spot_size = math.radians(95)
        spot.data.spot_blend = 0.6
        spot.data.shadow_soft_size = 0.05
        spot.rotation_euler = (math.radians(25), 0, 0)
        bpy.ops.object.light_add(type="POINT", location=(-0.15, 2.43, 1.3))
        glow = bpy.context.object
        glow.data.energy = m["lamp"] * 0.25
        glow.data.color = (1.0, 0.7, 0.4)
        glow.data.shadow_soft_size = 0.1

    if m["lamp"]:
        bpy.ops.object.light_add(type="POINT", location=(2.0, -0.4, 1.5))
        fl = bpy.context.object
        fl.data.energy = m["lamp"] * 0.8
        fl.data.color = (1.0, 0.72, 0.45)
        fl.data.shadow_soft_size = 0.15
        # make the shades glow a little when the lamps are on
        for name, strength in (("fl_shade", 0.9), ("lamp_shade", 0.4)):
            sm = bpy.data.objects[name].data.materials[0]
            bsdf = sm.node_tree.nodes["Principled BSDF"]
            bsdf.inputs["Emission Color"].default_value = (1.0, 0.75, 0.45, 1)
            bsdf.inputs["Emission Strength"].default_value = strength * m["lamp"] / 60

    # soft fill from the open (camera) side so the diorama never goes black
    bpy.ops.object.light_add(type="AREA", location=(4.5, -4.5, 5.0))
    fill = bpy.context.object
    fill.data.energy = m["fill_e"]
    fill.data.color = m["fill"]
    fill.data.size = 6
    fill.rotation_euler = (Vector((0, 0.5, 0.8)) - fill.location).to_track_quat("-Z", "Y").to_euler()

    # orthographic diorama camera
    bpy.ops.object.camera_add(location=(9.5, -9.0, 8.2))
    cam = bpy.context.object
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 8.2
    target = Vector((-0.1, 0.4, 1.0))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam


def render(path, samples, res):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
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
    a = ap.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    win_c, _ = build_room()
    build_desk()
    build_angle_bench()
    build_bookshelf()
    build_cabinet()
    build_wall_things()
    build_reading_corner()
    build_decor()
    setup_lights_and_camera(a.mood, win_c)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=a.save)
    if a.out:
        render(a.out, a.samples, tuple(int(v) for v in a.res.split("x")))


if __name__ == "__main__":
    main()
