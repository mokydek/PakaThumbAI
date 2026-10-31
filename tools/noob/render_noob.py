"""Builds the classic Roblox 'noob' avatar from blocks and renders a LoRA training set."""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1]
FACE = sys.argv[sys.argv.index("--") + 2]
COUNT = int(sys.argv[sys.argv.index("--") + 3])
os.makedirs(OUT, exist_ok=True)
random.seed(11)

YELLOW = (0.913, 0.604, 0.030, 1)   # Bright yellow 245,205,48 (linear)
BLUE = (0.004, 0.141, 0.413, 1)     # Bright blue 13,105,172
GREEN = (0.371, 0.503, 0.063, 1)    # Br. yellowish green 164,189,71


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = 48
    s.cycles.use_denoising = True
    s.render.resolution_x, s.render.resolution_y = 768, 512
    try:
        s.view_settings.view_transform = "Standard"
    except TypeError:
        pass
    return s


def mat(name, color, rough=0.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    return m


def block(name, size, loc, material, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bev = o.modifiers.new("bevel", "BEVEL")
    bev.width, bev.segments = 0.06, 3
    o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    if parent:
        o.parent = parent
        o.location = Vector(loc) - parent.location
    return o


def pivot(name, loc, parent):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    e.parent = parent
    return e


def build():
    root = bpy.data.objects.new("noob", None)
    bpy.context.collection.objects.link(root)
    y, b, g = mat("yellow", YELLOW), mat("blue", BLUE), mat("green", GREEN)
    block("torso", (2, 1, 2), (0, 0, 3), b, root)
    parts = {}
    for side, x in (("R", -1.5), ("L", 1.5)):
        p = pivot("shoulder" + side, (x, 0, 3.8), root)
        block("arm" + side, (1, 1, 2), (x, 0, 3), y, p)
        parts["arm" + side] = p
    for side, x in (("R", -0.5), ("L", 0.5)):
        p = pivot("hip" + side, (x, 0, 2), root)
        block("leg" + side, (1, 1, 2), (x, 0, 1), g, p)
        parts["leg" + side] = p
    # head: rounded cylinder with the face projected on the front
    neck = pivot("neck", (0, 0, 4), root)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.62, depth=1.2, location=(0, 0, 4.62))
    head = bpy.context.object
    head.parent = neck
    head.location = (0, 0, 0.62)
    bev = head.modifiers.new("bevel", "BEVEL")
    bev.width, bev.segments = 0.12, 4
    bpy.ops.object.shade_smooth()
    hm = bpy.data.materials.new("head")
    hm.use_nodes = True
    nt = hm.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.45
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(FACE)
    tex.projection = "TUBE"
    tex.extension = "CLIP"
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    # object coords of the head: center 0, radius .62 -> map to 0..1 tube space
    mapping.inputs["Scale"].default_value = (0.8, 0.8, 0.83)
    mapping.inputs["Location"].default_value = (0.5, 0.5, 0.5)
    mapping.inputs["Rotation"].default_value = (0, 0, math.radians(180))
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.inputs["Color1"].default_value = YELLOW
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(tex.outputs["Color"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    head.data.materials.append(hm)
    parts["neck"] = neck
    return root, parts


POSES = {
    "standing idle": dict(armR=(0, 0), armL=(0, 0), legR=0, legL=0),
    "waving one arm": dict(armR=(0, 165), armL=(0, 0), legR=0, legL=0),
    "both arms raised in panic": dict(armR=(0, 160), armL=(0, 160), legR=0, legL=0),
    "running": dict(armR=(50, 0), armL=(-50, 0), legR=-40, legL=40),
    "walking": dict(armR=(20, 0), armL=(-20, 0), legR=-18, legL=18),
    "pointing forward": dict(armR=(-90, 0), armL=(0, 0), legR=0, legL=0),
    "jumping": dict(armR=(0, 130), armL=(0, 130), legR=-20, legL=10),
    "arms out to the sides": dict(armR=(0, 90), armL=(0, 90), legR=0, legL=0),
}


def set_pose(parts, p):
    # (forward, outward) degrees; forward<0 = toward the camera, outward>0 = raised to the side
    parts["armR"].rotation_euler = (math.radians(p["armR"][0]), math.radians(p["armR"][1]), 0)
    parts["armL"].rotation_euler = (math.radians(p["armL"][0]), -math.radians(p["armL"][1]), 0)
    parts["legR"].rotation_euler = (math.radians(p["legR"]), 0, 0)
    parts["legL"].rotation_euler = (math.radians(p["legL"]), 0, 0)


SCENES = {
    "on a gray baseplate under a blue sky": dict(world=(0.35, 0.55, 0.9), floor=(0.35, 0.35, 0.35), sun=3.0, grid=True),
    "on green grass under a bright sky": dict(world=(0.5, 0.7, 1.0), floor=(0.1, 0.35, 0.05), sun=3.5, grid=False),
    "in a dark room lit by a single spotlight": dict(world=(0.002, 0.002, 0.004), floor=(0.05, 0.05, 0.05), sun=0, spot=2500, ambient=0.08, grid=False),
    "at sunset with orange sky": dict(world=(1.0, 0.35, 0.08), floor=(0.25, 0.12, 0.06), sun=3.0, grid=False),
    "at night with blue moonlight": dict(world=(0.005, 0.01, 0.04), floor=(0.03, 0.04, 0.06), sun=2.0, ambient=0.15, grid=False),
    "on a plain white background": dict(world=(0.9, 0.9, 0.9), floor=None, sun=3.0, grid=False),
    "on a red background": dict(world=(0.6, 0.02, 0.02), floor=None, sun=3.0, grid=False),
}

VIEWS = {
    "front view": (0, 0.0, 15, 2.9),
    "three quarter view": (35, 0.0, 15, 2.9),
    "three quarter view from the other side": (-35, 0.0, 15, 2.9),
    "low angle view": (20, -0.6, 11, 2.4),
    "close-up of the head and torso": (15, 0.1, 6.5, 4.2),
    "full body from a distance": (-20, 0.15, 20, 2.9),
}


def scene_setup(s, cfg):
    w = bpy.data.worlds.new("w")
    s.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    bg.inputs["Color"].default_value = (*cfg["world"], 1)
    # the background colour is only what the camera sees; lighting stays neutral so the noob keeps its colours
    amb = nt.nodes.new("ShaderNodeBackground")
    amb.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1)
    amb.inputs["Strength"].default_value = cfg.get("ambient", 0.6)
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(amb.outputs["Background"], mix.inputs[1])
    nt.links.new(bg.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], nt.nodes["World Output"].inputs["Surface"])
    if cfg.get("floor"):
        bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
        f = bpy.context.object
        fm = mat("floor", (*cfg["floor"], 1), 0.8)
        if cfg.get("grid"):
            nt = fm.node_tree
            chk = nt.nodes.new("ShaderNodeTexChecker")
            chk.inputs["Scale"].default_value = 100
            chk.inputs["Color1"].default_value = (0.32, 0.32, 0.32, 1)
            chk.inputs["Color2"].default_value = (0.28, 0.28, 0.28, 1)
            nt.links.new(chk.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
        f.data.materials.append(fm)
    if cfg.get("sun"):
        bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), 0, math.radians(random.uniform(-60, 60))))
        sun = bpy.context.object.data
        sun.energy = cfg["sun"]
        if cfg.get("warm"):
            sun.color = (1.0, 0.6, 0.35)
        if cfg.get("cold"):
            sun.color = (0.55, 0.65, 1.0)
    if cfg.get("spot"):
        bpy.ops.object.light_add(type="SPOT", location=(1.5, -3, 9))
        sp = bpy.context.object
        sp.data.energy = cfg["spot"]
        sp.data.spot_size = math.radians(40)
        sp.rotation_euler = (math.radians(20), math.radians(10), 0)


