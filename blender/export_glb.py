"""Bake the study's surfaces into textures and export the model the web page loads.

    python3 blender/export_glb.py web/assets/study.glb
    python3 blender/export_glb.py /tmp/study.glb --quick       # few samples, small textures

The study is built with procedural surface detail (build_study.py, detail=True). Each
clickable group, the top drawer and four parts of the room then become one mesh, named for
the web app. Every mesh is unwrapped (faces the diorama camera can never see, or that something
else always covers, get no texture space), and its base colour (wood grain, weave, paper fibre) and ambient occlusion are baked
with Cycles and multiplied into one JPEG. Parts in a plain colour (ink, slots, bulbs) keep a
plain material instead. Lighting stays live in the browser, so the same textures serve
morning, dusk and night.

Finally glTF-Transform (through npx) quantizes and meshopt-compresses the geometry, which
the page decodes with three.js's MeshoptDecoder; --no-compress skips that.
"""
import argparse
import math
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import bpy
import bmesh  # after bpy: the bpy package puts it on the path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import build_study as bs  # noqa: E402

# parts of the room baked together; everything else belongs to a clickable group
ROOM_UNITS = (("room_floor", ("ENV_floorboards", "ENV_plinth", "ENV_floor_book")),
              ("room_walls", ("ENV_wall", "ENV_cap", "ENV_wains")),
              ("room_window", ("WIN_",)),
              ("room_clock", ("CLOCK_",)))
SPECIAL = ("bulb", "lampshade", "shade2")   # the web app finds these by name to make them glow
CLOSE_UP = ("letter", "desk_papers", "angle_bench", "checklist", "magazines", "caricature", "drawer_body",
            "drawer_slide", "bookshelf", "calendar", "open_book", "lamp")   # the web app zooms in on these
