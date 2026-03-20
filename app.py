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

import os
import tempfile
from werkzeug.utils import secure_filename
from pptx import Presentation
import PyPDF2
import docx
import openpyxl

app = Flask(__name__)
CORS(app)

# ✅ 1. JWT first
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET", "aistudysecretkey123")
jwt = JWTManager(app)

# ✅ 2. Register blueprint second
app.register_blueprint(auth_bp, url_prefix="/auth")

# ✅ 3. Limiter third
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# ✅ 4. Apply limits last — after blueprint is registered
limiter.limit("5 per hour")(app.view_functions["auth_routes.register"])
limiter.limit("10 per hour")(app.view_functions["auth_routes.login"])

# Folder for uploaded files
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
    """Extract plain text from any supported document type."""
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

# ── Existing Routes ──────────────────────────────────────────

@app.route("/solve-assignment", methods=["POST"])
@limiter.limit("20 per hour")
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


# Kept for backward compatibility
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


# New document summarizer — handles PDF, Word, PPT, Excel, TXT
@app.route("/summarize-document", methods=["POST"])
@limiter.limit("15 per hour")
def summarize_document():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        if not allowed_doc_file(file.filename):
            return jsonify({"error": "Unsupported file type"}), 400

        # Save to temp file with correct extension
        ext = file.filename.rsplit(".", 1)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            text = extract_doc_text(tmp_path, file.filename)

            if not text.strip():
                return jsonify({"error": "Could not extract text from this document."}), 422

            # Cap at 6000 chars to stay within token limits
            summary = summarize_text(text[:6000])
            return jsonify({"summary": summary})

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        print("SERVER ERROR (Summarize Document):", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/generate-quiz", methods=["POST"])
@limiter.limit("15 per hour")
def generate_quiz_route():
    try:
        data         = request.json
        text         = data.get("text")
        num_question = data.get("num_question", 20)

        if not text:
            return jsonify({"error": "No text provided"}), 400

        quiz = generate_quiz(text, num_question)

        if not quiz:
            return jsonify({"error": "Could not generate quiz. Try a different topic."}), 400

        return jsonify({"quiz": quiz})

    except Exception as e:
        print("SERVER ERROR (Generate Quiz):", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/explain-code", methods=["POST"])
@limiter.limit("15 per hour")
def code_explainer():
    data = request.json
    code = data.get("code")
    language = data.get("language", "Python")

    if not code:
        return jsonify({"explanation": "No code provided!"})

    explanation = explain_code(code, language)
    return jsonify({"explanation": explanation})


@app.route("/explain-slide", methods=["POST"])
@limiter.limit("10 per hour")
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
@limiter.limit("20 per hour")
def humanize():
    data = request.json
    text = data.get("text")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    result = humanize_text(text)
    return jsonify({"humanized": result})


@app.route("/explain-youtube", methods=["POST"])
@limiter.limit("10 per hour")
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
@limiter.limit("20 per hour")
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
@limiter.limit("20 per hour")
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
@limiter.limit("10 per hour")
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
@limiter.limit("15 per hour")
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
            return jsonify({"error": "Could not generate flashcards. Try with more content."}), 400

        return jsonify({"flashcards": cards})

    except Exception as e:
        print("Flashcard Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/generate-flashcards-file", methods=["POST"])
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




if __name__ == "__main__":
    app.run(debug=True, port=5000)