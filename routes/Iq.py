from openai import OpenAI
import os
import json
import re
import math
from dotenv import load_dotenv

load_dotenv()

# ── Groq client (same pattern as assignment.py) ────────────────────────────
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

MODEL = "llama-3.3-70b-versatile"

# ── Constants ──────────────────────────────────────────────────────────────
TIME_MAP = {
    "primary":      90,
    "middle":       75,
    "high":         60,
    "undergrad":    50,
    "postgrad":     45,
    "professional": 45,
}

EDUCATION_LABELS = {
    "primary":      "Primary School (Grade 1–5)",
    "middle":       "Middle School (Grade 6–8)",
    "high":         "High School (Grade 9–12)",
    "undergrad":    "Undergraduate (Bachelor's Level)",
    "postgrad":     "Postgraduate (Master's / PhD)",
    "professional": "Professional / Working Adult",
}


# ── Helper: call Groq LLM ──────────────────────────────────────────────────
def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    """Shared wrapper — mirrors the pattern in assignment.py."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        print("AI ERROR:", e)
        raise


def _strip_fences(text: str) -> str:
    """Remove accidental markdown code fences the model might add."""
    text = re.sub(r"^```json\s*", "", text.strip())
    text = re.sub(r"^```\s*",     "", text)
    text = re.sub(r"\s*```$",     "", text)
    return text.strip()


# ── Generate questions ─────────────────────────────────────────────────────
def generate_questions(name: str, age: int, education: str, subject: str, grade: str, count: int = 15):
    """
    Generate IQ test questions calibrated to the user's profile via Groq.
    Returns (questions_list, time_per_question_seconds).
    """
    edu_label  = EDUCATION_LABELS.get(education, education)
    subject_ln = f"with a background in {subject}" if subject else "with a general academic background"
    grade_ln   = f" (currently at {grade})" if grade else ""

    system_prompt = (
        "You are an expert psychometrician. "
        "You only respond with valid JSON arrays — no markdown, no explanation, no extra text."
    )

    user_prompt = f"""Generate exactly {count} IQ test questions for:
- Name: {name}
- Age: {age} years old
- Education Level: {edu_label}{grade_ln}
- Academic Background: {subject_ln}

Requirements:
1. Distribute questions evenly across these 5 cognitive categories (3 each for 15 total):
   - Logical Reasoning
   - Pattern Recognition
   - Numerical Reasoning
   - Verbal Reasoning
   - Spatial Reasoning

2. Difficulty distribution:
   - Easy: ~30%
   - Medium: ~50%
   - Hard: ~20%

3. Calibrate difficulty to the user's education level.

4. Each question MUST have exactly 4 answer options.

5. For {subject_ln}, include 3-4 domain-relevant logical/analytical questions
   (reasoning in that domain - NOT pure subject knowledge recall).

Return ONLY a valid JSON array in this exact format:
[
  {{
    "question": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_index": 0,
    "category": "Logical Reasoning",
    "difficulty": "Medium"
  }}
]

