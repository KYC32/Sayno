"""Export the study as one .glb for the web app.

Every named group (desk_papers, lamp, letter, ...) becomes one mesh with that name so the
web app can pick it by name; everything else is merged into "room".

    python3 blender/export_glb.py web/assets/study.glb
"""
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).parent))
import build_study as bs  # noqa: E402


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bs.build_room()
    bs.build_desk()
    bs.build_angle_bench()
    bs.build_bookshelf()
    bs.build_cabinet()
    bs.build_wall_things()
    bs.build_reading_corner()
    bs.build_decor()


def bake_modifiers():
    """Apply bevels and the window boolean so the meshes are final."""
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render]
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.convert(target="MESH")
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.hide_render:
            bpy.data.objects.remove(o)


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    joined.data.name = name
    return joined


def merge_groups():
    empties = [o for o in bpy.data.objects if o.type == "EMPTY"]
    for e in empties:
        kids = [k for k in e.children if k.type == "MESH"]
        name = e.name
        for k in kids:  # keep world transform when unparenting
            mw = k.matrix_world.copy()
            k.parent = None
            k.matrix_world = mw
        bpy.data.objects.remove(e)
        if kids:
            join(kids, name)
    rest = [o for o in bpy.data.objects if o.type == "MESH" and o.parent is None
            and o.name not in {e for e in GROUP_NAMES}]
    join(rest, "room")


GROUP_NAMES = set()


def main(out):
    build()
    global GROUP_NAMES
    GROUP_NAMES = {o.name for o in bpy.data.objects if o.type == "EMPTY"}
    bake_modifiers()
    merge_groups()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=False,
                              export_apply=True, export_lights=False, export_cameras=False,
                              export_yup=True)
    print("exported", out, sorted(o.name for o in bpy.data.objects))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "web/assets/study.glb")
