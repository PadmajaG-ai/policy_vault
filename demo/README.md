# Demo video

Builds a 3–4 minute narrated demo by driving the real app with Playwright as a demo user
(Priya, new system admin), with an Indian English female voice-over from Google Cloud Text-to-Speech.

```powershell
pip install --use-feature=truststore -r requirements-dev.txt
python -m playwright install chromium
gcloud services enable texttospeech.googleapis.com

python demo/voice.py                 # narration clips (en-IN female voice); --list shows other voices
python main.py                       # in a second terminal (or use --url with the Cloud Run link)
python demo/record.py --show         # drives the app and records the screen
python demo/assemble.py              # -> demo/out/policy_vault_demo.mp4
```

- Narration lives in `demo/script.py`. Edit a line, re-run `voice.py` (only changed lines are re-synthesised), then record + assemble.
- Every result on screen is live: real Gemini calls, real comparisons. Only idle waiting with no narration is trimmed, and the video shows a "waiting time shortened" note while a live call runs.
- `python demo/voice.py --silent` makes silent clips timed by word count, for a dry run without the TTS API.
- Video quality: `record.py` captures Chrome's own rendered frames at 2560x1440 (2x pixel density, sharp text)
  and `assemble.py` encodes H.264 at CRF 16. Uploading 1440p makes YouTube use its higher-quality encode.
  `--lowres` falls back to Playwright's built-in 720p recorder. Frames need about 1 GB of free disk space.
