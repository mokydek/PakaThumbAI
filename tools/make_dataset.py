"""PakaThumbAI - generates a training dataset from config/dataset_prompts.txt.

Each prompt is rendered several times with the base model (no LoRA), the image
goes to dataset/ as gen_XXX.png and its caption to gen_XXX.txt.
"""
import argparse
import json
import os
import random
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate as g  # noqa: E402

PROMPTS = os.path.join(g.ROOT, "config", "dataset_prompts.txt")
DATASET = os.path.join(g.ROOT, "dataset")
# style anchor for SD 1.5: without it the model often drops the character
STYLE_PREFIX = "(roblox character:1.3), "
# keep other brands' toy/game looks out of the dataset
NEGATIVE = "lego, minifigure, minecraft"


def load_prompts(path):
    """Scene lines + optional settings lines: 'prefix: ...', 'style: ...', 'negative: ...'."""
    opts = {"prefix": STYLE_PREFIX, "style": "default", "negative": NEGATIVE}
    scenes = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, val = line.partition(":")
            if sep and key.strip() in opts and " " not in key.strip():
                opts[key.strip()] = val.strip()
            else:
                scenes.append(line)
    style = opts["style"]
    opts["style"] = g.STYLES.get(style, style)
    if opts["prefix"] and not opts["prefix"].endswith(" "):
        opts["prefix"] += " "
    return scenes, opts


def main():
    p = argparse.ArgumentParser(description="PakaThumbAI - генерация датасета для обучения")
    p.add_argument("--per-prompt", type=int, default=3, help="картинок на каждый промпт (3)")
    p.add_argument("--limit", type=int, default=0, help="взять только первые N промптов")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--prefix", default="gen", help="начало имени файлов (gen)")
    p.add_argument("--prompts", default=PROMPTS, help="файл со сценами (config/dataset_prompts.txt)")
    p.add_argument("--out", default=DATASET, help="папка датасета (dataset)")
    a = p.parse_args()

    prompts, opts = load_prompts(a.prompts)
    out_dir = a.out if os.path.isabs(a.out) else os.path.join(g.ROOT, a.out)
    if a.limit:
        prompts = prompts[:a.limit]
    total = len(prompts) * a.per_prompt
    os.makedirs(out_dir, exist_ok=True)
    pre = a.prefix + "_"
    existing = [f[len(pre):-4] for f in os.listdir(out_dir) if f.startswith(pre) and f.endswith(".png")]
    start = max([int(x) for x in existing if x.isdigit()] + [0]) + 1

    g.ensure_comfy()
    with open(g.WORKFLOW, encoding="utf-8") as f:
        base = json.load(f)
    if base["1"]["inputs"]["ckpt_name"] not in g.available("CheckpointLoaderSimple", "ckpt_name"):
        sys.exit("Нет базовой модели в models/checkpoints. Запусти install.bat ещё раз")

    print(f"Промптов: {len(prompts)} x {a.per_prompt} = {total} картинок -> {out_dir}")
    seed = a.seed if a.seed is not None else random.randint(0, 2**32 - 1)
    t0, n = time.time(), 0
    for prompt in prompts:
        for _ in range(a.per_prompt):
            wf = g.build(base, opts["prefix"] + prompt, None, 0, seed + n, 25, 6.5, "youtube",
                         opts["negative"], opts["style"])
            out = g.run(wf)
            name = f"{pre}{start + n:03d}"
            shutil.move(out[0], os.path.join(out_dir, name + ".png"))
            with open(os.path.join(out_dir, name + ".txt"), "w", encoding="utf-8") as f:
                f.write(f"{g.TRIGGER}, {prompt}")
            n += 1
            left = (time.time() - t0) / n * (total - n)
            print(f"[{n}/{total}] {name}.png  (осталось ~{left / 60:.0f} мин)")
    print("Готово. Открой папку dataset, удали неудачные картинки (вместе с их .txt) и запусти train.bat")


if __name__ == "__main__":
    main()
