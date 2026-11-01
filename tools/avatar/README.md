# Roblox avatar dataset renderer

Builds Roblox-style avatars with in-game anatomy (R6 rigid limbs, R15-blocky with
elbows and knees) in Blender: random skin/shirt/pants colours, 5 faces, simple
generic accessories, 9 poses, 7 camera views, 9 scenes, 1-3 characters per frame.
Captions describe the avatar so the LoRA learns body parts and colours.

```
pip install bpy   # Python 3.11
python render_avatars.py -- <out_dir> . 1000 1          # CPU
python render_avatars.py -- <out_dir> . 1000 1 --gpu    # Blender GPU (OptiX/CUDA)
```
Already rendered files are skipped, so the job can be resumed.
