"""One place to create the Gemini client and call it (with retry on rate limits)."""

import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

_client = None


def client():
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=os.environ.get("GEMINI_LOCATION", "global"),
        )
    return _client


def generate_with_retry(**kwargs):
    """Call Gemini, waiting and retrying when rate limited (HTTP 429)."""
    kwargs.setdefault("model", MODEL)
    delay = 5
    for attempt in range(5):
        try:
            return client().models.generate_content(**kwargs)
        except errors.ClientError as e:
            if e.code != 429 or attempt == 4:
                raise
            print(f"Rate limited, waiting {delay}s...")
            time.sleep(delay)
            delay *= 2  # 5, 10, 20, 40 seconds


def generate_json(contents, schema):
    """Call Gemini with structured output and return the parsed JSON."""
    response = generate_with_retry(
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    return json.loads(response.text)
