from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Create Groq client (same as assignment solver)
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

def explain_code(code, language="Python"):
    """
    Explain a piece of code using Groq API.

    Args:
        code (str): The code snippet to explain.
        language (str): Programming language (default Python)

    Returns:
        str: Step-by-step explanation of the code
    """
    try:
        prompt = f"""
You are an expert {language} developer and teacher.
Explain the following {language} code in simple terms, step by step.
Include:
- What each part does
- Output if the code runs
- Any potential issues

Code:
{code}
"""
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # same model you use in assignments
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI that explains code clearly and thoroughly."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        explanation = response.choices[0].message.content
        return explanation

    except Exception as e:
        print("AI ERROR:", e)
        return "Error explaining code"