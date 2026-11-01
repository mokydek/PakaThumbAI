"""Renders a large LoRA dataset of Roblox-style avatars with in-game anatomy.

R6 (rigid 1-piece limbs) and R15-blocky (elbows and knees) bodies, random skin and
clothing colours, faces, simple generic accessories, poses, cameras, scenes and
1-3 characters per frame. Usage:
    python render_avatars.py -- <out_dir> <faces_dir> <count> [start_index]
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
GPU = "--gpu" in args
args = [a for a in args if a != "--gpu"]
OUT, FACES, COUNT = args[0], args[1], int(args[2])
START = int(args[3]) if len(args) > 3 else 1
os.makedirs(OUT, exist_ok=True)


def lin(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (ch(c[0]), ch(c[1]), ch(c[2]), 1)


SKINS = {"yellow": (245, 205, 48), "light": (234, 184, 146), "tan": (204, 142, 105),
         "brown": (124, 92, 70), "dark brown": (86, 66, 54), "pale": (242, 243, 243)}
CLOTH = {"red": (196, 40, 28), "blue": (13, 105, 172), "green": (75, 151, 75), "black": (27, 42, 53),
         "white": (242, 243, 243), "orange": (218, 133, 65), "purple": (107, 50, 124),
         "pink": (255, 102, 204), "gray": (99, 95, 98), "dark blue": (33, 84, 185),
         "yellow": (245, 205, 48), "teal": (18, 238, 212), "lime green": (164, 189, 71)}
FACES_LIST = {"smiling face": "face_smile.png", "big grin": "face_grin.png", "angry face": "face_angry.png",
              "scared face": "face_scared.png", "cool face with sunglasses": "face_cool.png"}
ACCESSORIES = ["none", "none", "a black top hat", "a red baseball cap", "short brown hair",
               "spiky black hair", "a yellow hard hat", "headphones"]

POSES = {  # arms: (forward, outward) per side; legs: forward; bend: elbow/knee (R15 only)
    "standing": dict(aR=(0, 4), aL=(0, 4), lR=0, lL=0, el=0, kn=0),
    "waving": dict(aR=(0, 160), aL=(0, 4), lR=0, lL=0, el=40, kn=0),
    "running": dict(aR=(55, 0), aL=(-55, 0), lR=-45, lL=40, el=70, kn=60),
    "walking": dict(aR=(22, 0), aL=(-22, 0), lR=-20, lL=20, el=20, kn=15),
    "jumping with arms up": dict(aR=(0, 150), aL=(0, 150), lR=-25, lL=15, el=10, kn=50),
    "pointing forward": dict(aR=(-90, 0), aL=(0, 4), lR=0, lL=0, el=0, kn=0),
    "scared with hands up": dict(aR=(-40, 110), aL=(-40, 110), lR=-10, lL=10, el=90, kn=10),
    "arms spread wide": dict(aR=(0, 90), aL=(0, 90), lR=0, lL=0, el=0, kn=0),
    "celebrating": dict(aR=(-20, 135), aL=(-20, 135), lR=0, lL=0, el=30, kn=0),
}

SCENES = {
    "on a gray baseplate under a blue sky": dict(world=(0.35, 0.55, 0.9), floor=(0.35, 0.35, 0.35), grid=True, sun=3.0),
    "on green grass under a bright sky": dict(world=(0.5, 0.7, 1.0), floor=(0.1, 0.35, 0.05), sun=3.5, props=True),
    "in a dark room lit by a spotlight": dict(world=(0.002, 0.002, 0.004), floor=(0.05, 0.05, 0.05), sun=0, spot=2500, ambient=0.08),
    "at sunset with an orange sky": dict(world=(1.0, 0.35, 0.08), floor=(0.25, 0.12, 0.06), sun=3.0, props=True),
    "at night under blue moonlight": dict(world=(0.005, 0.01, 0.04), floor=(0.03, 0.04, 0.06), sun=2.0, ambient=0.15),
    "in a simple room with colored walls": dict(world=(0.6, 0.6, 0.6), floor=(0.5, 0.4, 0.3), sun=0, room=True, area=600),
    "in a blocky city with colorful buildings": dict(world=(0.45, 0.65, 1.0), floor=(0.2, 0.2, 0.22), sun=3.0, city=True),
    "on a plain white background": dict(world=(0.9, 0.9, 0.9), floor=None, sun=3.0),
    "on a bright colored background": dict(world=None, floor=None, sun=3.0),
}

VIEWS = {  # yaw, pitch(rad), distance factor, target height factor
    "front view": (0, 0.05, 1.0, 0.5),
    "three quarter view": (35, 0.05, 1.0, 0.5),
    "three quarter view from the other side": (-35, 0.05, 1.0, 0.5),
    "low angle view": (20, -0.45, 0.9, 0.45),
    "close-up": (15, 0.08, 0.5, 0.8),
    "wide shot": (-20, 0.15, 1.5, 0.5),
    "side view": (80, 0.05, 1.0, 0.5),
}

_mats = {}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _mats.clear()
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = 12
    if GPU:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = backend
                prefs.get_devices()
                if any(d.type == backend for d in prefs.devices):
                    break
            except TypeError:
                continue
        for d in prefs.devices:
            d.use = d.type != "CPU"
        s.cycles.device = "GPU"
        s.cycles.samples = 32
    s.cycles.use_denoising = True
    s.render.resolution_x, s.render.resolution_y = 768, 512
    try:
        s.view_settings.view_transform = "Standard"
    except TypeError:
        pass
    return s


def mat(rgb, rough=0.45):
    key = (rgb, rough)
    if key not in _mats:
        m = bpy.data.materials.new("m")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = lin(rgb)
        b.inputs["Roughness"].default_value = rough
        _mats[key] = m
    return _mats[key]


def box(size, loc, m, parent, bevel=0.06):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    o = bpy.context.object
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        b = o.modifiers.new("b", "BEVEL")
        b.width, b.segments = bevel, 3
    o.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    o.parent = parent
    o.location = loc
    return o


def cyl(r, depth, loc, m, parent, bevel=0.0, verts=40):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=(0, 0, 0))
    o = bpy.context.object
    if bevel:
        b = o.modifiers.new("b", "BEVEL")
        b.width, b.segments = bevel, 4
    o.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    o.parent = parent
    o.location = loc
    return o


def empty(loc, parent):
    e = bpy.data.objects.new("e", None)
    bpy.context.collection.objects.link(e)
    e.parent = parent
    e.location = loc
    return e


def head_material(skin, face_file):
    hm = bpy.data.materials.new("head")
    hm.use_nodes = True
    nt = hm.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.45
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(FACES, face_file), check_existing=True)
    tex.projection = "TUBE"
    tex.extension = "CLIP"
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.8, 0.8, 0.83)
    mp.inputs["Location"].default_value = (0.5, 0.5, 0.5)
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(180))
    nt.links.new(coord.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.inputs["Color1"].default_value = lin(skin)
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(tex.outputs["Color"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    return hm


def accessory(kind, head):
    if kind == "a black top hat":
        cyl(0.85, 0.08, (0, 0, 0.62), mat((27, 42, 53)), head)
        cyl(0.55, 0.9, (0, 0, 1.08), mat((27, 42, 53)), head)
    elif kind == "a red baseball cap":
        cyl(0.66, 0.35, (0, 0, 0.55), mat((196, 40, 28)), head, bevel=0.1)
        box((1.0, 0.7, 0.06), (0, -0.75, 0.42), mat((196, 40, 28)), head, bevel=0.02)
    elif kind == "short brown hair":
        cyl(0.67, 0.3, (0, 0.04, 0.5), mat((106, 57, 9)), head, bevel=0.12)
    elif kind == "spiky black hair":
        cyl(0.67, 0.25, (0, 0.04, 0.5), mat((27, 27, 27)), head, bevel=0.1)
        for i in range(6):
            a = i / 6 * math.tau
            bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.22, depth=0.5)
            c = bpy.context.object
            c.data.materials.append(mat((27, 27, 27)))
            c.parent = head
            c.location = (0.35 * math.cos(a), 0.35 * math.sin(a), 0.75)
            c.rotation_euler = (0.5 * math.sin(a), -0.5 * math.cos(a), 0)
    elif kind == "a yellow hard hat":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7, location=(0, 0, 0))
        s = bpy.context.object
        s.scale = (1, 1, 0.75)
        s.data.materials.append(mat((245, 205, 48), 0.3))
        bpy.ops.object.shade_smooth()
        s.parent = head
        s.location = (0, 0, 0.45)
        cyl(0.85, 0.05, (0, 0, 0.42), mat((245, 205, 48), 0.3), head)
    elif kind == "headphones":
        m = mat((27, 42, 53), 0.3)
        for x in (-0.68, 0.68):
            c = cyl(0.25, 0.15, (x, 0, 0.0), m, head)
            c.rotation_euler = (0, math.radians(90), 0)
        b = box((1.5, 0.12, 0.1), (0, 0, 0.72), m, head)


def avatar(root_loc, rng):
    kind = rng.choice(["R6", "R15"])
    skin_n = rng.choice(list(SKINS))
    shirt_n = rng.choice(list(CLOTH))
    pants_n = rng.choice([c for c in CLOTH if c != shirt_n])
    sleeves = rng.random() < 0.5
    face_n = rng.choice(list(FACES_LIST))
    acc = rng.choice(ACCESSORIES)
    pose_n = rng.choice(list(POSES))
    pose = POSES[pose_n]
    skin, shirt, pants = SKINS[skin_n], CLOTH[shirt_n], CLOTH[pants_n]
    arm_col = shirt if sleeves else skin

    root = empty(root_loc, None)
    box((2, 1, 2), (0, 0, 3), mat(shirt), root)
    jit = lambda v: v + rng.uniform(-12, 12)
    for side, x, sgn in (("R", -1.5, 1), ("L", 1.5, -1)):
        fwd, out = pose["a" + side]
        sh = empty((x, 0, 3.8), root)
        sh.rotation_euler = (math.radians(jit(fwd)), math.radians(sgn * jit(out)), 0)
        if kind == "R6":
            box((1, 1, 2), (0, 0, -0.8), mat(arm_col), sh)
        else:
            box((1, 1, 1.05), (0, 0, -0.3), mat(arm_col), sh)
            el = empty((0, 0, -0.8), sh)
            el.rotation_euler = (math.radians(-pose["el"] * rng.uniform(0.6, 1.2)), 0, 0)
            box((1, 1, 1.1), (0, 0, -0.55), mat(arm_col if rng.random() < 0.5 else skin), el)
        leg_fwd = pose["l" + side]
        hp = empty((x / 3, 0, 2), root)
        hp.rotation_euler = (math.radians(jit(leg_fwd)), 0, 0)
        if kind == "R6":
            box((1, 1, 2), (0, 0, -1), mat(pants), hp)
        else:
            box((1, 1, 1.05), (0, 0, -0.5), mat(pants), hp)
            kn = empty((0, 0, -1.0), hp)
            kn.rotation_euler = (math.radians(pose["kn"] * rng.uniform(0.5, 1.2)), 0, 0)
            box((1, 1, 1.05), (0, 0, -0.5), mat(pants), kn)
    neck = empty((0, 0, 4.0), root)
    neck.rotation_euler = (math.radians(rng.uniform(-10, 10)), 0, math.radians(rng.uniform(-20, 20)))
    head = cyl(0.62, 1.2, (0, 0, 0.62), head_material(skin, FACES_LIST[face_n]), neck, bevel=0.12, verts=48)
    if acc != "none":
        accessory(acc, head)
    root.rotation_euler = (0, 0, math.radians(rng.uniform(-25, 25)))
    if pose_n == "jumping with arms up":
        root.location.z += 1.0
    desc = (f"{kind} blocky roblox avatar with {skin_n} skin, a {shirt_n} shirt"
            f"{'' if sleeves else ' with bare arms'}, {pants_n} pants, {face_n}"
            f"{'' if acc == 'none' else ', wearing ' + acc}, {pose_n}")
    return desc


def scene(s, cfg, rng):
    w = bpy.data.worlds.new("w")
    s.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    col = cfg["world"] or tuple(c / 255 for c in rng.choice(list(CLOTH.values())))
    bg.inputs["Color"].default_value = (*col, 1)
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
        bpy.ops.mesh.primitive_plane_add(size=300)
        f = bpy.context.object
        fm = bpy.data.materials.new("floor")
        fm.use_nodes = True
        fb = fm.node_tree.nodes["Principled BSDF"]
        fb.inputs["Base Color"].default_value = (*cfg["floor"], 1)
        fb.inputs["Roughness"].default_value = 0.8
        if cfg.get("grid"):
            chk = fm.node_tree.nodes.new("ShaderNodeTexChecker")
            chk.inputs["Scale"].default_value = 150
            chk.inputs["Color1"].default_value = (0.32, 0.32, 0.32, 1)
            chk.inputs["Color2"].default_value = (0.28, 0.28, 0.28, 1)
            fm.node_tree.links.new(chk.outputs["Color"], fb.inputs["Base Color"])
        f.data.materials.append(fm)
    if cfg.get("props"):
        for _ in range(rng.randint(3, 8)):
            x, y = rng.uniform(-25, 25), rng.uniform(8, 40)
            if rng.random() < 0.5:  # blocky tree
                box((1.2, 1.2, 4), (x, y, 2), mat((105, 64, 40)), None, 0.03)
                box((4, 4, 4), (x, y, 5.5), mat((40, 127, 71)), None, 0.1)
            else:
                sz = rng.uniform(1.5, 4)
                box((sz, sz, sz), (x, y, sz / 2), mat(rng.choice(list(CLOTH.values()))), None, 0.05)
    if cfg.get("city"):
        for _ in range(14):
            x, y = rng.uniform(-40, 40), rng.uniform(15, 60)
            h = rng.uniform(8, 30)
            box((rng.uniform(5, 10), rng.uniform(5, 10), h), (x, y, h / 2), mat(rng.choice(list(CLOTH.values())), 0.6), None, 0.05)
    if cfg.get("room"):
        wall = mat(rng.choice(list(CLOTH.values())), 0.7)
        box((40, 0.5, 20), (0, 12, 10), wall, None, 0)
        box((0.5, 40, 20), (-14, 0, 10), wall, None, 0)
        box((0.5, 40, 20), (14, 0, 10), wall, None, 0)
        bpy.ops.object.light_add(type="AREA", location=(0, -4, 14))
        a = bpy.context.object
        a.data.energy = cfg["area"]
        a.data.size = 10
    if cfg.get("sun"):
        bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), 0, math.radians(rng.uniform(-60, 60))))
        bpy.context.object.data.energy = cfg["sun"]
    if cfg.get("spot"):
        bpy.ops.object.light_add(type="SPOT", location=(1.5, -4, 11))
        sp = bpy.context.object
        sp.data.energy = cfg["spot"]
        sp.data.spot_size = math.radians(50)
        sp.rotation_euler = (math.radians(22), math.radians(8), 0)


def camera(s, view, spread, rng):
    yaw, pitch, dfac, tfac = VIEWS[view]
    yaw = math.radians(yaw + rng.uniform(-8, 8))
    dist = (15 + spread * 1.6) * dfac
    tz = 5.2 * tfac + (0.8 if view == "close-up" else 0)
    loc = Vector((dist * math.sin(yaw), -dist * math.cos(yaw), max(0.5, tz + dist * math.sin(pitch) + 0.4)))
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object
    cam.rotation_euler = (Vector((0, 0, tz)) - loc).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50
    s.camera = cam


for i in range(START, START + COUNT):
    if os.path.exists(os.path.join(OUT, f"rbx_{i:04d}.txt")):
        continue
    rng = random.Random(1000 + i)
    s = reset()
    n = rng.choices([1, 2, 3], weights=[65, 22, 13])[0]
    spread = 0 if n == 1 else (n - 1) * 3.2
    descs = []
    for k in range(n):
        x = (k - (n - 1) / 2) * 3.4
        descs.append(avatar((x, rng.uniform(-0.5, 0.8) if n > 1 else 0, 0), rng))
    scn = rng.choice(list(SCENES))
    view = rng.choice(list(VIEWS))
    if n > 1 and view == "close-up":
        view = "front view"
    scene(s, SCENES[scn], rng)
    camera(s, view, spread, rng)
    name = f"rbx_{i:04d}"
    s.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    who = descs[0] if n == 1 else (f"{'two' if n == 2 else 'three'} roblox avatars: " + "; ".join(descs))
    with open(os.path.join(OUT, name + ".txt"), "w") as f:
        f.write(f"pakathumb thumbnail, roblox character, {who}, {view}, {scn}")
    print("rendered", name, flush=True)
