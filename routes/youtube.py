# routes/youtube.py

from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI
import os
import re
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


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


def get_transcript(video_id: str) -> str:
    print(f"[YouTube] Fetching transcript for: {video_id}")

    # ── New API: must instantiate the class first ──
    ytt = YouTubeTranscriptApi()

    try:
        fetched = ytt.fetch(video_id, languages=["en"])
        print("[YouTube] Got English transcript")
    except Exception as e1:
        print(f"[YouTube] English failed: {e1}")
        try:
            fetched = ytt.fetch(video_id, languages=["en-US", "en-GB", "en-IN", "hi"])
            print("[YouTube] Got fallback transcript")
        except Exception as e2:
            print(f"[YouTube] Fallback failed: {e2}")
            try:
                fetched = ytt.fetch(video_id)
                print("[YouTube] Got any-language transcript")
            except Exception as e3:
                raise Exception(f"No transcript available: {e3}")

    # New API returns FetchedTranscript — iterate snippets with .text
    text = " ".join(
        snippet.text.replace("\n", " ")
        for snippet in fetched
    )

    print(f"[YouTube] Transcript length: {len(text)} chars")

    if len(text) > 12000:
        text = text[:12000] + "...[transcript truncated]"

    return text


def explain_youtube(url: str) -> str:
    print(f"[YouTube] URL: {url}")

    video_id = get_video_id(url)
    print(f"[YouTube] Video ID: {video_id}")

    if not video_id:
        return "Invalid YouTube URL. Please check and try again."

    try:
        transcript = get_transcript(video_id)
    except Exception as e:
        print(f"[YouTube] Transcript Error: {type(e).__name__}: {e}")
        return f"Could not extract transcript: {str(e)}"

    try:
        prompt = f"""
Explain this YouTube lecture in a concise professional way for students.

Rules:
- Use headings
- Use bullet points
- Focus on key concepts
- Make it useful for exam revision

Lecture Transcript:
{transcript}
"""
        print("[YouTube] Sending to Groq...")

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You summarize YouTube lectures clearly and concisely for students."},
                {"role": "user",   "content": prompt}
            ]
        )

        print("[YouTube] Done.")
        return response.choices[0].message.content

    except Exception as e:
        print(f"[YouTube] Groq Error: {type(e).__name__}: {e}")
        return f"AI summarization failed: {str(e)}"