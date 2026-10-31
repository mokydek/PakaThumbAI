# Noob dataset renderer

Builds the classic Roblox noob avatar from blocks (yellow head and arms, blue torso,
green legs, smiling face) in Blender and renders a LoRA training set with varied
poses, camera angles and backgrounds. Background colour is camera-only, so lighting
stays neutral and the noob keeps its real colours.

```
pip install bpy            # Python 3.11
python render_noob.py -- <out_dir> face.png 48
```

Then: `train.bat -Dataset dataset_noob -Name pakanoob -Epochs 6`
and `generate.bat "roblox noob character ..." --lora pakanoob`.
