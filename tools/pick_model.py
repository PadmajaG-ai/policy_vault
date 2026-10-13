import re
from google import genai

client = genai.Client(vertexai=True, project="policy-vault-510216", location="global")

SKIP = ("preview", "exp", "lite", "image", "live", "audio", "tts", "embedding", "latest")
candidates = []
for m in client.models.list():
    name = m.name.split("/")[-1]
    if "flash" in name and not any(s in name for s in SKIP):
        version = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
        if version:
            candidates.append((float(version.group(1)), name))

candidates.sort(reverse=True)
print("Stable Flash models found:", [n for _, n in candidates])

for _, name in candidates:
    try:
        reply = client.models.generate_content(model=name, contents="Reply with just OK").text
        print(f"\nUSE THIS: {name}  (test reply: {reply.strip()})")
        break
    except Exception as e:
        print(f"{name} not usable here: {str(e)[:120]}")