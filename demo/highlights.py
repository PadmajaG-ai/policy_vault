"""Cut a silent ~60-second highlight clip (e.g. for LinkedIn) from the recorded demo.

Run after demo/assemble.py:   python demo/highlights.py
Writes demo/out/policy_vault_highlights_60s.mp4 (1920x1080, 30 fps, silent audio track).

Segments are anchored to narration scenes in timeline.json, so they follow a new recording.
Each segment gets a short on-screen label; the scan wait plays at 4x and is labelled as such.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("DEMO_OUT", HERE / "out"))
FONT = "C\\:/Windows/Fonts/segoeuib.ttf"

# The recording is 2560x1440 with the app's content centred; cropping to the content column
# zooms text ~1.2x with no loss of sharpness and drops the recording's own subtitle bar.
CROP_X, CROP_W, CROP_H = 200, 2160, 1215

# (scene key, seconds after the scene starts, source seconds, speed, crop top in px or None, label)
SEGMENTS = [
    ("intro", 0.0, 4.0, 1, None, ""),
    ("meet", 0.3, 3.0, 1, 0, "The expert retired. Nothing was written down."),
    ("scan", 0.7, 18.5, 4, 0, "Gemini reads the policy, code compares, Gemini finds root causes (4x speed)"),
    ("results", -1.3, 5.0, 1, 0, "12 rules checked: 4 drifts, 0 false alarms"),
    ("evidence", 1.0, 7.0, 1, 150, "Evidence side by side: policy, live config, the ticket that caused it"),
    ("gaps", -0.3, 4.5, 1, 0, "Gap finder: rules nobody can explain. Coverage 13 of 17"),
    ("interview", 6.5, 6.0, 1, 0, "AI interviews the retired expert, using clues from old tickets"),
    ("record", 2.0, 5.0, 1, 0, "The answer becomes a Decision Record. A human verifies it"),
    ("saved", 0.0, 4.0, 1, 0, "Knowledge coverage rises to 14 of 17"),
    ("ask_after_result", 3.2, 4.2, 1, 100, "Ask why before you change anything. Every answer cites its sources"),
    ("inventory", 13.75, 1.8, 0.5, 0, "Same engine, new domain: inventory"),  # results hold ~1.8 s before the outro
    ("close", 0.6, 5.0, 1, None, ""),
]


def main():
    tl = json.loads((OUT / "timeline.json").read_text())
    cuts = sorted(tl["cuts"])

    def shifted(x):
        return x - sum(min(max(0.0, x - a), b - a) for a, b in cuts)

    starts = {e["key"]: shifted(e["start"]) for e in tl["events"]}
    src = OUT / "policy_vault_demo.mp4"
    labels = OUT / "labels"
    labels.mkdir(exist_ok=True)

    parts, total = [], 0.0
    for i, (key, off, length, speed, crop_y, label) in enumerate(SEGMENTS):
        a = starts[key] + off
        chain = f"[0:v]trim=start={a:.2f}:end={a + length:.2f},setpts=(PTS-STARTPTS)/{speed},"
        if crop_y is not None:
            chain += f"crop={CROP_W}:{CROP_H}:{CROP_X}:{crop_y},"
        chain += "scale=1920:1080:flags=lanczos,setsar=1"
        if label:
            f = labels / f"{i:02d}.txt"
            f.write_text(label, encoding="utf-8")
            path = str(f).replace("\\", "/").replace(":", "\\:")
            chain += (f",drawtext=fontfile='{FONT}':textfile='{path}':fontsize=40:fontcolor=white"
                      ":box=1:boxcolor=0x101a2e@0.88:boxborderw=22:x=(w-text_w)/2:y=h-text_h-56")
        parts.append(chain + f",fps=30,format=yuv420p[v{i}]")
        total += length / speed
    n = len(SEGMENTS)
    parts.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]")

    out = OUT / "policy_vault_highlights_60s.mp4"
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src),
           "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
           "-filter_complex", ";".join(parts), "-map", "[v]", "-map", "1:a", "-t", f"{total:.2f}",
           "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-r", "30",
           "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr)
    print(f"Wrote {out}  ({total:.0f}s, {n} segments)")


if __name__ == "__main__":
    main()
