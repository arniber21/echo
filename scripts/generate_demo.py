"""Generate consent-free schematic demo evidence (Pillow, FFmpeg, macOS say).

The generated binaries are committed, so running the app needs none of these tools.
This is an illustrated scenario, never a recording of a real collision.
"""
from __future__ import annotations

import math
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo" / "media"
WIDTH, HEIGHT, FPS, SECONDS = 960, 540, 12, 20
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default(size=size)


def car(draw: ImageDraw.ImageDraw, x: float, y: float, color: str, label: str) -> None:
    draw.rounded_rectangle((x, y, x + 145, y + 66), 14, fill=color, outline="#17262c", width=3)
    draw.rounded_rectangle((x + 35, y + 7, x + 102, y + 59), 6, fill="#bfd3d6")
    draw.rectangle((x + 11, y - 4, x + 39, y + 5), fill="#1b252b")
    draw.rectangle((x + 11, y + 61, x + 39, y + 70), fill="#1b252b")
    draw.rectangle((x + 108, y - 4, x + 134, y + 5), fill="#1b252b")
    draw.rectangle((x + 108, y + 61, x + 134, y + 70), fill="#1b252b")
    draw.text((x + 47, y + 23), label, font=font(18), fill="#17262c")


def frame(t: float) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#e8ede8")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 78), fill="#182c32")
    draw.text((30, 16), "REWIND / SYNTHETIC EVIDENCE", font=font(24), fill="#f8f5ec")
    draw.text((30, 48), "Illustrated collision scenario · not real footage", font=font(15), fill="#acc6c5")
    draw.rectangle((0, 185, WIDTH, 413), fill="#52646a")
    for x in range(0, WIDTH, 100):
        draw.rectangle((x, 295, x + 50, 300), fill="#e5dbaa")
    draw.rectangle((835, 187, 844, 411), fill="#f3eee0")
    draw.rounded_rectangle((813, 92, 858, 176), 8, fill="#203238")
    draw.ellipse((823, 101, 848, 126), fill="#ef685b")
    draw.ellipse((823, 138, 848, 163), fill="#324549")
    draw.text((676, 125), "RED SIGNAL", font=font(18), fill="#8b3b32")
    # Car B waits at the stop line. Car A reaches its rear at exactly 8 seconds.
    x_a = 110 + min(t, 8) * (445 / 8)
    car(draw, x_a, 215, "#d49e47", "A")
    car(draw, 700, 215, "#69a4a0", "B")
    if 8 <= t < 9:
        draw.text((570, 339), "CONTACT + AUDIBLE IMPACT", font=font(18), fill="#fff1d6")
        draw.line((698, 208, 689, 223, 703, 238, 690, 254, 700, 280), fill="#f6d986", width=5)
    draw.text((30, 438), f"VIDEO CLOCK   {t:05.2f} s", font=font(24), fill="#263d43")
    draw.text((30, 479), "Overhead schematic. Car B stationary. Signal stays red throughout.", font=font(18), fill="#52646a")
    return image


def damage_photo(path: Path, color: str, label: str, detail: str) -> None:
    image = Image.new("RGB", (960, 640), "#e7e5dd")
    draw = ImageDraw.Draw(image)
    draw.text((36, 30), "SYNTHETIC DAMAGE ILLUSTRATION", font=font(26), fill="#233c40")
    draw.text((36, 75), detail, font=font(21), fill="#53676b")
    draw.rounded_rectangle((155, 180, 805, 475), 58, fill=color, outline="#263b42", width=5)
    draw.rounded_rectangle((325, 201, 650, 454), 25, fill="#adc3c5", outline="#263b42", width=3)
    draw.rectangle((190, 166, 290, 190), fill="#263238")
    draw.rectangle((190, 468, 290, 492), fill="#263238")
    draw.rectangle((675, 166, 775, 190), fill="#263238")
    draw.rectangle((675, 468, 775, 492), fill="#263238")
    damage_x = 785 if label == "A" else 173
    draw.line([(damage_x, 225), (damage_x - 14, 255), (damage_x + 7, 293), (damage_x - 17, 331), (damage_x + 5, 364), (damage_x - 12, 420)], fill="#623e32", width=10)
    draw.text((443, 300), f"CAR {label}", font=font(30), fill="#253a40")
    draw.text((36, 545), "Post-incident · capture time unknown · no EXIF timestamp", font=font(22), fill="#53676b")
    draw.text((36, 586), "Illustration only. Damage alone does not establish cause or fault.", font=font(18), fill="#53676b")
    image.save(path, quality=90)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        silent_video = temporary / "video.mp4"
        process = subprocess.Popen([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-crf", "23", str(silent_video),
        ], stdin=subprocess.PIPE)
        assert process.stdin is not None
        for index in range(FPS * SECONDS):
            process.stdin.write(frame(index / FPS).tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("FFmpeg could not encode the demo")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(silent_video), "-f", "lavfi",
            "-i", "aevalsrc=if(between(t\\,8\\,8.18)\\,0.7*sin(2*PI*95*t)*exp(-24*(t-8))\\,0):s=44100:d=20",
            "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", "-shortest", str(OUT / "demo-video.mp4"),
        ], check=True)
        narration = (
            "This is a synthetic witness statement for the Rewind demo. "
            "I was in the amber car approaching the teal car ahead of me. "
            "I remember that the traffic signal was green when the cars made contact. "
            "I heard a short bump and both vehicles stayed in the same lane. "
            "Afterwards I noticed damage to the front of the amber car. "
            "I cannot remember the exact speed, and I did not see anyone get hurt."
        )
        aiff = temporary / "narration.aiff"
        subprocess.run(["say", "-v", "Samantha", "-r", "160", "-o", str(aiff), narration], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-c:a", "aac", "-b:a", "96k", str(OUT / "demo-audio.m4a")], check=True)
    damage_photo(OUT / "demo-photo-front.jpg", "#d49e47", "A", "Car A · visible marks on front bumper")
    damage_photo(OUT / "demo-photo-side.jpg", "#69a4a0", "B", "Car B · visible marks on rear bumper")
    frame(8.2).save(OUT / "poster.jpg", quality=90)
    print("Generated synthetic demo video, voice memo, and two damage illustrations.")


if __name__ == "__main__":
    main()
