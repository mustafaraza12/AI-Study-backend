# routes/math_solver.py

from openai import OpenAI
import os
import base64
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

MATH_PROMPT = """You are an expert math tutor. Solve the given problem using EXACTLY this structure:

## 📌 Problem
Restate the problem clearly.

## 🔍 Approach
Briefly explain which method or formula you will use.

## 📝 Step-by-Step Solution
### Step 1: [Title]
Show the work clearly.

### Step 2: [Title]
Continue the solution.

### Step 3: [Title]
...and so on until solved.

## ✅ Final Answer
State the final answer clearly and boldly.

## 💡 Key Concept
Explain the concept behind this problem in 2-3 sentences for exam understanding.

RULES:
- Always show every step clearly
- Use ** ** for important values and formulas
- Never skip steps
- Keep explanations student-friendly
"""


def solve_math(problem: str) -> str:
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": MATH_PROMPT},
                {"role": "user", "content": f"Solve this math problem:\n{problem}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Math Solver Error: {e}")
        return f"Error solving problem: {str(e)}"


def solve_math_image(file) -> str:
    try:
        # Read and encode image to base64
        image_data = base64.b64encode(file.read()).decode("utf-8")
        mime_type  = file.content_type or "image/jpeg"

        # Groq supports vision with llama-3.2-90b-vision
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": f"{MATH_PROMPT}\n\nSolve the math problem shown in this image."
                        }
                    ]
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Math Image Solver Error: {e}")
        return f"Error solving image problem: {str(e)}"