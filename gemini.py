"""One place to create the Gemini client and call it with a JSON schema."""

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

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


def generate_json(contents, schema):
    """Call Gemini with structured output and return the parsed JSON."""
    response = client().models.generate_content(
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    return json.loads(response.text)
