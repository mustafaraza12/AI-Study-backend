from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Create Groq client
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

def explain_slide_text(slide_text, language="Slides"):
    """
    Send a slide's text to Groq AI and get a professional explanation.
    Returns explanation in Markdown with headings and bullet points.
    """
    try:
        prompt = f"""
You are an expert AI teacher and slide explainer.
Explain the following slide text **professionally** in Markdown format:
- Use headings for sections
- Use bullet points for key points
- Bold key concepts
- Include an 'Output / Key Message' section if applicable

Slide content:
{slide_text}
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful AI that explains slides professionally."},
                {"role": "user", "content": prompt}
            ]
        )

        explanation = response.choices[0].message.content
        return explanation

    except Exception as e:
        print("AI ERROR:", e)
        return "Error explaining slide"