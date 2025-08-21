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
                                description = "The line of dialogue spoken by the character. Never more than 99 characters",
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
3. Generate a conversation between Stewie and Peter in the required format which explains the topic
5. Check the dialogue to make sure it adheres to the dialogue rules

## Dialogue rules
1. The dialogue should start with a hook. This can be Stewie asking Peter an opening question on the topic/document or with peter making a hooking statement that causes stewie to ask for the explanation.
2. Peter should explain the topic in detail to Stewie as if they were a novice in that field.
3. Stewie should optionally ask between one and three follow-up questions to explore key areas further. Only do this if it benefits the explanation.
4. Each line must NOT be more than 99 characters. If a dialogue needs to run over 99 characters then split it over multiple consecutive dialogue entries in the output such that each does not exceed the 99-character limit. To help with this, you can put each sentence as a new dialogue for that character.
5. The dialogue should end with stewie thanking peter for explaining. It does not have to be verbatim and can be tongue-in-cheek or witty.
6. Use GenZ slang where appropriate. Reder to the GenZ definitions for words, what they mean and when to use them.
7. Open with a hook to grab the viewers attention. The hook should be related to the point of the article as all conversation from then on will explain the hook. See HookExamples 

### HookExamples.
1. Have you ever wondered what goes on behind the scenes of your favorite shows?
2. Imagine a world where your wildest dreams come true—what would it look like?
3. What if I told you that the key to success lies in your daily habits?
4. ChatGPT just made me Insanely rich, it can work for you too.
5. OpenAI just nerfed their largest model.
6. Heres how I released a 400 billion paramater model that can run on your laptop. 
                                 
### GenZ definitions
1. Glow Up
This means a makeover or transformation from bad to good.


2. CEO
If you’re the CEO of something, it means you’ve mastered it, or you’re a pro.

3. Fam
Fam is a shorter word for family, but don’t be fooled—it can be used to describe your friends or the way Millennials use “bro.”

4. Cancel Culture
Cancel culture is a form of shaming the actions or opinions of a public figure, company or organization. To use it would be "GPT5 just got cancelled. It did a bad thing"

5. Stan
No, it’s not short for Stanley. Instead, it’s a combination of “stalker” and “fan.” If you stan someone or something, it means you’re obsessed, but not in a creepy way.

6. E-boy or E-girl
This is similar to emo or goth culture, but they use the internet to express themselves.

7. W
To most, it’s just a letter of the alphabet, but to Gen Zers, it simply means “win.” "What a W"

8. Dank
If something is dank, it’s excellent or of very high quality.

9. Ghosting
This term is common in the earlier talking stages of a relationship. Ghosting someone means you start ignoring them or stop texting them back.

10. Salty
Gen Z uses this term when they’re feeling jealous.

11. Finna
Finna is a shorter way of saying, “I’m going to.”

12. Big Yikes
The slang speaks for itself in this one. Big Yikes is used when you’re so embarrassed that “yikes” doesn’t do justice.

13. Boujee
This term can be used if you’re describing something or someone that is extravagant or fancy.

14. Cap
An older but still relevant term, cap means to lie. If you say “no cap,” it means you are being authentic or truthful.

15. High-Key
High-key is simply the opposite of being low-key.

16. Cheugy
Something that is cheugy is not at all trendy.

17. Simp
Someone who does way too much for the person they have a crush on.

19. Woke
Woke refers to being politically aware.

20. TFW
TFW stands for “that feeling when.” TFW you get off work early on a Friday.

21. Snack
A snack is a person that you find attractive.

22. Sip Tea
Sip tea is an alternative to “spilling the tea,” meaning you’re sitting back and listening to the gossip rather than partaking in it.

23. L
Another simple letter-turned-slang, L is the opposite of a W—meaning a loss rather than a win. "What a fat L"

24. Take Several Seats
If someone is really getting on your nerves, you might tell them to take several seats.

25. Drip
Another way of saying swag, drip is a term for a cool or sexy trend/style.

26. Bop
When a song or album is exceptionally good.

27. Sheesh
Sheesh is used to hype someone up if they’re looking good or doing something good.

29. Living Rent-Free
If something is “living rent-free” in your head, that means you can’t stop thinking about it.

30. Bet
Simply put, this slang term means “yes.” It can be used to confirm something and could be compared to the Millennial term “word.”

31. Vibe Check
To check someone’s energy or mood.

32. Hits Different
When something is unique or better than the usual.

33. Periodt
Using this at the end of the statement adds emphasis or intensity to the point made.

34. Catch These Hands
To start a fight. This term is generally used in a contentious matter.

35. Drag
If you drag someone, you’re criticizing or making fun of them. This can be equated to roasting someone.

36. Finesse
Finesse means to trick or manipulate someone or a situation in order to get what you want.

37. I’m Weak
Similar to “I’m dead,” this is just another term to use when you find something hilarious.

38. Main Character
This is a phrase used to describe someone who is generally well-liked and charismatic. It can also be used to describe someone when they’re making a scene, but not necessarily in a bad way.

39. Sis
A shortened version of “sister,” this term is typically used to greet a friend, no matter their gender.

40. Sending Me
Another term to use if you find something particularly funny.

41. Slaps
Used to describe how exceptional something is. "GPT-5 fucking slaps"

42. Bussin’
A quirky word to use when you taste something delicious.

43. Sus
Short for “suspicious,” sus typically means something is not as expected, or shady.

44. Snatched
If someone is looking snatched, they look really good, particularly their outfit.

45. Guap
Money, and lots of it.

46. Smol
Something that is small and, in most cases, exceptionally adorable.

47. This Ain’t It, Chief
Another way of giving disapproval for something.

48. Extra
Someone who is out there and enjoys taking things to a new level of flamboyance.

49. Clapback
A response or comeback after you’ve been “called out” for something.

50. Goat.
Short for “The Greatest of All Time.” An acronym used to describe someone incredible.

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
