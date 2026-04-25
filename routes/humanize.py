from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

MODE_PROMPTS = {
    "standard": (
        "Rewrite the following AI-generated text to sound natural, human, and conversational. "
        "Keep the original meaning intact but make it feel like a real person wrote it. "
        "Vary sentence length, use natural transitions, and avoid robotic or overly formal phrasing. "
        "Do not add commentary — return only the rewritten text."
    ),
    "fluency": (
        "Rewrite the following AI-generated text to be exceptionally smooth and easy to read. "
        "Focus on flow, rhythm, and readability. Use clear transitions and well-paced sentences. "
        "The result should feel effortless to read from start to finish. "
        "Do not add commentary — return only the rewritten text."
    ),
    "formal": (
        "Rewrite the following AI-generated text in a professional and formal tone suitable for "
        "business reports, academic writing, or official communication. Maintain precision and clarity "
        "while removing any robotic or template-like AI patterns. "
        "Do not add commentary — return only the rewritten text."
    ),
    "simple": (
        "Rewrite the following AI-generated text using simple, everyday language that anyone can understand. "
        "Use short sentences, common words, and a friendly tone. Avoid jargon and complex structures. "
        "Make it feel approachable and easy to follow. "
        "Do not add commentary — return only the rewritten text."
    ),
    "creative": (
        "Rewrite the following AI-generated text in an expressive, vivid, and engaging style. "
        "Use creative word choices, varied sentence structures, and a distinctive voice. "
        "Make it feel alive and interesting to read while keeping the core meaning intact. "
        "Do not add commentary — return only the rewritten text."
    ),
}

DEFAULT_MODE = "standard"


def humanize_text(text: str, mode: str = DEFAULT_MODE) -> str:
    try:
        system_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS[DEFAULT_MODE])

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.85,       # slightly higher for more natural variation
            max_tokens=2048,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Humanizer Error [{mode}]:", e)
        return "Error humanizing text"", e)
        return "Error humanizing text"
