from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# ── Groq client (same pattern as assignment.py / iq.py) ───────────────────
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

MODEL = "llama-3.3-70b-versatile"

# ── Document type → friendly label map ────────────────────────────────────
DOC_LABELS = {
    # Applications
    "school_admission":     "School Admission Application",
    "college_admission":    "College Admission Application",
    "university_admission": "University Admission Application",
    "scholarship":          "Scholarship Application",
    "job_application":      "Job Application Letter",
    "internship":           "Internship Application Letter",
    "leave_application":    "Leave Application",
    "fee_concession":       "Fee Concession Application",
    "hostel":               "Hostel Application",
    "transfer":             "Transfer Certificate Application",
    # Formal Letters
    "complaint_letter":     "Formal Complaint Letter",
    "request_letter":       "Formal Request Letter",
    "recommendation":       "Recommendation Letter",
    "resignation":          "Resignation Letter",
    "appreciation":         "Appreciation Letter",
    "apology_letter":       "Formal Apology Letter",
    "permission_letter":    "Permission Letter",
    "noc":                  "No Objection Certificate (NOC)",
    "experience_letter":    "Experience Letter",
    "reference_letter":     "Reference Letter",
    # Emails
    "email_professor":      "Formal Email to Professor",
    "email_hr":             "Formal Email to HR / Manager",
    "email_complaint":      "Complaint Email",
    "email_followup":       "Follow-up Email",
    "email_inquiry":        "Inquiry Email",
    "email_apology":        "Apology Email",
    "email_resignation":    "Resignation Email",
    "email_thank_you":      "Thank You Email",
    # Reports
    "progress_report":      "Progress Report",
    "incident_report":      "Incident Report",
    "project_report":       "Project Report",
    "lab_report":           "Lab / Practical Report",
    "internship_report":    "Internship Report",
    "field_visit_report":   "Field Visit Report",
}

# ── Tone instructions ──────────────────────────────────────────────────────
TONE_INSTRUCTIONS = {
    "formal":     "Use a strictly formal, professional tone throughout. Avoid contractions and casual language.",
    "polite":     "Use a warm, polite, and courteous tone. Be respectful and considerate.",
    "humble":     "Use a modest, humble, and sincere tone. Show gratitude and deference where appropriate.",
    "confident":  "Use a confident, assertive, and direct tone. Be clear and decisive without being rude.",
    "urgent":     "Use an urgent, time-sensitive tone. Clearly convey the pressing nature of the matter.",
}


def generate_letter(
    doc_type: str,
    tone: str,
    subject: str,
    sender_name: str = "",
    sender_title: str = "",
    sender_org: str = "",
    sender_addr: str = "",
    recipient_name: str = "",
    recipient_title: str = "",
    recipient_org: str = "",
    recipient_addr: str = "",
    extra_details: str = "",
) -> str:

    doc_label  = DOC_LABELS.get(doc_type, doc_type.replace("_", " ").title())
    tone_instr = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["formal"])

    # ✅ Detect student vs office
    student_types = [
        "school_admission", "college_admission", "university_admission",
        "leave_application", "fee_concession", "scholarship", "hostel"
    ]

    is_student = doc_type in student_types

    salutation = "Respected Sir" if is_student else "Dear Sir"
    closing    = "Yours obediently" if is_student else "Yours sincerely"

    # ── Sender / Recipient Blocks ─────────────────────────────
    sender_block = "\n".join(filter(None, [
        f"Sender Name      : {sender_name}"    if sender_name    else "",
        f"Sender Title     : {sender_title}"   if sender_title   else "",
        f"Sender Org       : {sender_org}"     if sender_org     else "",
        f"Sender Address   : {sender_addr}"    if sender_addr    else "",
    ])) or "Not provided"

    recipient_block = "\n".join(filter(None, [
        f"Recipient Name   : {recipient_name}"   if recipient_name   else "",
        f"Recipient Title  : {recipient_title}"  if recipient_title  else "",
        f"Recipient Org    : {recipient_org}"    if recipient_org    else "",
        f"Recipient Address: {recipient_addr}"   if recipient_addr   else "",
    ])) or "Not provided"

    # ── SYSTEM PROMPT ────────────────────────────────────────
    system_prompt = (
        "You are an expert writer of Pakistani-style applications, letters, and emails "
        "used in schools, colleges, universities, and offices. "
        "You write balanced, well-structured documents in clear English. "
        "You strictly follow Pakistani formal writing format."
    )

    # ── USER PROMPT ─────────────────────────────────────────
    user_prompt = f"""
Write a {doc_label} in Pakistani standard format.

DOCUMENT TYPE : {doc_label}
TONE          : {tone.capitalize()} — {tone_instr}

SENDER DETAILS:
{sender_block}

RECIPIENT DETAILS:
{recipient_block}

SUBJECT:
{subject}

ADDITIONAL CONTEXT:
{extra_details if extra_details else "None provided"}


STRICT RULES (VERY IMPORTANT):

1. Use SIMPLE English (Pakistan style, not Western complex English)
2. Write exactly 2 paragraphs — each paragraph must be 3 to 4 sentences, not too short and not too long
3. DO NOT write unnecessary filler or padding sentences
4. DO NOT repeat the subject inside the body
5. DO NOT add headings like "Application for Leave"
6. Each sentence must carry meaningful information


STRUCTURE FORMAT:

Start EXACTLY like this:

{salutation},

[Paragraph 1: Clearly state your purpose and provide relevant background in 3–4 sentences]

[Paragraph 2: Explain your reason in detail, add any supporting context, and make a polite request in 3–4 sentences]

I shall be very thankful to you.

{closing},
{sender_name if sender_name else "Applicant"}


IMPORTANT RULES:

- Use "{salutation}" as greeting
- Use "{closing}" as closing
- Always end with: "I shall be very thankful to you."
- Keep tone: {tone}
- Keep sentences clear, meaningful, and complete
- Do NOT write one-line paragraphs
- Do NOT write overly long paragraphs either


FINAL OUTPUT:

- Ready to print
- Clean formatting
- No placeholders
- No extra explanation
- Only the final document text
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=2000,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print("AI ERROR:", e)
        raise
