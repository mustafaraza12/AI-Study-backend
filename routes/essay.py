# routes/essay.py

from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


def write_essay(topic: str, essay_type: str, tone: str, word_count: int, language: str) -> str:
    try:
        type_instructions = {
            "argumentative":    "Write an argumentative essay that takes a clear stance and defends it with strong evidence and logical reasoning.",
            "descriptive":      "Write a descriptive essay that uses vivid sensory details to paint a clear picture for the reader.",
            "expository":       "Write an expository essay that clearly explains the topic using facts, examples, and analysis.",
            "persuasive":       "Write a persuasive essay that convinces the reader using emotional appeal, logic, and credible evidence.",
            "compare_contrast": "Write a compare and contrast essay that analyzes the similarities and differences between key aspects of the topic.",
            "narrative":        "Write a narrative essay that tells an engaging story related to the topic with a clear beginning, middle, and end.",
        }

        type_instruction = type_instructions.get(
            essay_type,
            "Write a well-structured essay on the given topic."
        )

        prompt = f"""
You are an expert academic writer. Write a {tone.lower()} {essay_type.replace('_', ' ')} essay in {language}.

Topic: {topic}

Instructions:
- {type_instruction}
- Target length: approximately {word_count} words
- Tone: {tone}
- Language: {language}
- Use clear headings for each section (Introduction, Body paragraphs, Conclusion)
- Write in proper paragraphs with smooth transitions
- Make it engaging and well-structured
- Do NOT include any meta-commentary like "Here is your essay" — just write the essay directly

Structure to follow:
## [Essay Title]

### Introduction
[Hook + background + thesis statement]

### [Body Section 1 Title]
[Main argument/point with evidence]

### [Body Section 2 Title]
[Second argument/point with evidence]

### [Body Section 3 Title] (if word count allows)
[Third argument/point]

### Conclusion
[Restate thesis + summarize key points + closing thought]
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": f"You are an expert {tone.lower()} academic writer. Write essays directly without any preamble or meta-commentary."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=4000,
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"Essay Writer Error: {e}")
        return f"Error writing essay: {str(e)}"