PX_PER_M = (360, 560)                       # texture density aimed for: the room, close-ups
PACKING = 0.55                              # share of a texture the unwrapped islands fill
AO_DISTANCE = 0.35
AO_FLOOR = 0.3                              # brightness left under full occlusion
GLTF_TRANSFORM = "@gltf-transform/cli@4.5.1"


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def select(objs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def view_directions():
    """Directions toward the camera over the web page's whole orbit range, in Blender axes."""
    off = Vector((9.6, 7.2, 9.4))             # HOME_POS - HOME_TARGET in web/study.html (three.js axes)
    polar0, az0 = math.acos(off.y / off.length), math.atan2(off.x, off.z)
    dirs = []
    for da in np.linspace(-0.4, 0.4, 5):      # minAzimuthAngle .. maxAzimuthAngle
        for dp in np.linspace(-0.18, 0.12, 4):  # minPolarAngle .. maxPolarAngle
            p, a = polar0 + dp, az0 + da
            x, y, z = math.sin(p) * math.sin(a), math.cos(p), math.sin(p) * math.cos(a)
            dirs.append((x, -z, y))           # three.js (x, y, z) is Blender (x, -z, y)
    return np.array(dirs)


# ---------------------------------------------------------------- one mesh per unit

def unit_of(ob):
    if ob.get("keep"):
        return ob.name
    if ob.get("slide"):
        return "drawer_slide"
    if ob.parent is not None:
        return ob.parent.name
    for unit, prefixes in ROOM_UNITS:
        if ob.name.startswith(prefixes):
            return unit
    raise ValueError(f"no unit for {ob.name}")


def make_units():
    """Apply the modifiers, then join each unit's parts into one mesh in world space."""
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    parts = {}
    for o in meshes:
        parts.setdefault(unit_of(o), []).append(o)
    select(meshes)
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    for e in [o for o in bpy.data.objects if o.type == "EMPTY"]:
        bpy.data.objects.remove(e)
    units = {}
    for name, objs in parts.items():
        select(objs)
        if len(objs) > 1:
            bpy.ops.object.join()
        ob = bpy.context.view_layer.objects.active
        ob.name = ob.data.name = name
        if not ob.get("keep"):                # clock hands keep their pivot at the centre
            select([ob])
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        units[name] = ob
    body = units.pop("drawer")
    body.name = body.data.name = "drawer_body"
    units[body.name] = body
    holder("drawer", (0, 0, 0), [body, units["drawer_slide"]])
    for hand in ("clock_hour", "clock_minute"):
        ob = units.pop(hand)
        ob.name = ob.data.name = hand + "_mesh"
        units[ob.name] = ob
        holder(hand, ob.location.copy(), [ob])
    bpy.context.view_layer.update()
    return units


def date_card():
    """The calendar's printed date gives way to a blank card in the same place, which the web
    page writes today's date on."""
    digits = bpy.data.objects["CAL_date"]
    bpy.context.view_layer.update()
    co = np.array([v.co for v in digits.data.vertices])
    (x0, y, z0), (x1, _, z1) = co.min(axis=0) - (0.008, 0, 0.008), co.max(axis=0) + 0.008
    me = bpy.data.meshes.new("calendar_date")
    me.from_pydata([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], [], [(0, 1, 2, 3)])   # faces -y, the front
    uv = me.uv_layers.new(name="UVMap")
    for loop, corner in zip(me.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[loop.index].uv = corner
    me.materials.append(bs.mat("date", color=bs.PALETTE["paper"], rough=0.9))
    card = bpy.data.objects.new("calendar_date", me)
    bpy.context.scene.collection.objects.link(card)
    card.matrix_world = digits.matrix_world
    card["keep"] = True
    bpy.data.objects.remove(digits)


def holder(name, loc, kids):
    """An empty that moves its parts: the drawer, so its top drawer can slide out on its own,
    and each clock hand, so it turns about the clock's centre."""
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = loc
    bpy.context.view_layer.update()
    for k in kids:
        k.parent = e
        k.matrix_parent_inverse = e.matrix_world.inverted()


# ---------------------------------------------------------------- materials

def describe(m):
    bsdf = m.node_tree.nodes["Principled BSDF"]
    return dict(textured=bsdf.inputs["Base Color"].is_linked,
                colour=tuple(bsdf.inputs["Base Color"].default_value),
                rough=round(bsdf.inputs["Roughness"].default_value, 2),
                metal=round(bsdf.inputs["Metallic"].default_value, 2))


def emit_base_colour(m):
    """Show the base colour as emission, so an EMIT bake records it without any lighting."""
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(bsdf.inputs["Base Color"].links[0].from_socket, em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])


def bake_target(m, img):
    nt = m.node_tree
    node = nt.nodes.get("BAKE") or nt.nodes.new("ShaderNodeTexImage")
    node.name = "BAKE"
    node.image = img
    nt.nodes.active = node


def drop_bake_target(m):
    node = m.node_tree.nodes.get("BAKE")
    if node:
        m.node_tree.nodes.remove(node)


def new_material(name, d, img=None):
    """A plain Principled material: the baked texture as base colour, or the part's own colour."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    if img:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = d["colour"]
    bsdf.inputs["Roughness"].default_value = d["rough"]
    bsdf.inputs["Metallic"].default_value = d["metal"]
    return m


def replace_materials(ob, info, img):
    """Textured slots with the same roughness and metal share one material on the baked
    texture; plain slots keep their material. The glowing parts get their own, by name.
    Without a texture (nothing of the unit is in view) textured slots fall back to their colour."""
    me, unit = ob.data, ob.name
    new, keys, remap = [], {}, []
    for m in me.materials:
        d, base = info[m.name], m.name.split(".")[0]
        if not d["textured"]:
            key = ("plain", m.name)
        elif img is None:
            key = ("flat", m.name)
        elif base in SPECIAL:
            key = ("special", base)
        else:
            key = ("tex", d["rough"], d["metal"])
        if key not in keys:
            keys[key] = len(new)
            if key[0] == "plain" and base in SPECIAL:
                nm = m.copy()
                nm.name = f"{base}.{unit}"
            elif key[0] == "plain":
                nm = m
            elif key[0] == "flat":
                nm = new_material(f"{base}.{unit}", d)
            else:
                label = base if key[0] == "special" else str(sum(1 for k in keys if k[0] == "tex"))
                nm = new_material(f"{label}.{unit}", d, img)
            new.append(nm)
        remap.append(keys[key])
    idx = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", idx)
    idx = np.array(remap, np.int32)[idx] if len(remap) else idx
    me.materials.clear()
    for m in new:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", idx)
    me.update()


# ---------------------------------------------------------------- unwrap and bake

def scene_bvh(units):
    """What can hide a face. The clock hands turn and the date card is paper-thin, so not them."""
    verts, polys = [], []
    for ob in units.values():
        if ob.get("keep"):
            continue
        mw, base = ob.matrix_world, len(verts)
        verts += [mw @ v.co for v in ob.data.vertices]
        polys += [[base + i for i in p.vertices] for p in ob.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


def visible_faces(ob, dirs, bvh, textured):
    """Faces with a baked texture that the camera can see: facing it somewhere in the orbit
    range, and with a clear line toward it from the centre or near a corner. Returns the
    faces and their area."""
    me, mw = ob.data, ob.matrix_world
    n = len(me.polygons)
    normals = np.empty(n * 3, np.float32)
    me.polygons.foreach_get("normal", normals)
    areas = np.empty(n, np.float32)
    me.polygons.foreach_get("area", areas)
    mats = np.empty(n, np.int32)
    me.polygons.foreach_get("material_index", mats)
    rot = mw.to_3x3()
    world_normals = normals.reshape(n, 3) @ np.array(rot).T
    use = np.isin(mats, [i for i, m in enumerate(me.materials) if textured(m)])
    if ob.get("keep") or ob.get("slide"):     # they turn or slide out, so keep every side
        return use, float(areas[use].sum())
    use &= (world_normals @ dirs.T).max(axis=1) > 0.0
    rays = [Vector(d) for d in dirs[::3]]
    for i in np.flatnonzero(use):
        poly = me.polygons[i]
        c, nrm = mw @ poly.center, Vector(world_normals[i]).normalized()
        pts = [c]
        if poly.area > 0.0005:
            pts += [c.lerp(mw @ me.vertices[v].co, 0.9) for v in poly.vertices]
        use[i] = any(bvh.ray_cast(q + nrm * 2e-4, d, 40.0)[0] is None
                     for q in pts for d in rays if nrm.dot(d) > 0)
    return use, float(areas[use].sum())


def unwrap(ob, use, size):
    """Smart-project the chosen faces and pack them, leaving a free corner. Every other face
    sits on one point in that corner, so it costs no texels and gets the unit's average colour."""
    me = ob.data
    me.uv_layers.new(name="bake")
    select([ob])
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.mesh.select_all(action="DESELECT")
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        if use[f.index]:
            f.select_set(True)
    bmesh.update_edit_mesh(me)
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=4 / size, shape_method="AABB")
    bm = bmesh.from_edit_mesh(me)
    uv = bm.loops.layers.uv.active
    for f in bm.faces:
        for loop in f.loops:
            loop[uv].uv = loop[uv].uv * 0.97 if use[f.index] else Vector((0.985, 0.985))
    bmesh.update_edit_mesh(me)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake(ob, img, kind, samples):
    """Bake into img; texels the bake does not reach stay at -1, so they can be found later."""
    img.pixels.foreach_set(np.full(len(img.pixels), -1.0, np.float32))
    for m in ob.data.materials:
        bake_target(m, img)
    bpy.context.scene.cycles.samples = samples
    select([ob])
    bpy.ops.object.bake(type=kind, margin=6, margin_type="EXTEND", use_clear=False, target="IMAGE_TEXTURES")


