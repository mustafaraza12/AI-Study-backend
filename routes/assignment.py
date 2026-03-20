from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Create Groq client
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

def solve_assignment(question):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI that solves student assignments and explains answers clearly."
                },
                {
                    "role": "user",
                    "content": question
                }
            ]
        )

        answer = response.choices[0].message.content
        return answer

    except Exception as e:
        print("AI ERROR:", e)
        return "Error solving assignment"