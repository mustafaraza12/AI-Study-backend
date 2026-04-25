from openai import OpenAI
import os
import re
import json
import base64
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

MODEL       = "llama-3.3-70b-versatile"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"  # Groq vision model

# ── OCR: Extract math from image using vision model ───────────────────────
def extract_text_from_image(file) -> str:
    try:
        if hasattr(file, "read"):
            image_bytes = file.read()
        else:
            image_bytes = file

        # Detect mime type from magic bytes
        if image_bytes[:4] == b'\x89PNG':
            mime = "image/png"
        elif image_bytes[:2] == b'\xff\xd8':
            mime = "image/jpeg"
        elif image_bytes[:4] == b'RIFF':
            mime = "image/webp"
        else:
            mime = "image/jpeg"

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime};base64,{b64}"

        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract every math problem or expression visible in this image. "
                                "Write each one on its own line using plain text math notation "
                                "(e.g. x^2, sqrt(x), fractions as a/b). "
                                "Do not solve anything. Do not add any explanation. "
                                "Output only the extracted math expressions, nothing else."
                            ),
                        },
                    ],
                }
            ],
            max_tokens=800,
            temperature=0.0,
        )

        extracted = response.choices[0].message.content.strip()
        return extracted

    except Exception as e:
        print(f"Vision OCR Error: {e}")
        return ""


# ── Solve math — LaTeX output for professional rendering ─────────────────
def solve_math(problem: str) -> dict:
    system_prompt = """You are an expert math tutor. Solve math problems with clear, concise step-by-step working.

STRICT RULES — follow every one:
1. Return ONLY valid JSON. Every value must be a properly quoted JSON string.
   WRONG:  "solution": with no quotes around the math
   RIGHT:  "solution": "\\(x^2\\)"
2. Write ALL math using LaTeX inside quoted strings: "\\(x^2\\)", "\\(\\frac{3}{4}\\)", "\\(\\sqrt{x}\\)"
   The backslashes must be doubled because this is inside a JSON string.
3. Keep steps SHORT — one action per step, no long sentences.
   Each step label: 2-4 words of plain English (e.g. "Apply power rule", "Combine terms").
4. Use 6 to 10 steps. Break every operation into its own step — do not skip or combine actions.
5. The "solution" field: final answer only in LaTeX string e.g. "\\(f'(x) = 3x^2 + 4x - 5\\)"
6. The "explanation" field: one plain English sentence, no LaTeX.
7. No markdown, no code fences, no text outside the JSON object.

Step format — each step has two parts:
  "label": short action name (2-4 words, plain English)
  "work": the math shown in LaTeX

JSON format:
{
  "solution": "\\(x = 3\\)",
  "steps": [
    { "label": "Set up equation", "work": "\\(2x + 5 = 11\\)" },
    { "label": "Subtract 5", "work": "\\(2x = 11 - 5 = 6\\)" },
    { "label": "Divide by 2", "work": "\\(x = \\frac{6}{2} = 3\\)" }
  ],
  "explanation": "Solved using basic algebraic operations."
}"""

    user_prompt = f"Solve this math problem step by step:\n\n{problem}"

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=2500,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if model ignores rules
        raw = re.sub(r"```json|```", "", raw).strip()

        # Extract JSON object robustly
        start = raw.find("{")
        end   = raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON object in AI response")

        json_str = raw[start:end + 1]

        # ── Fix single-backslash LaTeX delimiters ─────────────────────────
        # The model writes \( and \) with a single backslash, which is an
        # invalid JSON escape sequence. Fix them to \\\\ before parsing.
        # We only touch \( and \) — leave \\cdot, \\frac etc. alone.
        json_str = re.sub(r'(?<!\\)\\(?=[()])', r'\\\\', json_str)

        data = json.loads(json_str)

        # Validate and normalise steps
        # Accept both old format (list of strings) and new format (list of objects)
        raw_steps = data.get("steps", [])
        normalised = []
        for i, step in enumerate(raw_steps):
            if isinstance(step, dict):
                normalised.append({
                    "label": str(step.get("label", f"Step {i + 1}")),
                    "work":  str(step.get("work", "")),
                })
            else:
                # Fallback: plain string step — split on first colon if present
                text = str(step)
                if ":" in text:
                    parts = text.split(":", 1)
                    normalised.append({"label": parts[0].strip(), "work": parts[1].strip()})
                else:
                    normalised.append({"label": f"Step {i + 1}", "work": text})

        data["steps"]       = normalised
        data["solution"]    = str(data.get("solution", ""))
        data["explanation"] = str(data.get("explanation", ""))

        return {"success": True, "data": data}

    except json.JSONDecodeError as e:
        print(f"JSON Error: {e}\nRaw: {raw[:400]}")
        return {"success": False, "error": "AI returned an unreadable response. Please try again."}
    except Exception as e:
        print(f"Math Error: {e}")
        return {"success": False, "error": str(e)}


# ── Combined: OCR → solve ─────────────────────────────────────────────────
def solve_math_image(file) -> dict:
    if hasattr(file, "seek"):
        file.seek(0)

    extracted = extract_text_from_image(file)

    if not extracted.strip():
        return {
            "success": False,
            "error": "Could not extract text from the image. Make sure the image is clear with printed text.",
        }

    result = solve_math(extracted)

    if result.get("success"):
        result["extracted_text"] = extracted

    return result Image Solver Error: {e}")
        return f"Error solving image problem: {str(e)}"