Rules:
- correct_index is 0-based (0=A, 1=B, 2=C, 3=D)
- category must be one of: Logical Reasoning, Pattern Recognition, Numerical Reasoning, Verbal Reasoning, Spatial Reasoning
- difficulty must be one of: Easy, Medium, Hard
- No trivia or factual recall - only reasoning and problem solving
"""

    raw       = _call_llm(system_prompt, user_prompt, max_tokens=4096)
    questions = json.loads(_strip_fences(raw))

    # Validate structure
    for i, q in enumerate(questions):
        assert "question"      in q,                            f"Q{i} missing 'question'"
        assert "options"       in q and len(q["options"]) == 4, f"Q{i} must have 4 options"
        assert "correct_index" in q and 0 <= q["correct_index"] <= 3, f"Q{i} bad correct_index"
        assert "category"      in q,                            f"Q{i} missing 'category'"
        assert "difficulty"    in q,                            f"Q{i} missing 'difficulty'"

    time_per_q = TIME_MAP.get(education, 60)
    return questions, time_per_q


# ── Evaluate answers ───────────────────────────────────────────────────────
def evaluate_answers(
    name: str, age: int, education: str, subject: str, grade: str,
    questions: list, answers: dict, timed_out: bool, time_taken: int
):
    """
    Score the test and return a full result dict the frontend expects.
    Uses Groq for the personalized AI analysis section.
    """
    edu_label = EDUCATION_LABELS.get(education, education)
    total     = len(questions)

    # ── Basic scoring ──────────────────────────────────────────────────────
    correct        = 0
    category_stats = {}  # { category: {correct, total} }

    for i, q in enumerate(questions):
        cat = q.get("category", "General")
        if cat not in category_stats:
            category_stats[cat] = {"correct": 0, "total": 0}
        category_stats[cat]["total"] += 1

        user_ans = answers.get(str(i))
        if user_ans is not None and int(user_ans) == q["correct_index"]:
            correct += 1
            category_stats[cat]["correct"] += 1

    accuracy = round((correct / total) * 100) if total else 0

    # ── Difficulty-weighted score for IQ estimation ────────────────────────
    difficulty_weights = {"Easy": 1.0, "Medium": 1.5, "Hard": 2.0}
    weighted_score = 0.0
    weighted_total = 0.0

    for i, q in enumerate(questions):
        w = difficulty_weights.get(q.get("difficulty", "Medium"), 1.5)
        weighted_total += w
        user_ans = answers.get(str(i))
        if user_ans is not None and int(user_ans) == q["correct_index"]:
            weighted_score += w

    weighted_pct = weighted_score / weighted_total if weighted_total else 0

    # ── IQ estimation ──────────────────────────────────────────────────────
    edu_baseline = {
        "primary":      88,
        "middle":       93,
        "high":         98,
        "undergrad":    103,
        "postgrad":     108,
        "professional": 105,
    }
    baseline      = edu_baseline.get(education, 100)
    raw_iq        = baseline - 30 + (weighted_pct * 75)
    time_allotted = TIME_MAP.get(education, 60) * total
    time_ratio    = time_taken / time_allotted if time_allotted else 1

    if not timed_out and time_ratio < 0.7:
        raw_iq += 3   # finished quickly
    elif timed_out:
        raw_iq -= 2   # ran out of time

    iq_score   = max(55, min(160, round(raw_iq)))
    percentile = iq_to_percentile(iq_score)

    # ── Category breakdown for frontend ───────────────────────────────────
    breakdown = []
    for cat, stats in category_stats.items():
        score_pct = round((stats["correct"] / stats["total"]) * 100) if stats["total"] else 0
        breakdown.append({
            "name":    cat,
            "score":   score_pct,
            "correct": stats["correct"],
            "total":   stats["total"],
        })
    breakdown.sort(key=lambda x: x["score"], reverse=True)

    # ── Build per-question summary for AI ─────────────────────────────────
    q_summary = []
    for i, q in enumerate(questions):
        user_ans = answers.get(str(i))
        q_summary.append({
            "category":   q["category"],
            "difficulty": q["difficulty"],
            "correct":    (user_ans is not None and int(user_ans) == q["correct_index"]),
            "skipped":    user_ans is None,
        })

    # ── AI analysis via Groq ───────────────────────────────────────────────
    system_prompt = (
        "You are an expert cognitive psychologist providing brief, personalized, encouraging test feedback. "
        "You only respond with valid JSON objects — no markdown, no extra text."
    )

    analysis_prompt = f"""Analyze this IQ test result and provide personalized insights.

Test taker: {name}, age {age}, {edu_label}
{f"Background: {subject}" if subject else ""}
Score: {correct}/{total} correct ({accuracy}%)
Estimated IQ band: {iq_band_label(iq_score)}
Timed out: {timed_out}
Time taken: {time_taken}s of {time_allotted}s allotted

Category performance:
{json.dumps(category_stats, indent=2)}

Question summary:
{json.dumps(q_summary, indent=2)}

Respond ONLY with this JSON structure:
{{
  "analysis": "2-3 sentences of warm, professional, personalized cognitive insight mentioning strongest and weakest categories",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "improvements": ["actionable tip 1", "actionable tip 2", "actionable tip 3"]
}}

Rules:
- Do NOT mention the numeric IQ score in the analysis text
- strengths: specific cognitive abilities demonstrated
- improvements: concrete, actionable next steps
"""

    try:
        ai_raw  = _call_llm(system_prompt, analysis_prompt, max_tokens=800)
        ai_data = json.loads(_strip_fences(ai_raw))
    except Exception as e:
        print("Analysis AI ERROR:", e)
        ai_data = {
            "analysis":     "Your results show a diverse cognitive profile across multiple reasoning domains.",
            "strengths":    ["Completed the assessment", "Demonstrated reasoning ability", "Engaged with varied question types"],
            "improvements": ["Practice logical puzzles daily", "Work on pattern recognition exercises", "Review numerical reasoning techniques"],
        }

    return {
        "iq_score":     iq_score,
        "percentile":   percentile,
        "correct":      correct,
        "accuracy":     accuracy,
        "time_taken":   time_taken,
        "breakdown":    breakdown,
        "analysis":     ai_data.get("analysis", ""),
        "strengths":    ai_data.get("strengths", []),
        "improvements": ai_data.get("improvements", []),
    }


# ── Helpers ────────────────────────────────────────────────────────────────
def iq_to_percentile(iq: int) -> int:
    """Approximate percentile from IQ (normal distribution, mean=100, sd=15)."""
    z   = (iq - 100) / 15
    phi = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return max(1, min(99, round(phi * 100)))


def iq_band_label(score: int) -> str:
    if score >= 145: return "Genius"
    if score >= 130: return "Highly Gifted"
    if score >= 120: return "Superior"
    if score >= 110: return "High Average"
    if score >= 90:  return "Average"
    if score >= 80:  return "Low Average"
    if score >= 70:  return "Borderline"
    return "Below Average"
