import base64
import os
import requests
import json
from typing import Optional, Dict
from google import genai
from google.genai import types
from settings import get_settings
from services.character_service import CharacterService

settings = get_settings()

def fetch_pdf_from_url(url: str) -> bytes:
    """Fetches a PDF from a URL and returns its content as bytes."""
    if not url or not url.startswith('http'):
        print(f"Invalid URL provided: {url}")
        return None
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PDF from URL {url}: {e}")
        return None

def _build_system_instruction(s1_name: str, s2_name: str, s1_image: str, s2_image: str) -> str:
    """Return system prompt with dynamic speaker names & images replacing hard-coded Peter/Stewie."""
    # Use lowercase short tokens speaker1/speaker2 in output schema
    base = f"""# High level instructions

Your task is to read the provided document and produce a transcript that summarises and explains the document in detail.
The conversation should be between {s1_name} (speaker1) and {s2_name} (speaker2) from Family Guy. Any dialogue should be witty and in character.

# Instructions
1. Analyse the provided file to understand its contents
2. Determine the key takeaways
3. Generate a conversation between {s1_name.split()[0]} and {s2_name.split()[0]} in the required format which explains the topic
5. Check the dialogue to make sure it adheres to the dialogue rules

## Dialogue rules
1. The dialogue should start with a hook. This can be either character posing an opening question or statement that drives the explanation.
2. One character (typically {s1_name.split()[0]}) should explain the topic in detail to the other as if they were a novice in that field.
3. The other should optionally ask between one and three follow-up questions to explore key areas further if it improves clarity.
4. Each line must NOT be more than 99 characters. If a dialogue needs to run over 99 characters then split it over multiple consecutive dialogue entries so each is <= 99 characters. Prefer splitting at sentence boundaries.
5. End with a witty acknowledgement or thanks.
6. Use GenZ slang where appropriate (see definitions) but don't overdo it.
7. Open with a strong hook related to the central topic.

## Image rules
When speaker1 is speaking, the image should be "{s1_image}"
When speaker2 is speaking, the image should be "{s2_image}"
No other values are accepted for this field.

## Image search rules
If the line of dialogue could benefit from an illustrative image, provide 1-4 short keywords. Otherwise empty string.

## Character field rules
If the line corresponds to {s1_name} use value "speaker1"
If the line corresponds to {s2_name} use value "speaker2"
No other values are accepted.

Return ONLY JSON matching the response schema. No extra commentary.
Remember no dialogue can exceed 99 characters.
"""
    # Append existing GenZ slang section by slicing original (reuse from file if needed but here simplified)
    return base


def generate_from_pdf_content(pdf_content: bytes, speaker_context: Optional[Dict] = None):
    """Generates dialogue from PDF content (bytes) using dynamic speakers.

    speaker_context: {"speaker1": {name,image_path}, "speaker2": {...}}
    Falls back to Peter/Stewie seed if not provided.
    """
    if not pdf_content:
        return None

    char_service = CharacterService()
    if not speaker_context:
        # fallback to first two active
        chars = char_service.list_active_characters()[:2]
        if len(chars) < 2:
            print("Not enough characters to generate dialogue")
            return None
        speaker_context = {"speaker1": chars[0], "speaker2": chars[1]}

    s1 = speaker_context.get("speaker1")
    s2 = speaker_context.get("speaker2")
    if not (s1 and s2):
        print("Invalid speaker context provided")
        return None

    key = settings.GEMINI_API_KEY

    client = genai.Client(api_key=key)

    model = "gemini-2.5-pro"
    system_instruction_text = _build_system_instruction(
        s1.get("name", "Speaker One"),
        s2.get("name", "Speaker Two"),
        s1.get("image_path", "speaker1.png"),
        s2.get("image_path", "speaker2.png"),
    )

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(mime_type="application/pdf", data=pdf_content),
            ],
        ),
    ]

    generate_content_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=genai.types.Schema(
            type=genai.types.Type.OBJECT,
            required=["dialogue_scenes"],
            properties={
                "dialogue_scenes": genai.types.Schema(
                    type=genai.types.Type.ARRAY,
                    description="A list of scenes, each with a character key, dialogue, image, and search query.",
                    items=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        required=["image", "dialogue", "character", "image_search"],
                        properties={
                            "image": genai.types.Schema(type=genai.types.Type.STRING),
                            "dialogue": genai.types.Schema(type=genai.types.Type.STRING),
                            "character": genai.types.Schema(type=genai.types.Type.STRING),  # expects "speaker1" / "speaker2"
                            "image_search": genai.types.Schema(type=genai.types.Type.STRING),
                        },
                    ),
                ),
            },
        ),
        system_instruction=[types.Part.from_text(text=system_instruction_text)],
    )
    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        data = json.loads(response.text)
        scenes = data.get("dialogue_scenes", [])
        for scene in scenes:
            keyc = scene.get("character")
            if keyc == "speaker1":
                scene["character_name"] = s1.get("name")
                scene["image"] = s1.get("image_path")
            elif keyc == "speaker2":
                scene["character_name"] = s2.get("name")
                scene["image"] = s2.get("image_path")
        return data
    except Exception as e:
        print(f"Error during dialogue generation: {e}")
        return None

if __name__ == "__main__":
    pdf_url = "https://arxiv.org/pdf/1706.03762.pdf"
    pdf_bytes = fetch_pdf_from_url(pdf_url)
    if pdf_bytes:
        cs = CharacterService()
        chars = cs.list_active_characters()[:2]
        speaker_ctx = {"speaker1": chars[0], "speaker2": chars[1]} if len(chars) >= 2 else None
        dialogue_data = generate_from_pdf_content(pdf_bytes, speaker_context=speaker_ctx)
        if dialogue_data:
            print(json.dumps(dialogue_data, indent=2))