def camera(s, view):
    yaw, pitch, dist, target_z = VIEWS[view]
    yaw = math.radians(yaw + random.uniform(-8, 8))
    cam_z = target_z + dist * math.sin(pitch) + (0.5 if pitch >= 0 else 0)
    loc = Vector((dist * math.sin(yaw), -dist * math.cos(yaw), max(0.6, cam_z)))
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object
    d = Vector((0, 0, target_z)) - loc
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50
    s.camera = cam


combos = [(p, sc, v) for p in POSES for sc in SCENES for v in VIEWS]
random.shuffle(combos)
for i, (pose, scn, view) in enumerate(combos[:COUNT], 1):
    s = reset()
    root, parts = build()
    set_pose(parts, POSES[pose])
    root.rotation_euler = (0, 0, math.radians(random.uniform(-10, 10)))
    scene_setup(s, SCENES[scn])
    camera(s, view)
    name = f"noob_{i:03d}"
    s.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    with open(os.path.join(OUT, name + ".txt"), "w") as f:
        f.write(f"pakathumb thumbnail, roblox noob character, blocky avatar with a yellow head with a simple "
                f"smiling face, yellow arms, blue torso, green legs, {pose}, {view}, {scn}")
    print("rendered", name, pose, "|", scn, "|", view, flush=True)
