from openai import OpenAI
import os
import json
import re
import PyPDF2
import docx
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


def extract_text_from_file(file, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    text = ""
    if ext == "pdf":
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    elif ext in ("doc", "docx"):
        document = docx.Document(file)
        for para in document.paragraphs:
            text += para.text + "\n"
    elif ext == "txt":
        text = file.read().decode("utf-8", errors="ignore")
    return text.strip()


def generate_flashcards(text: str, card_count: int = 10, subject: str = "") -> list:
    subject_line = f"Subject: {subject}\n" if subject else ""

    prompt = f"""
You are an expert study assistant. Generate exactly {card_count} flashcards from the content below.

{subject_line}

STRICT RULES:
- Return ONLY a valid JSON array — no extra text, no markdown, no explanation
- Each object must have exactly two keys: "question" and "answer"
- Questions should test key concepts, definitions, or facts
- Answers should be concise but complete (1-3 sentences max)
- Make questions clear and specific
- Do NOT number the questions

Example format:
[
  {{"question": "What is photosynthesis?", "answer": "The process by which plants convert sunlight into food using CO2 and water."}},
  {{"question": "What organelle performs photosynthesis?", "answer": "The chloroplast."}}
]

Content:
{text[:8000]}

Return ONLY the JSON array:
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a flashcard generator. You only return valid JSON arrays. Never add any text before or after the JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=4000,
    )

    raw = response.choices[0].message.content.strip()
    print(f"[Flashcard] Raw response: {raw[:200]}")

    # Clean up common issues
    raw = re.sub(r"```json|```", "", raw).strip()

    # Extract JSON array
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    flashcards = json.loads(raw)

    # Validate structure
    validated = []
    for card in flashcards:
        if isinstance(card, dict) and "question" in card and "answer" in card:
            validated.append({
                "question": str(card["question"]).strip(),
                "answer":   str(card["answer"]).strip(),
            })

    return validated
    return validated
