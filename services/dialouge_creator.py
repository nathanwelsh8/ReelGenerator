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
    """Return system prompt with dynamic speaker names & images using actual names in output schema."""
    base = f"""# High level instructions

Your task is to read the provided document and produce a transcript that summarises and explains the document in detail.
The conversation should be between {s1_name} and {s2_name}. Any dialogue should be witty and in character.

# Instructions
1. Analyse the provided file to understand its contents
2. Determine the key takeaways and concepts that need to be explained
3. Generate a conversation between {s1_name.split()[0]} and {s2_name.split()[0]} in the required format which clearly explains the topic to a novice.
4. Check the dialogue to make sure it adheres to the dialogue rules

## Dialogue rules
1. The dialogue should start with an Opening hook. This can be either character posing an opening question or statement that drives the explanation.
2. One character (typically {s1_name.split()[0]}) should explain the topic in detail to the other as if they were a novice in that field. The explanation should be in depth and not surface level. The viewer should have enough knowledge to have a basic high level conversation afterwards. 
3. The other should optionally ask between one and three follow-up questions to explore key areas further if it improves clarity.
4. Each line must NOT be more than 99 characters. If a dialogue needs to run over 99 characters then split it over multiple consecutive dialogue entries so each is <= 99 characters. Prefer splitting at sentence boundaries.
5. End with a witty acknowledgement or thanks.
6. Use GenZ slang where appropriate but don't overdo it.
7. Open with a strong hook related to the central topic.

## Image rules
When {s1_name} is speaking, the image should be "{s1_image}"
When {s2_name} is speaking, the image should be "{s2_image}"
No other values are accepted for this field.

## Image search rules
The image should be as closely related to the dialogue as possible. 
For example if talking about a cat, "cat" is a good keyword.
For example if talking about OpenAI, "OpenAI" is a good keyword.
If talking about a specific concept, use that concept as the keyword.
If no image is needed, use an empty string.

## Character field rules
For each line, set the "character" field to the actual speaker's name exactly as given:
If the line corresponds to {s1_name} use value "{s1_name}"
If the line corresponds to {s2_name} use value "{s2_name}"
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
                            # character: model should return actual character name (we also accept legacy 'speaker1'/'speaker2')
                            "character": genai.types.Schema(type=genai.types.Type.STRING),
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
        s1n = (s1.get("name") or "").strip()
        s2n = (s2.get("name") or "").strip()
        s1n_low = s1n.lower()
        s2n_low = s2n.lower()
        for scene in scenes:
            val = (scene.get("character") or "").strip()
            low = val.lower()
            # Accept either explicit names or legacy placeholders
            if low in ("speaker1", s1n_low):
                scene["character"] = s1n
                if s1.get("id") is not None:
                    scene["character_id"] = s1.get("id")
                if not scene.get("image"):
                    scene["image"] = s1.get("image_path")
            elif low in ("speaker2", s2n_low):
                scene["character"] = s2n
                if s2.get("id") is not None:
                    scene["character_id"] = s2.get("id")
                if not scene.get("image"):
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
