# routes/quiz.py
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

def generate_quiz(text, num_question):
    try:
        prompt = f"""
Create {num_question} multiple choice questions about the topic below.

IMPORTANT:
- Always generate EXACTLY {num_question} questions.
- Each question must have 4 options.
- Return ONLY valid JSON array — no markdown, no explanation, no extra text.
- Do not reduce the number of questions.

Format:
[
  {{
    "question": "Question text",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Correct option text"
  }}
]

Topic:
{text}
"""
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=5000,
            messages=[
                {"role": "system", "content": "You are a helpful AI that creates educational quizzes. Always return only valid JSON arrays with no extra text."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.5
        )

        raw = response.choices[0].message.content.strip()
        print("Raw quiz output:", raw[:300])

        # Strip markdown code blocks if present
        raw = re.sub(r"```json|```", "", raw).strip()

        # Extract JSON array
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            raw = match.group(0)

        # Parse string → list
        quiz_list = json.loads(raw)

        # Validate each question has required fields
        validated = []
        for q in quiz_list:
            if "question" in q and "options" in q and "answer" in q:
                validated.append({
                    "question": str(q["question"]).strip(),
                    "options":  [str(o).strip() for o in q["options"]],
                    "answer":   str(q["answer"]).strip(),
                })

        print(f"Generated {len(validated)} questions")
        return validated

    except json.JSONDecodeError as e:
        print("JSON Parse Error:", e)
        print("Raw output was:", raw[:500])
        return []

    except Exception as e:
        print("Quiz Error:", e)
        return []