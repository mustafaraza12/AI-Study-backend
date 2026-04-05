from flask import Flask, request, jsonify
from flask_cors import CORS
from routes.assignment import solve_assignment
from routes.summarize import summarize_text
from routes.quiz import generate_quiz
from routes.code_helper import explain_code
from routes.slide import explain_slide_text
from routes.youtube import explain_youtube
from routes.humanize import humanize_text
from routes.math import solve_math, solve_math_image
from routes.essay import write_essay
from routes.flash import generate_flashcards, extract_text_from_file
from flask_jwt_extended import JWTManager
from routes.auth import auth_bp
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from routes.assignmentmaker import write_assignment
from routes.Letter import generate_letter, DOC_LABELS
import traceback
import json
from routes.Iq import generate_questions, evaluate_answers

import os
import tempfile
from werkzeug.utils import secure_filename
from pptx import Presentation
import PyPDF2
import docx
import openpyxl

app = Flask(__name__)
CORS(app)

# ✅ JWT
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET", "aistudysecretkey123")
jwt = JWTManager(app)

# ✅ Register blueprint
app.register_blueprint(auth_bp, url_prefix="/auth")

# ✅ GLOBAL RATE LIMITER — 20 requests per day across ALL AI tools
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],          # no default — we control manually
    storage_uri="memory://"
)

# Auth routes — separate limits
limiter.limit("5 per hour")(app.view_functions["auth_routes.register"])
limiter.limit("10 per hour")(app.view_functions["auth_routes.login"])

# ✅ Global AI limit — 20 requests per day per IP
AI_LIMIT = "20 per day"

# ── Folders ──────────────────────────────────────────────────
UPLOAD_FOLDER = "./uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_SLIDE_EXTENSIONS = {"pptx", "ppt", "pdf"}
ALLOWED_DOC_EXTENSIONS   = {"pdf", "doc", "docx", "ppt", "pptx", "xlsx", "txt"}

def allowed_slide_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_SLIDE_EXTENSIONS

def allowed_doc_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_DOC_EXTENSIONS

# ── Text extractors ──────────────────────────────────────────

def extract_text_from_pptx(file_path):
    prs = Presentation(file_path)
    slides_text = []
    for idx, slide in enumerate(prs.slides):
        text = ""
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text += shape.text + "\n"
        slides_text.append({"slide_number": idx + 1, "text": text.strip()})
    return slides_text

def extract_text_from_pdf(file_path):
    slides_text = []
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for idx, page in enumerate(reader.pages):
            text = page.extract_text()
            slides_text.append({"slide_number": idx + 1, "text": text.strip() if text else ""})
    return slides_text

def extract_doc_text(file_path, filename):
    ext = filename.lower().rsplit(".", 1)[-1]
    text = ""
    if ext == "pdf":
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
    elif ext in ("doc", "docx"):
        document = docx.Document(file_path)
        for para in document.paragraphs:
            text += para.text + "\n"
    elif ext in ("ppt", "pptx"):
        prs = Presentation(file_path)
        for i, slide in enumerate(prs.slides):
            text += f"Slide {i + 1}:\n"
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    text += shape.text + "\n"
            text += "\n"
    elif ext == "xlsx":
        wb = openpyxl.load_workbook(file_path, data_only=True)
        for sheet in wb.worksheets:
            text += f"Sheet: {sheet.title}\n"
            for row in sheet.iter_rows(values_only=True):
                row_text = "\t".join(str(c) for c in row if c is not None)
                if row_text.strip():
                    text += row_text + "\n"
            text += "\n"
    elif ext == "txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    return text

# ── Helper: return remaining requests in response ────────────
def add_rate_headers(response):
    """Adds X-RateLimit-Remaining header so frontend can show it."""
    return response

# ── AI Tool Routes (ALL use AI_LIMIT) ───────────────────────

