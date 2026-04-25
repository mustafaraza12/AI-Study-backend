from openai import OpenAI
import os
from dotenv import load_dotenv
 
load_dotenv()
 
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)
 
VALID_MODES = {"beginner", "detailed", "summary", "linebyline"}
 
MODE_PROMPTS = {
    "beginner": (
        "You are a patient teacher explaining code to a complete beginner with no programming background. "
        "Use simple everyday language, avoid technical jargon, and use real-life analogies where helpful. "
        "Break it down into small easy steps. Do not use markdown symbols like ** or ##. "
        "Return only the explanation as clean plain text."
    ),
    "detailed": (
        "You are an expert software engineer. Provide a thorough, step-by-step explanation of the code. "
        "Cover what it does, how it works, the logic behind each major section, any algorithms used, "
        "edge cases, and potential improvements. Be precise and technical but clear. "
        "Do not use markdown symbols like ** or ##. Return only the explanation as clean plain text."
    ),
    "summary": (
        "You are a concise technical writer. Provide a single clear paragraph summarizing what this code does, "
        "its purpose, and how it achieves it. Keep it under 100 words. No bullet points, no lists. "
        "Do not use markdown symbols like ** or ##. Return only the plain text summary."
    ),
    "linebyline": (
        "You are a coding instructor. Explain this code line by line (or block by block for repetitive sections). "
        "For each line or logical block, clearly state what it does in plain English. "
        "Number each explanation to match the line or block. "
        "Do not use markdown symbols like ** or ##. Return only the clean numbered explanation."
    ),
}
 
 
def explain_code(code: str, language: str = None, mode: str = "detailed") -> str:
    try:
        mode = mode if mode in VALID_MODES else "detailed"
        system_prompt = MODE_PROMPTS[mode]
 
        lang_context = f"The code is written in {language}. " if language else ""
        user_message = f"{lang_context}Please explain the following code:\n\n{code}"
 
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.5,   # lower for factual accuracy
            max_tokens=2048,
        )
 
        return response.choices[0].message.content.strip()
 
    except Exception as e:
        print(f"Code Explainer Error [{mode}]:", e)
        return "Error explaining code"
 
        return "Error explaining code"
