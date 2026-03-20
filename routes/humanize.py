from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

def humanize_text(text):

    try:

        response = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[
                {
                    "role": "system",
                    "content": "Rewrite AI generated text to sound natural, human, and conversational."
                },
                {
                    "role": "user",
                    "content": text
                }
            ]

        )

        return response.choices[0].message.content

    except Exception as e:
        print("Humanizer Error:", e)
        return "Error humanizing text"