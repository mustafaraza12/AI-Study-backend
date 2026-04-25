from openai import OpenAI
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

DIFFICULTY_INSTRUCTIONS = {
    "easy":   "Use simple vocabulary and straightforward factual recall questions. Suitable for beginners.",
    "medium": "Mix factual recall with some application and understanding questions. Moderate complexity.",
    "hard":   "Focus on deep understanding, analysis, and tricky edge cases. Suitable for advanced learners.",
}

def generate_quiz(text, num_question, difficulty="medium", quiz_type="mcq"):
    """
    Generate a quiz from the given text.

    Parameters:
    - text         : topic or content to quiz on
    - num_question : number of questions to generate
    - difficulty   : "easy" | "medium" | "hard"
    - quiz_type    : "mcq" | "truefalse" | "mixed"
    """
    difficulty     = difficulty if difficulty in DIFFICULTY_INSTRUCTIONS else "medium"
    difficulty_tip = DIFFICULTY_INSTRUCTIONS[difficulty]

    # ── Build type-specific instructions ────────────────────────────────────
    if quiz_type == "truefalse":
        type_instruction = (
            'Each question must be a True/False question. '
            'The "options" array must always be exactly ["True", "False"]. '
            'The "answer" must be either "True" or "False".'
        )
    elif quiz_type == "mixed":
        type_instruction = (
            f'Mix the question types: roughly half should be standard multiple choice '
            f'with 4 options (A-D), and the other half should be True/False with options '
            f'["True", "False"]. Set "type" field to "mcq" or "truefalse" accordingly.'
        )
    else:  # default mcq
        type_instruction = (
            'Each question must have exactly 4 answer options. '
            'The "answer" must be the exact text of the correct option.'
        )

    prompt = f"""
Create exactly {num_question} quiz questions about the topic below.

Difficulty: {difficulty.upper()} — {difficulty_tip}

Question type rules:
{type_instruction}

STRICT OUTPUT RULES:
- Return ONLY a valid JSON array — no markdown, no explanation, no extra text.
- Always generate EXACTLY {num_question} questions.
- Each object MUST have these fields:
  - "question"    : the question text
  - "options"     : array of answer choices
  - "answer"      : exact text of the correct option
  - "explanation" : 1-2 sentence explanation of WHY the answer is correct
  - "difficulty"  : "{difficulty}"
  - "type"        : "mcq" or "truefalse"

Example format:
[
  {{
    "question": "What is the powerhouse of the cell?",
    "options": ["Nucleus", "Mitochondria", "Ribosome", "Golgi apparatus"],
    "answer": "Mitochondria",
    "explanation": "Mitochondria produce ATP through cellular respiration, earning them the nickname 'powerhouse of the cell'.",
    "difficulty": "{difficulty}",
    "type": "mcq"
  }}
]

Topic:
{text}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=8000,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert quiz creator. "
                        "Always return only a valid JSON array with no extra text, "
                        "no markdown fences, and no preamble."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )

        raw = response.choices[0].message.content.strip()
        print("Raw quiz output:", raw[:300])

        # Strip markdown code fences if model ignores instructions
        raw = re.sub(r"```json|```", "", raw).strip()

        # Extract JSON array robustly
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            raw = match.group(0)

        quiz_list = json.loads(raw)

        validated = []
        for q in quiz_list:
            if "question" in q and "options" in q and "answer" in q:
                validated.append({
                    "question":    str(q.get("question", "")).strip(),
                    "options":     [str(o).strip() for o in q.get("options", [])],
                    "answer":      str(q.get("answer", "")).strip(),
                    "explanation": str(q.get("explanation", "")).strip(),
                    "difficulty":  str(q.get("difficulty", difficulty)).strip(),
                    "type":        str(q.get("type", "mcq")).strip(),
                })

        print(f"Generated {len(validated)} questions (type={quiz_type}, difficulty={difficulty})")
        return validated

    except json.JSONDecodeError as e:
        print("JSON Parse Error:", e)
        print("Raw output was:", raw[:500])
        return []

    except Exception as e:
        print("Quiz Error:", e)
        return []
        return []
