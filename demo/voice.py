"""Synthesise the narration with Google Cloud Text-to-Speech (Indian English, female voice).

Run:   python demo/voice.py                      (default voice)
       python demo/voice.py --list               (show en-IN voices and their gender)
       python demo/voice.py --voice en-IN-Chirp3-HD-Aoede
       python demo/voice.py --silent             (no API: silent clips timed by word count, for dry runs)

Needs the Text-to-Speech API once:  gcloud services enable texttospeech.googleapis.com
Writes demo/out/audio/<key>.wav plus durations.json; unchanged lines are not re-synthesised.
"""
import argparse
import hashlib
import json
import os
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from script import LINES  # noqa: E402

OUT = Path(os.environ.get("DEMO_OUT", Path(__file__).resolve().parent / "out")) / "audio"
DEFAULT_VOICE = "en-IN-Neural2-A"  # Indian English, female
RATE = 24000


def client():
    from dotenv import load_dotenv
    from google.api_core.client_options import ClientOptions
    from google.cloud import texttospeech
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    return texttospeech, texttospeech.TextToSpeechClient(client_options=ClientOptions(quota_project_id=project))


def list_voices():
    tts, c = client()
    for v in c.list_voices(language_code="en-IN").voices:
        print(f"{v.name:<32} {tts.SsmlVoiceGender(v.ssml_gender).name}")


def silent_wav(path, seconds):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(RATE)
        w.writeframes(b"\x00\x00" * int(seconds * RATE))


def duration(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--rate", type=float, default=1.0, help="speaking rate, 1.0 = normal")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--silent", action="store_true")
    a = ap.parse_args()
    if a.list:
        return list_voices()

    OUT.mkdir(parents=True, exist_ok=True)
    stamp_file = OUT / "stamps.json"
    stamps = json.loads(stamp_file.read_text()) if stamp_file.exists() else {}
    tts = c = None
    durations = {}
    for key, say, _ in LINES:
        path = OUT / f"{key}.wav"
        stamp = hashlib.sha1(f"{a.voice}|{a.rate}|{a.silent}|{say}".encode()).hexdigest()
        if not (path.exists() and stamps.get(key) == stamp):
            if a.silent:
                silent_wav(path, len(say.split()) / 2.6)
            else:
                if c is None:
                    tts, c = client()
                audio = c.synthesize_speech(
                    input=tts.SynthesisInput(text=say),
                    voice=tts.VoiceSelectionParams(language_code="en-IN", name=a.voice),
                    audio_config=tts.AudioConfig(audio_encoding=tts.AudioEncoding.LINEAR16,
                                                 sample_rate_hertz=RATE, speaking_rate=a.rate),
                ).audio_content
                path.write_bytes(audio)
            stamps[key] = stamp
            print(f"  synthesised {key}")
        durations[key] = round(duration(path), 2)
    stamp_file.write_text(json.dumps(stamps, indent=1))
    (OUT / "durations.json").write_text(json.dumps(durations, indent=1))
    print(f"{len(durations)} clips, {sum(durations.values()):.0f}s of narration -> {OUT}")


if __name__ == "__main__":
    main()
