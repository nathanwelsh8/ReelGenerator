import base64
import os
import requests
import json
from google import genai
from google.genai import types
from settings import get_settings

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

def generate_from_pdf_content(pdf_content: bytes):
    """Generates dialogue from PDF content (bytes) and returns it as a JSON object."""
    if not pdf_content:
        return None
        

    key = settings.GEMINI_API_KEY

    client = genai.Client(
        api_key=key,
    )

    model = "gemini-2.5-pro"
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
            type = genai.types.Type.OBJECT,
            required = ["dialogue_scenes"],
            properties = {
                "dialogue_scenes": genai.types.Schema(
                    type = genai.types.Type.ARRAY,
                    description = "A list of scenes, each with a character, dialogue, and associated image.",
                    items = genai.types.Schema(
                        type = genai.types.Type.OBJECT,
                        required = ["image", "dialogue", "character", "image_search"],
                        properties = {
                            "image": genai.types.Schema(
                                type = genai.types.Type.STRING,
                                description = "The filename of the character's image (e.g., 'stewie.png').",
                            ),
                            "dialogue": genai.types.Schema(
                                type = genai.types.Type.STRING,
                                description = "The line of dialogue spoken by the character.",
                            ),
                            "character": genai.types.Schema(
                                type = genai.types.Type.STRING,
                                description = "The name of the character speaking the dialogue.",
                            ),
                            "image_search": genai.types.Schema(
                                type = genai.types.Type.STRING,
                                description = "A search query to find a relevant image for the scene. Can be an empty string if not applicable.",
                            ),
                        },
                    ),
                ),
            },
        ),
        system_instruction=[
            types.Part.from_text(text="""# High level instructions

Your task is to read the provided document and produce a transcript that summarises and explains the document in detail.
The conversation should be between Peter Griffin (Peter) and Stewie Griffin (Stewie) from Family Guy. Any dialogue should be witty and in character. 

# Instructions
1. Analyse the provided file to understand its contents
2. Determine the key takeaways
3. Generate a conversation between Stewie and Peter in the required format
5. Check the dialogue to make sure it adheres to the dialogue rules

## Dialogue rules
1. The dialogue should start with Stewie asking Peter an opening question on the topic/document
2. Peter should explain the topic in detail to Stewie as if they were a novice in that field.
3. Stewie should optionally ask between one and three follow-up questions to explore key areas further. Only do this if it benefits the explanation.
4. Each line must NOT be more than 100 characters. If a dialogue needs to run over 100 characters then split it over multiple consecutive dialogue entries in the output such that each does not exceed the 100-character limit. To help with this, you can put each sentence as a new dialogue for that character. 
5. The dialogue should end with stewie thanking peter for explaining. It does not have to be verbatim and can be tongue-in-cheek or witty. 

## image rules
When Peter is speaking, the image should be \"peter.png\"
When Stewie is speaking, the image should be \"stewie.png\"
No other values are accepted for this field

## image search rules
If the line of dialogue could benefit from an image to help the users understand, then supply a couple of basic keywords that can be used in a google image search to find relevant images.

For example if Peter was explaining nuclear fusion then suitable keywords would be \"nuclear fusion reactor\".

## Character rules
If the dialogue line corresponds to Peter then use value \"peter\"
If the dialogue line corresponds to Stewie then use value \"stewie\"
No other values are accepted

### Example output
The actual transcript you generate will be longer, this is just to show you how each field should be populated and that the same speaker can split their sentences up into multiple dialogues. Return only json output no additional text.

[{
    \"image\": \"stewie.png\",
    \"dialogue\": \"Peter, what's this I've been hearing about fine-tuning in LLMs?\",
    \"character\": \"stewie\",
    \"image_search\": \"\"
  },
  {
    \"image\": \"peter.png\",
    \"dialogue\": \"Heh heh heh. Alright, settle down, settle down.\",
    \"character\": \"peter\",
    \"image_search\": \"neural network\"
  },
{
    \"image\": \"peter.png\",
    \"dialogue\": \"You wanna know about \"fine-tuning\" one of them neural... net-thingies? \",
    \"character\": \"peter\",
    \"image_search\": \"neural network\"
  },
{ 
  \"image\": \"peter.png\",
  \"dialogue\": \"It's like this, see. It's actually a lot like beer. And I know beer.\",
  \"character\": \"peter\",
  \"image_search\": \"\"
},
{
  \"image\": \"peter.png\",
  \"dialogue\": \"Okay, so first, the nerds make this giant, freakin' smart computer brain\"
   \"character\": \"peter\",
   \"image_search\": \"smart computer\"
},
  {
    \"image\": \"stewie.png\",
    \"dialogue\": \"Ahh I see and how does this differ to the attention thingy?\",
    \"character\": \"stewie\",
    \"image_search\": \"\"
  }
]

Remember no dialogue can exceed 100 characters. If in doubt, split it over multiple dialogues.
"""),
        ],
    )
    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error during dialogue generation: {e}")
        return None

if __name__ == "__main__":
    # Example usage:
    # You can replace this with a PDF URL for testing
    pdf_url = "https://arxiv.org/pdf/1706.03762.pdf"
    pdf_bytes = fetch_pdf_from_url(pdf_url)
    if pdf_bytes:
        dialogue_data = generate_from_pdf_content(pdf_bytes)
        if dialogue_data:
            print(json.dumps(dialogue_data, indent=2))
