"""PakaThumbAI - thumbnail generator (talks to local ComfyUI).

Usage:
    generate.bat "a hydraulic press crushing a watermelon" -n 4
    generate.bat "..." --size roblox --lora none --seed 123
"""
import argparse
import copy
import json
import os
import random
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMFY_DIR = os.path.join(ROOT, "app", "ComfyUI")
WORKFLOW = os.path.join(ROOT, "workflows", "thumbnail_api.json")
LORA_DIR = os.path.join(ROOT, "models", "loras")
OUTPUT_DIR = os.path.join(ROOT, "outputs")
HOST, PORT = "127.0.0.1", 8188
URL = f"http://{HOST}:{PORT}"

TRIGGER = "pakathumb thumbnail"
STYLES = {
    "default": ("youtube thumbnail, vibrant saturated colors, high contrast, dramatic lighting, "
                "bold composition, sharp focus, highly detailed, 3d render"),
    "horror": ("roblox horror game thumbnail, dark, low key lighting, single dim light source, "
               "high contrast, film grain, vignette, eerie atmosphere, desaturated colors, 3d render"),
    "none": "",
}
STYLE = STYLES["default"]
SIZES = {
    # name: (base pass, hires pass, final image)
    "youtube": ((768, 432), (1280, 720), (1280, 720)),
    "roblox": ((768, 432), (1280, 720), (1920, 1080)),
}
DEFAULT_LORA = "pakathumb.safetensors"


def comfy_args():
    args = [
        os.path.join(COMFY_DIR, "main.py"),
        "--extra-model-paths-config", os.path.join(ROOT, "config", "extra_model_paths.yaml"),
        "--output-directory", OUTPUT_DIR,
        "--listen", HOST, "--port", str(PORT),
    ]
    extra = os.environ.get("PAKA_COMFY_ARGS", "").split()
    return args + extra


def port_open():
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex((HOST, PORT)) == 0


def api(path, data=None):
    req = urllib.request.Request(URL + path)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def ensure_comfy():
    if port_open():
        return
    if not os.path.isfile(os.path.join(COMFY_DIR, "main.py")):
        sys.exit("ComfyUI не установлен. Сначала запусти install.bat")
    print("Запускаю ComfyUI в фоне (первый раз может занять минуту)...")
    log = open(os.path.join(ROOT, "app", "comfyui.log"), "a", encoding="utf-8")
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    subprocess.Popen([sys.executable] + comfy_args(), cwd=COMFY_DIR, stdout=log,
                     stderr=subprocess.STDOUT, creationflags=flags)
    for _ in range(300):
        if port_open():
            try:
                api("/system_stats")
                return
            except Exception:
                pass
        time.sleep(1)
    sys.exit("ComfyUI не запустился за 5 минут. Смотри app/comfyui.log")


def available(node, field):
    info = api(f"/object_info/{node}")
    return info[node]["input"]["required"][field][0]


def build(base, prompt, lora, strength, seed, steps, cfg, size, negative, style=STYLE):
    wf = copy.deepcopy(base)
    (bw, bh), (hw, hh), (fw, fh) = SIZES[size]
    if lora:
        wf["2"]["inputs"].update(lora_name=lora, strength_model=strength, strength_clip=strength)
        text = f"{TRIGGER}, {prompt}"
    else:
        # no LoRA: wire everything straight to the checkpoint
        del wf["2"]
        for nid in ("3", "4"):
            wf[nid]["inputs"]["clip"] = ["1", 1]
        for nid in ("6", "8"):
            wf[nid]["inputs"]["model"] = ["1", 0]
        text = prompt
    if style:
        text += ", " + style
    wf["3"]["inputs"]["text"] = text
    if negative:
        wf["4"]["inputs"]["text"] += ", " + negative
    wf["5"]["inputs"].update(width=bw, height=bh)
    wf["7"]["inputs"].update(width=hw, height=hh)
    wf["10"]["inputs"].update(width=fw, height=fh)
    for nid in ("6", "8"):
        wf[nid]["inputs"].update(seed=seed, cfg=cfg)
    wf["6"]["inputs"]["steps"] = steps
    wf["8"]["inputs"]["steps"] = max(1, round(steps * 0.6))
    wf["11"]["inputs"]["filename_prefix"] = f"thumb_{size}"
    return wf


def run(wf):
    client = uuid.uuid4().hex
    try:
        res = api("/prompt", {"prompt": wf, "client_id": client})
    except urllib.error.HTTPError as e:
        sys.exit("ComfyUI отклонил задачу:\n" + e.read().decode("utf-8", "replace"))
    pid = res["prompt_id"]
    while True:
        time.sleep(1)
        try:
            hist = api(f"/history/{pid}")
        except (urllib.error.URLError, ConnectionError):
            sys.exit("ComfyUI упал во время генерации (часто не хватило памяти). Смотри app/comfyui.log")
        if pid not in hist:
            continue
        item = hist[pid]
        status = item.get("status", {})
        if status.get("status_str") == "error":
            msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
            detail = msgs[0][1].get("exception_message", "") if msgs else ""
            sys.exit("Ошибка генерации: " + detail.strip())
        if status.get("completed") or item.get("outputs"):
            out = []
            for img in item["outputs"].get("11", {}).get("images", []):
                out.append(os.path.join(OUTPUT_DIR, img.get("subfolder", ""), img["filename"]))
            return out


def main():
    p = argparse.ArgumentParser(description="PakaThumbAI - генерация thumbnail'ов")
    p.add_argument("prompt", help="что нарисовать (лучше на английском)")
    p.add_argument("-n", "--count", type=int, default=4, help="сколько вариантов (4)")
    p.add_argument("--size", choices=SIZES, default="youtube", help="youtube=1280x720, roblox=1920x1080")
    p.add_argument("--lora", default="auto", help="auto / none / имя файла из models/loras")
    p.add_argument("--strength", type=float, default=0.8, help="сила LoRA (0.8)")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--steps", type=int, default=25)
    p.add_argument("--cfg", type=float, default=6.5)
    p.add_argument("--negative", default="", help="что добавить в негативный промпт")
    p.add_argument("--style", choices=STYLES, default="default", help="default / horror / none")
    a = p.parse_args()

    ensure_comfy()

    ckpts = available("CheckpointLoaderSimple", "ckpt_name")
    with open(WORKFLOW, encoding="utf-8") as f:
        base = json.load(f)
    if base["1"]["inputs"]["ckpt_name"] not in ckpts:
        sys.exit("Нет базовой модели в models/checkpoints. Запусти install.bat ещё раз")

    loras = available("LoraLoader", "lora_name")
    lora = None
    if a.lora == "auto":
        lora = DEFAULT_LORA if DEFAULT_LORA in loras else None
    elif a.lora != "none":
        lora = a.lora if a.lora.endswith(".safetensors") else a.lora + ".safetensors"
        if lora not in loras:
            sys.exit(f"LoRA {lora} не найдена. Есть: {', '.join(loras) or 'ничего'}")
    print(f"LoRA: {lora or 'без LoRA'} | размер: {a.size} | вариантов: {a.count}")

    seed = a.seed if a.seed is not None else random.randint(0, 2**32 - 1)
    for i in range(a.count):
        wf = build(base, a.prompt, lora, a.strength, seed + i, a.steps, a.cfg, a.size, a.negative,
                   STYLES[a.style])
        t = time.time()
        for path in run(wf):
            print(f"[{i + 1}/{a.count}] seed {seed + i} -> {path} ({time.time() - t:.0f} c)")
    print("Готово. Все картинки в папке outputs")


if __name__ == "__main__":
    main()