def pixels(img):
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


def write_jpeg(colour, ao, path):
    """Base colour times ambient occlusion, linear to sRGB, top row first. Texels no face
    reached get the average, which is what hidden faces show through gaps."""
    col, occ = pixels(colour)[..., :3], pixels(ao)[..., :1]
    empty = col[..., 0] < -0.5
    col[empty] = col[~empty].mean(axis=0)
    occ[empty] = occ[~empty].mean()
    lin = np.clip(col * (AO_FLOOR + (1 - AO_FLOOR) * occ), 0.0, 1.0)
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    px = (srgb * 255 + 0.5).astype(np.uint8)[::-1]
    Image.fromarray(px, "RGB").save(path, quality=88, optimize=True, progressive=True)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="web/assets/study.glb")
    ap.add_argument("--quick", action="store_true", help="few samples and small textures, to try things")
    ap.add_argument("--keep-textures", help="also copy the baked JPEGs to this folder")
    ap.add_argument("--no-compress", action="store_true", help="leave the geometry uncompressed")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    a = ap.parse_args(argv)
    t0 = time.time()

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bs.build_study(detail=True, lights=False)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.world = bpy.data.worlds.new("bake")
    scene.world.light_settings.distance = AO_DISTANCE
    log("built", len(bpy.data.objects), "objects")

    date_card()
    info = {m.name: describe(m) for m in bpy.data.materials}
    for m in bpy.data.materials:
        if info[m.name]["textured"]:
            emit_base_colour(m)
    units = make_units()
    log("joined into", len(units), "meshes:", ", ".join(sorted(units)))

    dirs, bvh = view_directions(), scene_bvh(units)
    moving = [ob for ob in units.values() if ob.get("keep")]
    for ob in moving:                         # the hands turn, so they must leave no shade on the face
        ob.hide_render = True
    tmp = Path(tempfile.mkdtemp(prefix="study_tex_"))
    textured = lambda m: info[m.name]["textured"]  # noqa: E731
    max_size = 512 if a.quick else 2048
    for name, ob in sorted(units.items()):
        use, area = visible_faces(ob, dirs, bvh, textured)
        if not area:
            replace_materials(ob, info, None)
            log(f"{name:14s} plain colours only")
            continue
        side = math.sqrt(area / PACKING) * PX_PER_M[name in CLOSE_UP] / (4 if a.quick else 1)
        size = int(min(max(2 ** round(math.log2(side)), 128), max_size))
        unwrap(ob, use, size)
        colour = bpy.data.images.new(name + "_colour", size, size, alpha=False, float_buffer=True)
        ao = bpy.data.images.new(name + "_ao", size, size, alpha=False, float_buffer=True)
        bake(ob, colour, "EMIT", 2 if a.quick else 8)
        bake(ob, ao, "AO", 8 if a.quick else 64)
        path = tmp / f"{name}.jpg"
        write_jpeg(colour, ao, path)
        for m in ob.data.materials:
            drop_bake_target(m)
        replace_materials(ob, info, bpy.data.images.load(str(path)))
        log(f"{name:14s} {area:6.2f} m2 -> {size}px, {path.stat().st_size // 1024} KB, "
            f"{len(ob.data.materials)} materials")

    for ob in moving:
        ob.hide_render = False
    for ob in units.values():                 # the procedural inputs are not needed any more
        for attr in ("pc", "pr"):
            if attr in ob.data.attributes:
                ob.data.attributes.remove(ob.data.attributes[attr])
        for m in ob.data.materials:           # every mesh is closed and faces outward: one-sided
            m.use_backface_culling = True
    if a.keep_textures:
        Path(a.keep_textures).mkdir(parents=True, exist_ok=True)
        for p in tmp.glob("*.jpg"):
            shutil.copy(p, a.keep_textures)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out if a.no_compress else tmp / "raw.glb"
    bpy.ops.export_scene.gltf(filepath=str(raw), export_format="GLB", use_selection=False, export_apply=False,
                              export_lights=False, export_cameras=False, export_yup=True,
                              export_image_format="AUTO", export_texcoords=True, export_normals=True,
                              export_tangents=False, export_attributes=False, export_extras=False,
                              export_animations=False)
    if not a.no_compress:
        subprocess.run(["npx", "--yes", GLTF_TRANSFORM, "meshopt", str(raw), str(out), "--level", "medium"],
                       check=True)
    shutil.rmtree(tmp)
    log(f"exported {out} ({out.stat().st_size // 1024} KB) in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
