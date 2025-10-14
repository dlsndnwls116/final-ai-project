# tools/smoke_render.py
from __future__ import annotations
import os
from PIL import Image, ImageDraw

try:
    from moviepy.editor import ImageClip, CompositeVideoClip
except Exception as e:
    print("moviepy import failed:", e)
    raise

os.makedirs("outputs/smoke", exist_ok=True)
img_path = "outputs/smoke/smoke.png"

# 480x852 세로 캔버스
im = Image.new("RGB", (480, 852), (240, 240, 240))
draw = ImageDraw.Draw(im)
draw.rectangle((40, 200, 440, 650), fill=(200, 220, 255))
draw.text((60, 60), "SMOKE", fill=(20, 20, 20))
im.save(img_path)

base = ImageClip(img_path, duration=1.0).resize((1080, 1920))
video = CompositeVideoClip([base])
out = "outputs/smoke/smoke.mp4"
video.write_videofile(out, fps=30, codec="libx264", audio=False, verbose=False, logger=None)
print(f"[SMOKE] wrote {out}")
