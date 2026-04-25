from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI
import os
import re
import json
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

MODEL = "llama-3.1-8b-instant"


def get_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
        r"(?:shorts\/)([0-9A-Za-z_-]{11})",
        r"(?:embed\/)([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


# ── TRANSCRIPT — no LLM, pure text extraction ───────────────────────────────

def fetch_transcript_only(url: str) -> dict:
    """
    Just extract the raw transcript text. No LLM involved.
    Returns in under 2 seconds.
    """
    video_id = get_video_id(url)
    if not video_id:
        return {"error": "Invalid YouTube URL."}

    try:
        ytt = YouTubeTranscriptApi()
        try:
            fetched = ytt.fetch(video_id, languages=["en"])
        except Exception:
            try:
                fetched = ytt.fetch(video_id, languages=["en-US", "en-GB", "en-IN", "hi"])
            except Exception:
                fetched = ytt.fetch(video_id)

        # Build plain text
        text = " ".join(s.text.replace("\n", " ") for s in fetched)

        # Build timestamped segments for better UX
        segments = [
            {
                "start": round(s.start),
                "text":  s.text.replace("\n", " ").strip()
            }
            for s in fetched
        ]

        print(f"[Transcript] Done — {len(text)} chars, {len(segments)} segments")
        return {
            "transcript": text,
            "segments":   segments,
            "word_count": len(text.split()),
            "video_id":   video_id,
        }

    except Exception as e:
        return {"error": f"Could not fetch transcript: {str(e)}"}


# ── ANALYSIS — LLM call, no transcript in output ────────────────────────────

def _smart_trim(transcript: str, max_chars: int = 12000) -> str:
    """
    Take beginning + middle + end so the LLM sees the full arc
    of the video without blowing token limits.
    """
    if len(transcript) <= max_chars:
        return transcript

    third         = max_chars // 3
    middle_start  = len(transcript) // 2 - third // 2

    beginning = transcript[:third]
    middle    = transcript[middle_start: middle_start + third]
    end       = transcript[-third:]

    return (
        beginning
        + "\n...[mid section]...\n"
        + middle
        + "\n...[end section]...\n"
        + end
    )


def _sanitize_json_string(text: str) -> str:
    result = []
    in_string  = False
    escape_next = False
    for char in text:
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        if char == "\\":
            result.append(char)
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            result.append(char)
            continue
        if in_string:
            if char == "\n":     result.append("\\n")
            elif char == "\r":   result.append("\\r")
            elif char == "\t":   result.append("\\t")
            elif ord(char) < 32: result.append(" ")
            else:                result.append(char)
        else:
            result.append(char)
    return "".join(result)


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$",          "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    for attempt in [cleaned, _sanitize_json_string(cleaned)]:
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            pass

    start = cleaned.find("{")
    end   = cleaned.rfind("}")
    if start != -1 and end != -1:
        substr = cleaned[start:end + 1]
        for attempt in [substr, _sanitize_json_string(substr)]:
            try:
                return json.loads(attempt)
            except json.JSONDecodeError:
                pass

    raise ValueError(f"Could not parse JSON. Preview: {text[:300]}")


def analyze_youtube(url: str) -> dict:
    """
    Single LLM call — returns summary, keypoints, mindmap,
    flashcards, quiz. No transcript in output (fetched separately).
    """
    video_id = get_video_id(url)
    if not video_id:
        return {"error": "Invalid YouTube URL."}

    # Step 1 — get transcript
    try:
        ytt = YouTubeTranscriptApi()
        try:
            fetched = ytt.fetch(video_id, languages=["en"])
        except Exception:
            try:
                fetched = ytt.fetch(video_id, languages=["en-US", "en-GB", "en-IN", "hi"])
            except Exception:
                fetched = ytt.fetch(video_id)

        full_text = " ".join(s.text.replace("\n", " ") for s in fetched)
        print(f"[Analyze] Transcript: {len(full_text)} chars")

    except Exception as e:
        return {"error": f"Could not fetch transcript: {str(e)}"}

    # Step 2 — smart trim for LLM (one call, no chunking)
    trimmed = _smart_trim(full_text, max_chars=6000)
    print(f"[Analyze] Trimmed to: {len(trimmed)} chars for LLM")

    # Step 3 — single LLM call
    prompt = f"""Analyze this YouTube video transcript and return ONLY a valid JSON object.
No markdown, no code fences, no extra text before or after.

{{
  "title": "video title or best guess",
  "channel": "channel name or Unknown",
  "duration": "estimated duration e.g. 15:00",
  "topic": "main topic in 5 words",
  "summary": "Thorough explanation for a student who has NOT watched the video. Cover every major concept, example, and explanation. Use section headings on separate lines followed by detailed paragraphs. Minimum 500 words.",
  "keypoints": [
    "Full sentence key point 1 with detail",
    "Full sentence key point 2",
    "Full sentence key point 3",
    "Full sentence key point 4",
    "Full sentence key point 5",
    "Full sentence key point 6",
    "Full sentence key point 7",
    "Full sentence key point 8"
  ],
  "mindmap": {{
    "center": "central theme",
    "branches": [
      {{"label": "Topic 1", "children": ["sub a", "sub b", "sub c"]}},
      {{"label": "Topic 2", "children": ["sub a", "sub b"]}},
      {{"label": "Topic 3", "children": ["sub a", "sub b", "sub c"]}},
      {{"label": "Topic 4", "children": ["sub a", "sub b"]}}
    ]
  }},
  "flashcards": [
    {{"front": "Specific question about this video?", "back": "Detailed answer from the video"}},
    {{"front": "Question 2?", "back": "Answer 2"}},
    {{"front": "Question 3?", "back": "Answer 3"}},
    {{"front": "Question 4?", "back": "Answer 4"}},
    {{"front": "Question 5?", "back": "Answer 5"}},
    {{"front": "Question 6?", "back": "Answer 6"}}
  ],
  "quiz": [
    {{"question": "MCQ 1?", "options": ["A", "B", "C", "D"], "answer": 0}},
    {{"question": "MCQ 2?", "options": ["A", "B", "C", "D"], "answer": 1}},
    {{"question": "MCQ 3?", "options": ["A", "B", "C", "D"], "answer": 2}},
    {{"question": "MCQ 4?", "options": ["A", "B", "C", "D"], "answer": 3}},
    {{"question": "MCQ 5?", "options": ["A", "B", "C", "D"], "answer": 0}}
  ]
}}

Rules:
- summary: minimum 500 words, section headings on their own lines
- keypoints: exactly 8 full informative sentences
- flashcards: exactly 6, specific to actual video content
- quiz: exactly 5, answer is zero-based index (0=A 1=B 2=C 3=D)
- mindmap: exactly 4 branches
- NO transcript field — it is fetched separately
- Return ONLY the JSON object, nothing else

Transcript:
{trimmed}"""

    try:
        print(f"[Analyze] Calling {MODEL}...")
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a JSON-only response engine. Return only a valid JSON object. No markdown, no code fences, no extra text."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content
        print(f"[Analyze] Response: {len(raw)} chars")
        return _extract_json(raw)

    except Exception as e:
        print(f"[Analyze] LLM error: {type(e).__name__}: {e}")
        return {"error": f"AI analysis failed: {str(e)}"}: {type(e).__name__}: {e}")
        return f"AI summarization failed: {str(e)}"