@app.route("/solve-assignment", methods=["POST"])
@limiter.limit(AI_LIMIT)
def solve():
    try:
        data = request.json
        question = data.get("question")
        if not question:
            return jsonify({"error": "No question provided"}), 400
        answer = solve_assignment(question)
        return jsonify({"answer": answer})
    except Exception as e:
        print("SERVER ERROR:", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/summarize-pdf", methods=["POST"])
def summarize_pdf():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        if not text.strip():
            return jsonify({"error": "PDF is empty"}), 400
        summary = summarize_text(text)
        return jsonify({"summary": summary})
    except Exception as e:
        print("SERVER ERROR (Summarize PDF):", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/summarize-document", methods=["POST"])
@limiter.limit(AI_LIMIT)
def summarize_document():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        if not allowed_doc_file(file.filename):
            return jsonify({"error": "Unsupported file type"}), 400
        ext = file.filename.rsplit(".", 1)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        try:
            text = extract_doc_text(tmp_path, file.filename)
            if not text.strip():
                return jsonify({"error": "Could not extract text from this document."}), 422
            summary = summarize_text(text[:6000])
            return jsonify({"summary": summary})
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as e:
        print("SERVER ERROR (Summarize Document):", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/generate-quiz", methods=["POST"])
@limiter.limit(AI_LIMIT)
def generate_quiz_route():
    try:
        data         = request.json
        text         = data.get("text")
        num_question = data.get("num_question", 20)
        if not text:
            return jsonify({"error": "No text provided"}), 400
        quiz = generate_quiz(text, num_question)
        if not quiz:
            return jsonify({"error": "Could not generate quiz."}), 400
        return jsonify({"quiz": quiz})
    except Exception as e:
        print("SERVER ERROR (Generate Quiz):", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/explain-code", methods=["POST"])
@limiter.limit(AI_LIMIT)
def code_explainer():
    data = request.json
    code = data.get("code")
    language = data.get("language", "Python")
    if not code:
        return jsonify({"explanation": "No code provided!"})
    explanation = explain_code(code, language)
    return jsonify({"explanation": explanation})


@app.route("/explain-slide", methods=["POST"])
@limiter.limit(AI_LIMIT)
def slide_explainer():
    if "file" not in request.files:
        return jsonify({"explanation": "No file uploaded!"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"explanation": "No file selected!"}), 400
    if not allowed_slide_file(file.filename):
        return jsonify({"explanation": "File type not allowed!"}), 400
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    ext = filename.rsplit(".", 1)[1].lower()
    if ext in ["pptx", "ppt"]:
        slides = extract_text_from_pptx(file_path)
    elif ext == "pdf":
        slides = extract_text_from_pdf(file_path)
    else:
        return jsonify({"explanation": "Unsupported file type"}), 400
    combined_explanation = ""
    for slide in slides:
        if not slide["text"]:
            continue
        explanation = explain_slide_text(slide["text"], language="Slides")
        combined_explanation += f"### Slide {slide['slide_number']}\n{explanation}\n\n"
    return jsonify({"explanation": combined_explanation})


@app.route("/humanize-text", methods=["POST"])
@limiter.limit(AI_LIMIT)
def humanize():
    data = request.json
    text = data.get("text")
    if not text:
        return jsonify({"error": "No text provided"}), 400
    result = humanize_text(text)
    return jsonify({"humanized": result})


@app.route("/explain-youtube", methods=["POST"])
@limiter.limit(AI_LIMIT)
def youtube_explainer():
    try:
        data = request.json
        url = data.get("url")
        if not url:
            return jsonify({"error": "No YouTube URL provided"}), 400
        explanation = explain_youtube(url)
        return jsonify({"explanation": explanation})
    except Exception as e:
        print("SERVER ERROR (YouTube Explainer):", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/solve-math", methods=["POST"])
@limiter.limit(AI_LIMIT)
def math_solver():
    try:
        data = request.json
        problem = data.get("problem")
        if not problem:
            return jsonify({"error": "No problem provided"}), 400
        solution = solve_math(problem)
        return jsonify({"solution": solution})
    except Exception as e:
        print("Math Solver Error:", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/solve-math-image", methods=["POST"])
@limiter.limit(AI_LIMIT)
def math_solver_image():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400
        file = request.files["image"]
        solution = solve_math_image(file)
        return jsonify({"solution": solution})
    except Exception as e:
        print("Math Image Solver Error:", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/write-essay", methods=["POST"])
@limiter.limit(AI_LIMIT)
def essay_writer():
    try:
        data       = request.json
        topic      = data.get("topic")
        essay_type = data.get("essayType", "argumentative")
        tone       = data.get("tone", "Academic")
        word_count = data.get("wordCount", 500)
        language   = data.get("language", "English")
        if not topic:
            return jsonify({"error": "No topic provided"}), 400
        essay = write_essay(topic, essay_type, tone, word_count, language)
        return jsonify({"essay": essay})
    except Exception as e:
        print("Essay Writer Error:", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/generate-flashcards", methods=["POST"])
@limiter.limit(AI_LIMIT)
def flashcard_generator():
    try:
        data       = request.json
        text       = data.get("text", "")
        card_count = int(data.get("cardCount", 10))
        subject    = data.get("subject", "")
        if not text:
            return jsonify({"error": "No text provided"}), 400
        cards = generate_flashcards(text, card_count, subject)
        if not cards:
            return jsonify({"error": "Could not generate flashcards."}), 400
        return jsonify({"flashcards": cards})
    except Exception as e:
        print("Flashcard Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/generate-flashcards-file", methods=["POST"])
@limiter.limit(AI_LIMIT)
def flashcard_generator_file():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        file       = request.files["file"]
        card_count = int(request.form.get("cardCount", 10))
        subject    = request.form.get("subject", "")
        text = extract_text_from_file(file, file.filename)
        if not text.strip():
            return jsonify({"error": "Could not extract text from file."}), 422
        cards = generate_flashcards(text, card_count, subject)
        if not cards:
            return jsonify({"error": "Could not generate flashcards from this file."}), 400
        return jsonify({"flashcards": cards})
    except Exception as e:
        print("Flashcard File Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/assignment", methods=["POST"])
@limiter.limit(AI_LIMIT)
def generate_assignment():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON body provided."}), 400
        topic = data.get("topic", "").strip()
        if not topic:
            return jsonify({"success": False, "error": "Assignment topic is required."}), 400
        pages        = int(data.get("pages", 3))
        subject      = data.get("subject", topic).strip()
        student_name = data.get("student_name", "Student Name").strip()
        roll_no      = data.get("roll_no", "N/A").strip()
        professor    = data.get("professor", "Professor").strip()
        humanize     = bool(data.get("humanize", True))
        if pages < 1 or pages > 10:
            return jsonify({"success": False, "error": "Pages must be between 1 and 10."}), 400
        content = write_assignment(
            topic=topic, pages=pages, subject=subject,
            student_name=student_name, roll_no=roll_no,
            professor=professor, humanize=humanize,
        )
        if content.startswith("Error generating assignment:"):
            return jsonify({"success": False, "error": content}), 500
        return jsonify({"success": True, "content": content})
    except ValueError as ve:
        return jsonify({"success": False, "error": f"Invalid input: {str(ve)}"}), 400
    except Exception as e:
        print(f"[/api/assignment] Unexpected error: {e}")
        return jsonify({"success": False, "error": "An unexpected error occurred."}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "IQ Test API"})


@app.route("/api/iq/generate", methods=["POST"])
@limiter.limit(AI_LIMIT)
def api_generate():
    try:
        body      = request.get_json(force=True)
        name      = str(body.get("name",      "")).strip()
        age       = int(body.get("age",        0))
        education = str(body.get("education", "")).strip()
        subject   = str(body.get("subject",   "")).strip()
        grade     = str(body.get("grade",     "")).strip()
        count     = int(body.get("count",      15))
        if not name:
            return jsonify({"success": False, "error": "Name is required"}), 400
        if age < 5 or age > 100:
            return jsonify({"success": False, "error": "Invalid age (must be 5–100)"}), 400
        if not education:
            return jsonify({"success": False, "error": "Education level is required"}), 400
        if count < 5 or count > 30:
            return jsonify({"success": False, "error": "Count must be between 5 and 30"}), 400
        questions, time_per_q = generate_questions(
            name=name, age=age, education=education,
            subject=subject, grade=grade, count=count,
        )
        return jsonify({"success": True, "questions": questions, "time_per_question": time_per_q})
    except json.JSONDecodeError as e:
        return jsonify({"success": False, "error": f"AI returned invalid JSON: {str(e)}"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/iq/evaluate", methods=["POST"])
@limiter.limit(AI_LIMIT)
def api_evaluate():
    try:
        body       = request.get_json(force=True)
        name       = str(body.get("name",      "")).strip()
        age        = int(body.get("age",        0))
        education  = str(body.get("education", "")).strip()
        subject    = str(body.get("subject",   "")).strip()
        grade      = str(body.get("grade",     "")).strip()
        questions  = body.get("questions",  [])
        answers    = body.get("answers",    {})
        timed_out  = bool(body.get("timed_out",  False))
        time_taken = int(body.get("time_taken",  0))
        if not questions:
            return jsonify({"success": False, "error": "No questions provided"}), 400
        result = evaluate_answers(
            name=name, age=age, education=education,
            subject=subject, grade=grade,
            questions=questions, answers=answers,
            timed_out=timed_out, time_taken=time_taken,
        )
        return jsonify({"success": True, "result": result})
    except json.JSONDecodeError as e:
        return jsonify({"success": False, "error": f"AI returned invalid JSON: {str(e)}"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/letter/types", methods=["GET"])
def api_letter_types():
    types = [{"id": k, "label": v} for k, v in DOC_LABELS.items()]
    return jsonify({"success": True, "types": types})


@app.route("/api/letter/generate", methods=["POST"])
@limiter.limit(AI_LIMIT)
def api_letter_generate():
    try:
        body            = request.get_json(force=True)
        doc_type        = str(body.get("doc_type",         "")).strip()
        tone            = str(body.get("tone",        "formal")).strip().lower()
        subject         = str(body.get("subject",          "")).strip()
        sender_name     = str(body.get("sender_name",      "")).strip()
        sender_title    = str(body.get("sender_title",     "")).strip()
        sender_org      = str(body.get("sender_org",       "")).strip()
        sender_addr     = str(body.get("sender_addr",      "")).strip()
        recipient_name  = str(body.get("recipient_name",   "")).strip()
        recipient_title = str(body.get("recipient_title",  "")).strip()
        recipient_org   = str(body.get("recipient_org",    "")).strip()
        recipient_addr  = str(body.get("recipient_addr",   "")).strip()
        extra_details   = str(body.get("extra_details",    "")).strip()
        if not doc_type:
            return jsonify({"success": False, "error": "doc_type is required"}), 400
        if doc_type not in DOC_LABELS:
            return jsonify({"success": False, "error": f"Unknown doc_type '{doc_type}'."}), 400
        if not subject:
            return jsonify({"success": False, "error": "subject is required"}), 400
        valid_tones = {"formal", "polite", "humble", "confident", "urgent"}
        if tone not in valid_tones:
            tone = "formal"
        content = generate_letter(
            doc_type=doc_type, tone=tone, subject=subject,
            sender_name=sender_name, sender_title=sender_title,
            sender_org=sender_org, sender_addr=sender_addr,
            recipient_name=recipient_name, recipient_title=recipient_title,
            recipient_org=recipient_org, recipient_addr=recipient_addr,
            extra_details=extra_details,
        )
        return jsonify({"success": True, "content": content})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ── Custom error for rate limit exceeded ─────────────────────
@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({
        "error": "Daily limit reached",
        "message": "You have used all 20 free requests for today. Please come back tomorrow!",
        "retry_after": "24 hours"
    }), 429


if __name__ == "__main__":
    app.run(debug=True, port=5000)
