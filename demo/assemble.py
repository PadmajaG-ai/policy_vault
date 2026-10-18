"""Combine the screen recording and the narration into demo/out/policy_vault_demo.mp4.

Run after demo/voice.py and demo/record.py:   python demo/assemble.py
Trims only the idle waits record.py marked (no narration playing), then places every
narration clip at its recorded moment on the trimmed timeline.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("DEMO_OUT", HERE / "out"))
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def main():
    tl = json.loads((OUT / "timeline.json").read_text())
    cuts = sorted(tl["cuts"])
    end = tl["end"]

    keep, t = [], 0.0
    for a, b in cuts:
        keep.append((t, a))
        t = b
    keep.append((t, end))
    keep = [(a, b) for a, b in keep if b - a > 0.05]

    def shifted(x):
        return x - sum(min(max(0.0, x - a), b - a) for a, b in cuts)

    total = shifted(end)
    inputs = ["-i", tl["video"]]
    parts = [f"[0:v]trim=start={a:.2f}:end={b:.2f},setpts=PTS-STARTPTS[v{i}]" for i, (a, b) in enumerate(keep)]
    parts.append("".join(f"[v{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=0[v]")

    for n, ev in enumerate(tl["events"], start=1):
        inputs += ["-i", str(OUT / "audio" / f"{ev['key']}.wav")]
        ms = int(shifted(ev["start"]) * 1000)
        parts.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[a{n}]")
    n_audio = len(tl["events"])
    parts.append("".join(f"[a{n}]" for n in range(1, n_audio + 1))
                 + f"amix=inputs={n_audio}:normalize=0:dropout_transition=0,apad[a]")

    out = OUT / "policy_vault_demo.mp4"
    cmd = [FFMPEG, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(parts),
           "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
           # High quality for screen content, so text stays sharp after YouTube re-encodes it
           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-r", "30",
           "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr)
    m, s = divmod(round(total), 60)
    print(f"Wrote {out}  ({m}:{s:02d}, {len(cuts)} idle waits trimmed, {n_audio} narration clips)")
    if total > 240:
        print("  Note: longer than 4 minutes. Shorten lines in demo/script.py or raise --rate in voice.py.")


if __name__ == "__main__":
    main()
